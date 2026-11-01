import argparse
import os
import re
from collections import Counter
from pprint import pformat

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
COMPARABLE_QUERY_IDS = tuple(range(1, 29))

QUESTION_MARKER_PATTERN = re.compile(
    r"(?m)^\s*--\s*QUESTION\s+(\d+)\s*:\s*.*$",
    flags=re.IGNORECASE,
)


# =========================================================
# SQL Parsing Utilities
# =========================================================

def remove_comments(sql):
    """
    Remove SQL comments without modifying comment-like text
    inside strings or quoted identifiers.

    Handles single-quoted strings, double-quoted identifiers,
    dollar-quoted strings, line comments, and nested block comments.
    Newlines are preserved so separate SQL lines are not joined.
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

        if state == "line_comment":
            if char == "\n":
                result.append("\n")
                state = "normal"
            else:
                result.append(" ")
            i += 1
            continue

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

        # Normal SQL state.
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

        if char == '"':
            result.append(char)
            state = "double"
            i += 1
            continue

        if char == "-" and next_char == "-":
            result.extend([" ", " "])
            state = "line_comment"
            i += 2
            continue

        if char == "/" and next_char == "*":
            result.extend([" ", " "])
            state = "block_comment"
            block_depth = 1
            i += 2
            continue

        if char == "$":
            match = re.match(
                r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$",
                sql[i:],
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

    Semicolons inside strings, quoted identifiers, and dollar-quoted
    strings are not treated as statement delimiters.
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
                sql[i:],
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
        raise FileNotFoundError(f"Could not find SQL file: {filepath}")

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    return [
        int(match.group(1))
        for match in QUESTION_MARKER_PATTERN.finditer(content)
    ]


def load_numbered_queries(filepath):
    """
    Extract SQL blocks using the question marker convention.

    Empty blocks are ignored, allowing the challenge file to contain
    question descriptions without completed answers.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Could not find SQL file: {filepath}")

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    markers = list(QUESTION_MARKER_PATTERN.finditer(content))
    queries = {}

    for index, marker in enumerate(markers):
        query_id = int(marker.group(1))

        if query_id in queries:
            raise ValueError(
                f"Duplicate question marker: {query_id} in {filepath}"
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

    try:
        yield cursor
    finally:
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

    if isinstance(value, (list, tuple)):
        return tuple(normalize_value(item) for item in value)

    return value


def execute_and_capture(cursor, sql):
    """
    Execute SQL and capture column names and result rows.

    Counter preserves duplicate rows while ignoring row order.
    """
    cursor.execute(sql)

    if cursor.description is None:
        return None, None

    columns = tuple(description[0] for description in cursor.description)
    rows = cursor.fetchall()

    normalized_rows = Counter(normalize_value(row) for row in rows)
    return columns, normalized_rows


def format_rows(rows):
    """Format a normalized row Counter as readable row/count pairs."""
    if rows is None:
        return "<no result set>"

    if not rows:
        return "<no rows>"

    ordered_rows = sorted(rows.items(), key=lambda item: repr(item[0]))
    return pformat(
        [{"row": row, "count": count} for row, count in ordered_rows],
        width=100,
        sort_dicts=False,
    )


def compare_queries(cursor, user_sql, reference_sql, query_id):
    """
    Execute user and reference queries in separate savepoints.

    Row order is ignored, but duplicate rows are preserved.
    """
    savepoint = f"question_{query_id}"
    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        try:
            user_columns, user_rows = execute_and_capture(cursor, user_sql)
        except Exception as error:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            pytest.fail(
                f"Question {query_id}: Your query raised an error:\n{error}"
            )

        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")

        try:
            reference_columns, reference_rows = execute_and_capture(
                cursor, reference_sql
            )
        except Exception as error:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            pytest.fail(
                f"Question {query_id}: The reference solution raised an "
                f"error:\n{error}"
            )

        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")

        if user_columns is None or reference_columns is None:
            pytest.fail(
                f"Question {query_id}: Both queries must return a result set.\n"
                f"Expected columns (reference): {reference_columns}\n"
                f"Actual columns (your query):  {user_columns}\n\n"
                f"Expected rows:\n{format_rows(reference_rows)}\n\n"
                f"Actual rows:\n{format_rows(user_rows)}"
            )

        if user_columns != reference_columns:
            pytest.fail(
                f"Question {query_id}: Column names do not match.\n"
                f"Expected columns (reference): {reference_columns}\n"
                f"Actual columns (your query):  {user_columns}\n\n"
                f"Expected rows:\n{format_rows(reference_rows)}\n\n"
                f"Actual rows:\n{format_rows(user_rows)}"
            )

        if user_rows != reference_rows:
            pytest.fail(
                f"Question {query_id}: Result rows do not match.\n"
                f"Expected columns: {reference_columns}\n"
                f"Actual columns:   {user_columns}\n\n"
                f"Expected rows (reference):\n{format_rows(reference_rows)}\n\n"
                f"Actual rows (your query):\n{format_rows(user_rows)}"
            )

    finally:
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")


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
    Execute a materialized-view definition in isolation, then read
    the actual contents of daily_exam_metrics.
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

        columns = tuple(description[0] for description in cursor.description)
        rows = Counter(
            normalize_value(row) for row in cursor.fetchall()
        )
        return columns, rows

    except Exception as error:
        pytest.fail(
            f"Question 29: {label} materialized view failed:\n{error}"
        )

    finally:
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")


def capture_expected_daily_metrics(cursor):
    """
    Independently calculate expected daily metrics from exams.
    This prevents Q29 passing merely because both view definitions
    contain the same mistake.
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

    columns = tuple(description[0] for description in cursor.description)
    rows = Counter(normalize_value(row) for row in cursor.fetchall())
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
        if re.match(r"^\s*EXPLAIN\b", statement, flags=re.IGNORECASE)
    ]


def remove_explain_prefix(statement):
    """
    Remove EXPLAIN ANALYZE so the underlying SELECT can be executed.

    Supports EXPLAIN ANALYZE SELECT ... and
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

    if not re.match(r"^(SELECT|WITH)\b", query, flags=re.IGNORECASE):
        raise ValueError(
            "Question 30 should use SELECT queries inside EXPLAIN ANALYZE."
        )

    return query


def extract_plan_metrics(plan_text):
    """
    Extract planning time, execution time, estimated total cost,
    and root actual time from EXPLAIN ANALYZE output.
    """
    execution_match = re.search(
        r"Execution Time:\s*([\d.]+)\s*ms",
        plan_text,
        flags=re.IGNORECASE,
    )
    planning_match = re.search(
        r"Planning Time:\s*([\d.]+)\s*ms",
        plan_text,
        flags=re.IGNORECASE,
    )
    cost_match = re.search(
        r"cost=[\d.]+\.\.([\d.]+)",
        plan_text,
        flags=re.IGNORECASE,
    )
    actual_match = re.search(
        r"actual time=[\d.]+\.\.([\d.]+)",
        plan_text,
        flags=re.IGNORECASE,
    )

    if not execution_match or not planning_match:
        raise ValueError(
            "The EXPLAIN ANALYZE output is missing planning or execution time."
        )

    if not actual_match:
        raise ValueError(
            "The EXPLAIN ANALYZE output does not contain actual execution details."
        )

    return {
        "execution_time_ms": float(execution_match.group(1)),
        "planning_time_ms": float(planning_match.group(1)),
        "estimated_total_cost": (
            float(cost_match.group(1)) if cost_match else None
        ),
        "root_actual_time_ms": float(actual_match.group(1)),
    }


def execute_and_capture_plan(cursor, explain_statement, label):
    """
    Execute one EXPLAIN ANALYZE statement and capture its plan,
    metrics, and the underlying SELECT result, inside a savepoint.
    """
    savepoint = f"q30_{label}"
    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        cursor.execute(explain_statement)
        plan_rows = cursor.fetchall()
        plan_text = "\n".join(str(row[0]) for row in plan_rows)

        if not plan_text.strip():
            raise ValueError(
                "EXPLAIN ANALYZE returned an empty execution plan."
            )

        metrics = extract_plan_metrics(plan_text)
        underlying_query = remove_explain_prefix(explain_statement)
        columns, rows = execute_and_capture(cursor, underlying_query)

        if columns is None:
            raise ValueError(
                "The underlying Q30 query did not return a result set."
            )

        return {
            "plan": plan_text,
            "metrics": metrics,
            "columns": columns,
            "rows": rows,
        }

    except Exception as error:
        pytest.fail(
            f"Question 30: {label} execution plan failed:\n{error}"
        )

    finally:
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")


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
    [WORKSPACE_FILE, SOLUTION_FILE],
)
def test_question_marker_integrity(filepath):
    """
    Verify that each SQL file contains exactly one marker
    for every question from 1 through 30.
    """
    marker_ids = extract_question_markers(filepath)
    marker_counts = Counter(marker_ids)

    duplicates = sorted(
        question_id
        for question_id, count in marker_counts.items()
        if count > 1
    )
    actual_ids = set(marker_ids)
    missing = sorted(EXPECTED_QUESTION_IDS - actual_ids)
    unexpected = sorted(actual_ids - EXPECTED_QUESTION_IDS)

    assert not duplicates, (
        f"{filepath}: Duplicate question markers: {duplicates}"
    )
    assert not missing, f"{filepath}: Missing question markers: {missing}"
    assert not unexpected, (
        f"{filepath}: Unexpected question markers: {unexpected}"
    )
    assert len(marker_ids) == 30, (
        f"{filepath}: Expected exactly 30 markers, found {len(marker_ids)}."
    )


