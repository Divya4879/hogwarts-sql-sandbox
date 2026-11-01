
import os
import re
from collections import Counter

import psycopg2
import pytest


# =========================================================
# Configuration
# =========================================================

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "hogwarts"),
    "user": os.getenv("DB_USER", "wizard"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

SOLUTION_FILE = "solutions/04_solutions.sql"
WORKSPACE_FILE = "workspace/03_challenges.sql"

EXPECTED_QUESTION_IDS = set(range(1, 31))

# Q29 creates a materialized view.
# Q30 uses EXPLAIN ANALYZE.
# Both require dedicated tests.
COMPARABLE_QUERY_IDS = range(1, 29)

QUESTION_MARKER_PATTERN = re.compile(
    r"(?m)^\s*--\s*QUESTION\s+(\d+)\s*:\s*.*$",
    flags=re.IGNORECASE,
)


# =========================================================
# SQL Parsing Utilities
# =========================================================

def remove_comments(sql):
    """
    Remove SQL comments without modifying comments-like text
    inside strings or quoted identifiers.

    Handles:
    - Single-quoted strings
    - Double-quoted identifiers
    - Dollar-quoted strings
    - Line comments (-- ...)
    - Nested block comments (/* ... */)

    Newlines are preserved to avoid joining separate SQL lines.
    """

    result = []
    i = 0
    length = len(sql)

    state = "normal"
    block_depth = 0
    dollar_delimiter = None
    escape_string = False

    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""

        # ---------------------------------------------
        # Inside a single-quoted string
        # ---------------------------------------------
        if state == "single":
            result.append(char)

            if escape_string and char == "\\":
                if i + 1 < length:
                    result.append(sql[i + 1])
                    i += 2
                    continue

            if char == "'":
                if next_char == "'":
                    result.append(next_char)
                    i += 2
                    continue

                state = "normal"
                escape_string = False

            i += 1
            continue

        # ---------------------------------------------
        # Inside a double-quoted identifier
        # ---------------------------------------------
        if state == "double":
            result.append(char)

            if char == '"':
                if next_char == '"':
                    result.append(next_char)
                    i += 2
                    continue

                state = "normal"

            i += 1
            continue

        # ---------------------------------------------
        # Inside a dollar-quoted string
        # ---------------------------------------------
        if state == "dollar":
            if sql.startswith(dollar_delimiter, i):
                result.append(dollar_delimiter)
                i += len(dollar_delimiter)
                state = "normal"
                dollar_delimiter = None
                continue

            result.append(char)
            i += 1
            continue

        # ---------------------------------------------
        # Inside a line comment
        # ---------------------------------------------
        if state == "line_comment":
            if char == "\n":
                result.append("\n")
                state = "normal"
            else:
                result.append(" ")

            i += 1
            continue

        # ---------------------------------------------
        # Inside a block comment
        # ---------------------------------------------
        if state == "block_comment":
            if char == "/" and next_char == "*":
                result.extend([" ", " "])
                block_depth += 1
                i += 2
                continue

            if char == "*" and next_char == "/":
                result.extend([" ", " "])
                block_depth -= 1
                i += 2

                if block_depth == 0:
                    state = "normal"

                continue

            result.append("\n" if char == "\n" else " ")
            i += 1
            continue

        # =================================================
        # Normal SQL state
        # =================================================

        # Start of a single-quoted string.
        if char == "'":
            previous = sql[i - 1] if i > 0 else ""
            before_previous = sql[i - 2] if i > 1 else ""

            # PostgreSQL E'...' escape strings.
            escape_string = (
                previous in ("e", "E")
                and (
                    not before_previous
                    or not (
                        before_previous.isalnum()
                        or before_previous in ("_", "$")
                    )
                )
            )

            result.append(char)
            state = "single"
            i += 1
            continue

        # Start of a quoted identifier.
        if char == '"':
            result.append(char)
            state = "double"
            i += 1
            continue

        # Start of a line comment.
        if char == "-" and next_char == "-":
            result.extend([" ", " "])
            state = "line_comment"
            i += 2
            continue

        # Start of a block comment.
        if char == "/" and next_char == "*":
            result.extend([" ", " "])
            state = "block_comment"
            block_depth = 1
            i += 2
            continue

        # Start of a dollar-quoted string.
        if char == "$":
            match = re.match(
                r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$",
                sql[i:]
            )

            if match:
                dollar_delimiter = match.group(0)
                result.append(dollar_delimiter)
                state = "dollar"
                i += len(dollar_delimiter)
                continue

        result.append(char)
        i += 1

    return "".join(result).strip()


def split_sql_statements(sql):
    """
    Split SQL into individual statements using semicolons.

    Semicolons inside strings, quoted identifiers, and
    dollar-quoted strings are not treated as delimiters.
    """

    sql = remove_comments(sql)

    statements = []
    current = []

    i = 0
    length = len(sql)

    state = "normal"
    dollar_delimiter = None
    escape_string = False

    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""

        if state == "single":
            current.append(char)

            if escape_string and char == "\\":
                if i + 1 < length:
                    current.append(sql[i + 1])
                    i += 2
                    continue

            if char == "'":
                if next_char == "'":
                    current.append(next_char)
                    i += 2
                    continue

                state = "normal"
                escape_string = False

            i += 1
            continue

        if state == "double":
            current.append(char)

            if char == '"':
                if next_char == '"':
                    current.append(next_char)
                    i += 2
                    continue

                state = "normal"

            i += 1
            continue

        if state == "dollar":
            if sql.startswith(dollar_delimiter, i):
                current.append(dollar_delimiter)
                i += len(dollar_delimiter)
                state = "normal"
                dollar_delimiter = None
                continue

            current.append(char)
            i += 1
            continue

        if char == "'":
            previous = sql[i - 1] if i > 0 else ""
            before_previous = sql[i - 2] if i > 1 else ""

            escape_string = (
                previous in ("e", "E")
                and (
                    not before_previous
                    or not (
                        before_previous.isalnum()
                        or before_previous in ("_", "$")
                    )
                )
            )

            current.append(char)
            state = "single"
            i += 1
            continue

        if char == '"':
            current.append(char)
            state = "double"
            i += 1
            continue

        if char == "$":
            match = re.match(
                r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$",
                sql[i:]
            )

            if match:
                dollar_delimiter = match.group(0)
                current.append(dollar_delimiter)
                state = "dollar"
                i += len(dollar_delimiter)
                continue

        if char == ";":
            statement = "".join(current).strip()

            if statement:
                statements.append(statement)

            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    remaining = "".join(current).strip()

    if remaining:
        statements.append(remaining)

    return statements


# =========================================================
# SQL File Loading
# =========================================================

def extract_question_markers(filepath):
    """Return every question marker found in a SQL file."""

    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"Could not find SQL file: {filepath}"
        )

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    return [
        int(match.group(1))
        for match in QUESTION_MARKER_PATTERN.finditer(content)
    ]


def load_numbered_queries(filepath):
    """
    Extract SQL blocks using the question marker convention:

        -- QUESTION 1: Description
        SELECT ...

        -- QUESTION 2: Description
        SELECT ...

    Empty blocks are ignored. This allows the challenge file
    to contain question descriptions without completed answers.
    """

    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"Could not find SQL file: {filepath}"
        )

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    markers = list(QUESTION_MARKER_PATTERN.finditer(content))

    queries = {}

    for index, marker in enumerate(markers):
        query_id = int(marker.group(1))

        if query_id in queries:
            raise ValueError(
                f"Duplicate question marker: {query_id} "
                f"in {filepath}"
            )

        start = marker.end()

        end = (
            markers[index + 1].start()
            if index + 1 < len(markers)
            else len(content)
        )

        query_sql = remove_comments(content[start:end])

        if query_sql:
            queries[query_id] = query_sql

    return queries


# =========================================================
# Database Fixture
# =========================================================

@pytest.fixture(scope="module")
def db_cursor():
    """Connect to PostgreSQL and provide a cursor."""

    connection = psycopg2.connect(**DB_CONFIG)
    connection.autocommit = False

    cursor = connection.cursor()

    yield cursor

    connection.rollback()
    cursor.close()
    connection.close()


# =========================================================
# Result Normalization and Comparison
# =========================================================