# =========================================================
# Database Connection Test
# =========================================================

def test_sandbox_connection(db_cursor):
    """Verify that the database and seed data are available."""
    db_cursor.execute("SELECT COUNT(*) FROM students")
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
    [
        pytest.param(
            query_id,
            id=f"query_{query_id}",
            marks=pytest.mark.question(query_id),
        )
        for query_id in COMPARABLE_QUERY_IDS
    ],
)
def test_query_match_solution(db_cursor, query_files, query_id):
    user_queries, reference_queries = query_files

    assert query_id in user_queries, (
        f"Question {query_id}: No SQL answer found in {WORKSPACE_FILE}. "
        "The challenge description alone is not an answer."
    )
    assert query_id in reference_queries, (
        f"Question {query_id}: No reference answer found in {SOLUTION_FILE}."
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

@pytest.mark.question(29)
def test_query_29_materialized_view_contents(db_cursor, query_files):
    user_queries, reference_queries = query_files

    assert 29 in user_queries, (
        f"Question 29: Add your materialized-view solution to {WORKSPACE_FILE}."
    )
    assert 29 in reference_queries, (
        "Question 29: Reference solution is missing."
    )

    user_columns, user_rows = capture_materialized_view(
        db_cursor, user_queries[29], "user"
    )
    reference_columns, reference_rows = capture_materialized_view(
        db_cursor, reference_queries[29], "reference"
    )
    expected_columns, expected_rows = capture_expected_daily_metrics(db_cursor)

    assert expected_columns == EXPECTED_METRIC_COLUMNS, (
        "Question 29: The independent metric query returned unexpected columns. "
        f"Expected: {EXPECTED_METRIC_COLUMNS}; actual: {expected_columns}"
    )
    assert user_columns == EXPECTED_METRIC_COLUMNS, (
        "Question 29: Your materialized view has incorrect columns.\n"
        f"Expected: {EXPECTED_METRIC_COLUMNS}\n"
        f"Actual:   {user_columns}"
    )
    assert reference_columns == EXPECTED_METRIC_COLUMNS, (
        "Question 29: The reference materialized view has incorrect columns."
    )
    assert user_columns == reference_columns, (
        "Question 29: Your materialized-view columns do not match the reference."
    )
    assert user_rows == expected_rows, (
        "Question 29: Your materialized view contains incorrect data.\n"
        f"Expected rows:\n{format_rows(expected_rows)}\n\n"
        f"Actual rows:\n{format_rows(user_rows)}"
    )
    assert reference_rows == expected_rows, (
        "Question 29: The reference materialized view does not match "
        "the independently calculated daily metrics."
    )


# =========================================================
# Q30: Execute and Compare Both EXPLAIN ANALYZE Plans
# =========================================================

@pytest.mark.question(30)
def test_query_30_explain_analyze_plans(db_cursor, query_files):
    user_queries, reference_queries = query_files

    assert 30 in user_queries, (
        f"Question 30: Add both EXPLAIN ANALYZE queries to {WORKSPACE_FILE}."
    )
    assert 30 in reference_queries, (
        "Question 30: Reference solution is missing."
    )

    user_statements = extract_explain_statements(user_queries[30])
    reference_statements = extract_explain_statements(reference_queries[30])

    assert len(user_statements) == 2, (
        "Question 30: Your answer must contain exactly two EXPLAIN ANALYZE "
        f"statements: one for each approach. Found {len(user_statements)}."
    )
    assert len(reference_statements) == 2, (
        "Question 30: The reference must contain exactly two "
        "EXPLAIN ANALYZE statements."
    )

    user_plans = [
        execute_and_capture_plan(
            db_cursor, statement, f"user_plan_{index + 1}"
        )
        for index, statement in enumerate(user_statements)
    ]
    reference_plans = [
        execute_and_capture_plan(
            db_cursor, statement, f"reference_plan_{index + 1}"
        )
        for index, statement in enumerate(reference_statements)
    ]

    # Both user queries must return equivalent results.
    first_plan, second_plan = user_plans
    assert first_plan["columns"] == second_plan["columns"], (
        "Question 30: The two approaches return different column names.\n"
        f"First:  {first_plan['columns']}\n"
        f"Second: {second_plan['columns']}"
    )
    assert first_plan["rows"] == second_plan["rows"], (
        "Question 30: The correlated and optimized queries do not "
        "return equivalent results.\n"
        f"First query columns:  {first_plan['columns']}\n"
        f"Second query columns: {second_plan['columns']}\n\n"
        f"First query rows:\n{format_rows(first_plan['rows'])}\n\n"
        f"Second query rows:\n{format_rows(second_plan['rows'])}"
    )

    # Both reference queries must also be equivalent.
    reference_first, reference_second = reference_plans
    assert reference_first["columns"] == reference_second["columns"], (
        "Question 30: The two reference approaches return different columns."
    )
    assert reference_first["rows"] == reference_second["rows"], (
        "Question 30: The two reference approaches do not return equivalent "
        "results.\n"
        f"First reference rows:\n{format_rows(reference_first['rows'])}\n\n"
        f"Second reference rows:\n{format_rows(reference_second['rows'])}"
    )

    # Compare user results with reference results.
    assert first_plan["columns"] == reference_first["columns"], (
        "Question 30: Your query columns do not match the reference."
    )
    assert first_plan["rows"] == reference_first["rows"], (
        "Question 30: Your query results do not match the reference.\n"
        f"Expected columns (reference): {reference_first['columns']}\n"
        f"Actual columns (your query):  {first_plan['columns']}\n\n"
        f"Expected rows (reference):\n{format_rows(reference_first['rows'])}\n\n"
        f"Actual rows (your query):\n{format_rows(first_plan['rows'])}"
    )

    # Display plan metrics for manual performance review.
    print("\nQuestion 30 — EXPLAIN ANALYZE comparison")

    for index, result in enumerate(user_plans, start=1):
        metrics = result["metrics"]
        print(f"\nYour plan {index}:")
        print(f"  Planning time:       {metrics['planning_time_ms']} ms")
        print(f"  Execution time:      {metrics['execution_time_ms']} ms")
        print(f"  Estimated total cost: {metrics['estimated_total_cost']}")
        print(f"  Root actual time:    {metrics['root_actual_time_ms']} ms")

    # Do not assert that the second query must be faster. Execution times
    # and planner costs depend on data size, indexes, caching, and hardware.


# =========================================================
# Exact pytest selection and command-line interface
# =========================================================

def pytest_configure(config):
    """Register the marker used to identify individual questions."""
    config.addinivalue_line(
        "markers",
        "question(question_id): identifies the SQL question being tested",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """
    Make a simple '-k query_N' expression select exactly question N.

    Pytest normally uses substring matching, so '-k query_1' also matches
    query_10 through query_19. This hook narrows simple query_N expressions
    before pytest's normal keyword filtering. Other -k expressions retain
    pytest's standard behavior.
    """
    keyword_expression = (config.option.keyword or "").strip()
    match = re.fullmatch(
        r"query_(\d+)",
        keyword_expression,
        flags=re.IGNORECASE,
    )

    if not match:
        return

    requested_id = int(match.group(1))
    selected = []
    deselected = []

    for item in items:
        marker = item.get_closest_marker("question")
        question_id = marker.args[0] if marker and marker.args else None

        if question_id == requested_id:
            selected.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)

    items[:] = selected


def question_node_id(question_id):
    """Return the exact pytest node ID for a question."""
    if question_id in COMPARABLE_QUERY_IDS:
        return (
            f"{os.path.abspath(__file__)}::"
            f"test_query_match_solution[query_{question_id}]"
        )

    if question_id == 29:
        return (
            f"{os.path.abspath(__file__)}::"
            "test_query_29_materialized_view_contents"
        )

    if question_id == 30:
        return (
            f"{os.path.abspath(__file__)}::"
            "test_query_30_explain_analyze_plans"
        )

    raise ValueError(f"Unsupported question number: {question_id}")


def main(argv=None):
    """Run the full test suite or one selected question."""
    parser = argparse.ArgumentParser(
        description="Run SQL challenge tests for Hogwarts SQL Sandbox."
    )
    selection = parser.add_mutually_exclusive_group()

    selection.add_argument(
        "--question",
        type=int,
        choices=range(1, 31),
        metavar="N",
        help="run only question N (1-30)",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="run the complete test suite",
    )

    args = parser.parse_args(argv)
    pytest_args = ["-v"]

    if args.question is not None:
        pytest_args.append(question_node_id(args.question))
    else:
        # --all, or no CLI option, runs the complete suite.
        pytest_args.append(os.path.abspath(__file__))

    return int(pytest.main(pytest_args))


if __name__ == "__main__":
    raise SystemExit(main())

    # The test deliberately does not assert that the second
    # query must be faster. Execution times and planner costs
    # depend on database size, indexes, caching and hardware.