def normalize_value(value):
    """Convert nested values into comparable structures."""

    if isinstance(value, dict):
        return tuple(
            sorted(
                (key, normalize_value(val))
                for key, val in value.items()
            )
        )

    if isinstance(value, list):
        return tuple(
            normalize_value(item)
            for item in value
        )

    if isinstance(value, tuple):
        return tuple(
            normalize_value(item)
            for item in value
        )

    return value


def execute_and_capture(cursor, sql):
    """
    Execute SQL and capture column names and result rows.

    Counter preserves duplicate rows while ignoring row order.
    """

    cursor.execute(sql)

    if cursor.description is None:
        return None, None

    columns = tuple(
        description[0]
        for description in cursor.description
    )

    rows = cursor.fetchall()

    normalized_rows = Counter(
        normalize_value(row)
        for row in rows
    )

    return columns, normalized_rows


def compare_queries(cursor, user_sql, reference_sql, query_id):
    """
    Execute user and reference queries in separate savepoints.

    Each execution is rolled back before the next one, preventing
    data modifications from affecting subsequent comparisons.
    """

    savepoint = f"question_{query_id}"

    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        try:
            user_columns, user_rows = execute_and_capture(
                cursor, user_sql
            )
        except Exception as error:
            cursor.execute(
                f"ROLLBACK TO SAVEPOINT {savepoint}"
            )

            pytest.fail(
                f"Question {query_id}: Your query raised an error:\n"
                f"{error}"
            )

        cursor.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )

        try:
            reference_columns, reference_rows = execute_and_capture(
                cursor, reference_sql
            )
        except Exception as error:
            cursor.execute(
                f"ROLLBACK TO SAVEPOINT {savepoint}"
            )

            pytest.fail(
                f"Question {query_id}: The reference solution "
                f"raised an error:\n{error}"
            )

        cursor.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )

        assert user_columns is not None, (
            f"Question {query_id}: Your query did not return "
            f"a result set."
        )

        assert reference_columns is not None, (
            f"Question {query_id}: The reference solution did not "
            f"return a result set."
        )

        assert user_columns == reference_columns, (
            f"Question {query_id}: Column names do not match.\n"
            f"Your columns:       {user_columns}\n"
            f"Reference columns: {reference_columns}"
        )

        assert user_rows == reference_rows, (
            f"Question {query_id}: Result rows do not match.\n"
            f"Your result:       {user_rows}\n"
            f"Reference result: {reference_rows}"
        )

    finally:
        cursor.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )
        cursor.execute(
            f"RELEASE SAVEPOINT {savepoint}"
        )


# =========================================================
# Materialized View Testing — Question 29
# =========================================================

EXPECTED_METRIC_COLUMNS = (
    "exam_date",
    "total_exams",
    "failed_exams",
    "failure_rate_percent",
)


def capture_materialized_view(cursor, sql, label):
    """
    Execute a materialized-view definition in isolation.

    Then read the actual contents of daily_exam_metrics.

    The savepoint ensures the materialized view is removed
    when the test finishes.
    """

    savepoint = f"q29_{label}"

    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        cursor.execute(
            "DROP MATERIALIZED VIEW IF EXISTS daily_exam_metrics"
        )

        statements = split_sql_statements(sql)

        if not statements:
            pytest.fail(
                f"Question 29: {label} contains no SQL statements."
            )

        for statement in statements:
            cursor.execute(statement)

        cursor.execute(
            """
            SELECT
                exam_date,
                total_exams,
                failed_exams,
                failure_rate_percent
            FROM daily_exam_metrics
            ORDER BY exam_date
            """
        )

        columns = tuple(
            description[0]
            for description in cursor.description
        )

        rows = Counter(
            normalize_value(row)
            for row in cursor.fetchall()
        )

        return columns, rows

    except Exception as error:
        pytest.fail(
            f"Question 29: {label} materialized view failed:\n"
            f"{error}"
        )

    finally:
        cursor.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )
        cursor.execute(
            f"RELEASE SAVEPOINT {savepoint}"
        )


def capture_expected_daily_metrics(cursor):
    """
    Independently calculate the expected daily metrics
    directly from the exams table.

    This prevents Q29 from passing merely because the
    user and reference definitions are equally incorrect.
    """

    cursor.execute(
        """
        SELECT
            exam_date,
            COUNT(*) AS total_exams,
            COUNT(*) FILTER (
                WHERE grade_result IN ('p', 'troll')
            ) AS failed_exams,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE grade_result IN ('p', 'troll')
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS failure_rate_percent
        FROM exams
        GROUP BY exam_date
        ORDER BY exam_date
        """
    )

    columns = tuple(
        description[0]
        for description in cursor.description
    )

    rows = Counter(
        normalize_value(row)
        for row in cursor.fetchall()
    )

    return columns, rows


# =========================================================
# EXPLAIN ANALYZE Testing — Question 30
# =========================================================

def extract_explain_statements(sql):
    """Extract EXPLAIN statements from a SQL question block."""

    statements = split_sql_statements(sql)

    return [
        statement
        for statement in statements
        if re.match(
            r"^\s*EXPLAIN\b",
            statement,
            flags=re.IGNORECASE
        )
    ]


def remove_explain_prefix(statement):
    """
    Remove EXPLAIN ANALYZE from a statement so that
    the underlying query can be executed and compared.

    Supports:
        EXPLAIN ANALYZE SELECT ...
        EXPLAIN (ANALYZE, BUFFERS) SELECT ...
    """

    pattern = re.compile(
        r"""
        ^\s*
        EXPLAIN
        \s+
        (?:
            ANALYZE\b
            |
            \([^)]*\bANALYZE\b[^)]*\)
        )
        \s*
        """,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    match = pattern.match(statement)

    if not match:
        raise ValueError(
            "Question 30 requires EXPLAIN ANALYZE statements."
        )

    query = statement[match.end():].strip()

    if not re.match(
        r"^(SELECT|WITH)\b",
        query,
        flags=re.IGNORECASE
    ):
        raise ValueError(
            "Question 30 should use SELECT queries inside "
            "EXPLAIN ANALYZE."
        )

    return query


def extract_plan_metrics(plan_text):
    """
    Extract useful metrics from EXPLAIN ANALYZE output.

    Execution time and planning time are reported for comparison.
    Estimated total cost is also extracted when available.
    """

    execution_match = re.search(
        r"Execution Time:\s*([\d.]+)\s*ms",
        plan_text,
        flags=re.IGNORECASE
    )

    planning_match = re.search(
        r"Planning Time:\s*([\d.]+)\s*ms",
        plan_text,
        flags=re.IGNORECASE
    )

    cost_match = re.search(
        r"cost=[\d.]+\.\.([\d.]+)",
        plan_text,
        flags=re.IGNORECASE
    )

    actual_match = re.search(
        r"actual time=[\d.]+\.\.([\d.]+)",
        plan_text,
        flags=re.IGNORECASE
    )

    if not execution_match or not planning_match:
        raise ValueError(
            "The EXPLAIN ANALYZE output is missing "
            "planning or execution time."
        )

    if not actual_match:
        raise ValueError(
            "The EXPLAIN ANALYZE output does not contain "
            "actual execution details."
        )

    return {
        "execution_time_ms": float(execution_match.group(1)),
        "planning_time_ms": float(planning_match.group(1)),
        "estimated_total_cost": (
            float(cost_match.group(1))
            if cost_match
            else None
        ),
        "root_actual_time_ms": float(actual_match.group(1)),
    }


def execute_and_capture_plan(cursor, explain_statement, label):
    """
    Execute one EXPLAIN ANALYZE statement.

    Capture:
    - The execution plan
    - Planning and execution time
    - Estimated cost, when available
    - Results of the underlying SELECT query

    Everything runs inside a savepoint.
    """

    savepoint = f"q30_{label}"

    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        cursor.execute(explain_statement)

        plan_rows = cursor.fetchall()

        plan_text = "\n".join(
            str(row[0])
            for row in plan_rows
        )

        if not plan_text.strip():
            raise ValueError(
                "EXPLAIN ANALYZE returned an empty execution plan."
            )

        metrics = extract_plan_metrics(plan_text)

        underlying_query = remove_explain_prefix(
            explain_statement
        )

        columns, rows = execute_and_capture(
            cursor,
            underlying_query
        )

        if columns is None:
            raise ValueError(
                "The underlying Q30 query did not return "
                "a result set."
            )

        return {
            "plan": plan_text,
            "metrics": metrics,
            "columns": columns,
            "rows": rows,
        }

    except Exception as error:
        pytest.fail(
            f"Question 30: {label} execution plan failed:\n"
            f"{error}"
        )

    finally:
        cursor.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )
        cursor.execute(
            f"RELEASE SAVEPOINT {savepoint}"
        )


# =========================================================
# Load Both SQL Files Once
# =========================================================

@pytest.fixture(scope="module")
def query_files():
    user_queries = load_numbered_queries(WORKSPACE_FILE)
    reference_queries = load_numbered_queries(SOLUTION_FILE)

    return user_queries, reference_queries


# =========================================================
# Marker Integrity Tests
# =========================================================

@pytest.mark.parametrize(
    "filepath",
    [WORKSPACE_FILE, SOLUTION_FILE]
)
def test_question_marker_integrity(filepath):
    """
    Verify that each SQL file contains exactly one marker
    for every question from 1 through 30.

    Detects:
    - Missing markers
    - Duplicate markers
    - Unexpected question numbers
    """

    marker_ids = extract_question_markers(filepath)

    marker_counts = Counter(marker_ids)

    duplicates = sorted(
        question_id
        for question_id, count in marker_counts.items()
        if count > 1
    )

    actual_ids = set(marker_ids)

    missing = sorted(
        EXPECTED_QUESTION_IDS - actual_ids
    )

    unexpected = sorted(
        actual_ids - EXPECTED_QUESTION_IDS
    )

    assert not duplicates, (
        f"{filepath}: Duplicate question markers: {duplicates}"
    )

    assert not missing, (
        f"{filepath}: Missing question markers: {missing}"
    )

    assert not unexpected, (
        f"{filepath}: Unexpected question markers: {unexpected}"
    )

    assert len(marker_ids) == 30, (
        f"{filepath}: Expected exactly 30 markers, "
        f"found {len(marker_ids)}."
    )


# =========================================================
# Database Connection Test
# =========================================================

def test_sandbox_connection(db_cursor):
    """Verify that the database and seed data are available."""

    db_cursor.execute(
        "SELECT COUNT(*) FROM students"
    )

    student_count = db_cursor.fetchone()[0]

    assert student_count > 0, (
        "The database has no students. "
        "Check whether the schema and seed scripts have run."
    )


# =========================================================
# Q1–Q28: Compare Answers Against Reference Solutions
# =========================================================

@pytest.mark.parametrize(
    "query_id",
    COMPARABLE_QUERY_IDS
)
def test_query_match_solution(db_cursor, query_files, query_id):
    user_queries, reference_queries = query_files

    assert query_id in user_queries, (
        f"Question {query_id}: No SQL answer found in "
        f"{WORKSPACE_FILE}. The challenge description alone "
        f"is not an answer."
    )

    assert query_id in reference_queries, (
        f"Question {query_id}: No reference answer found in "
        f"{SOLUTION_FILE}."
    )

    compare_queries(
        cursor=db_cursor,
        user_sql=user_queries[query_id],
        reference_sql=reference_queries[query_id],
        query_id=query_id,
    )


# =========================================================
# Q29: Validate Actual Materialized View Contents
# =========================================================

def test_query_29_materialized_view_contents(
    db_cursor,
    query_files
):
    user_queries, reference_queries = query_files

    assert 29 in user_queries, (
        "Question 29: Add your materialized-view solution "
        f"to {WORKSPACE_FILE}."
    )

    assert 29 in reference_queries, (
        "Question 29: Reference solution is missing."
    )

    user_columns, user_rows = capture_materialized_view(
        db_cursor,
        user_queries[29],
        "user"
    )

    reference_columns, reference_rows = capture_materialized_view(
        db_cursor,
        reference_queries[29],
        "reference"
    )

    expected_columns, expected_rows = (
        capture_expected_daily_metrics(db_cursor)
    )

    assert user_columns == EXPECTED_METRIC_COLUMNS, (
        "Question 29: Your materialized view has incorrect "
        f"columns.\nExpected: {EXPECTED_METRIC_COLUMNS}\n"
        f"Received: {user_columns}"
    )

    assert reference_columns == EXPECTED_METRIC_COLUMNS, (
        "Question 29: The reference materialized view has "
        "incorrect columns."
    )

    assert user_columns == reference_columns, (
        "Question 29: Your materialized-view columns do not "
        "match the reference."
    )

    assert user_rows == expected_rows, (
        "Question 29: Your materialized view contains incorrect "
        "data when compared with the exams table.\n"
        f"Your result: {user_rows}\n"
        f"Expected: {expected_rows}"
    )

    assert reference_rows == expected_rows, (
        "Question 29: The reference materialized view does not "
        "match the independently calculated daily metrics."
    )


# =========================================================
# Q30: Execute and Compare Both EXPLAIN ANALYZE Plans
# =========================================================

def test_query_30_explain_analyze_plans(
    db_cursor,
    query_files
):
    user_queries, reference_queries = query_files

    assert 30 in user_queries, (
        "Question 30: Add both EXPLAIN ANALYZE queries "
        f"to {WORKSPACE_FILE}."
    )

    assert 30 in reference_queries, (
        "Question 30: Reference solution is missing."
    )

    user_statements = extract_explain_statements(
        user_queries[30]
    )

    reference_statements = extract_explain_statements(
        reference_queries[30]
    )

    assert len(user_statements) == 2, (
        "Question 30: Your answer must contain exactly two "
        "EXPLAIN ANALYZE statements: one for each approach. "
        f"Found {len(user_statements)}."
    )

    assert len(reference_statements) == 2, (
        "Question 30: The reference must contain exactly two "
        "EXPLAIN ANALYZE statements."
    )

    user_plans = [
        execute_and_capture_plan(
            db_cursor,
            statement,
            f"user_plan_{index + 1}"
        )
        for index, statement in enumerate(user_statements)
    ]

    reference_plans = [
        execute_and_capture_plan(
            db_cursor,
            statement,
            f"reference_plan_{index + 1}"
        )
        for index, statement in enumerate(reference_statements)
    ]

    # Both user queries must return equivalent results.
    first_plan, second_plan = user_plans

    assert first_plan["columns"] == second_plan["columns"], (
        "Question 30: The two approaches return different "
        "column names."
    )

    assert first_plan["rows"] == second_plan["rows"], (
        "Question 30: The correlated and optimized queries "
        "do not return equivalent results."
    )

    # Both reference queries must also be equivalent.
    reference_first, reference_second = reference_plans

    assert reference_first["columns"] == reference_second["columns"], (
        "Question 30: The two reference approaches return "
        "different column names."
    )

    assert reference_first["rows"] == reference_second["rows"], (
        "Question 30: The two reference approaches do not "
        "return equivalent results."
    )

    # Compare user results with reference results.
    assert first_plan["columns"] == reference_first["columns"], (
        "Question 30: Your query columns do not match "
        "the reference."
    )

    assert first_plan["rows"] == reference_first["rows"], (
        "Question 30: Your query results do not match "
        "the reference."
    )

    # Display useful plan metrics for manual performance review.
    print("\nQuestion 30 — EXPLAIN ANALYZE comparison")

    for index, result in enumerate(user_plans, start=1):
        metrics = result["metrics"]

        print(f"\nYour plan {index}:")
        print(
            f"  Planning time: "
            f"{metrics['planning_time_ms']} ms"
        )
        print(
            f"  Execution time: "
            f"{metrics['execution_time_ms']} ms"
        )
        print(
            f"  Estimated total cost: "
            f"{metrics['estimated_total_cost']}"
        )
        print(
            f"  Root actual time: "
            f"{metrics['root_actual_time_ms']} ms"
        )

    # The test deliberately does not assert that the second
    # query must be faster. Execution times and planner costs
    # depend on database size, indexes, caching and hardware.
