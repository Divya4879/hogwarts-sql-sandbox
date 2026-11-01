
import os
import re
from collections import Counter

import psycopg2
import pytest


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "hogwarts"),
    "user": os.getenv("DB_USER", "wizard"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

SOLUTION_FILE = "solutions/04_solutions.sql"
WORKSPACE_FILE = "workspace/03_challenges.sql"

# Query 30 compares EXPLAIN ANALYZE plans, not ordinary
# result sets. It needs a separate performance-oriented check.
COMPARABLE_QUERY_IDS = range(1, 30)

# Only this exact heading format identifies a question:
# -- QUESTION 18: Relational Division
#
# Numbered comments inside explanations, such as:
# -- 1. Generate unique pairs of students.
# are deliberately not recognized.
QUESTION_MARKER_PATTERN = re.compile(
    r"(?m)^\s*--\s*QUESTION\s+(\d+)\s*:\s*.*$",
    flags=re.IGNORECASE,
)


# ---------------------------------------------------------
# SQL file parsing
# ---------------------------------------------------------

def remove_comments(sql):
    """Remove SQL line comments and block comments."""
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql.strip()


def load_numbered_queries(filepath):
    """
    Extract SQL query blocks using unambiguous question markers.

    Expected format:
        -- QUESTION 1: Description
        SELECT ...

        -- QUESTION 2: Description
        SELECT ...

    Only lines matching QUESTION_MARKER_PATTERN are treated
    as question headings.

    Returns:
        {1: "SELECT ...", 2: "SELECT ...", ...}
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

        start = marker.end()
        end = (
            markers[index + 1].start()
            if index + 1 < len(markers)
            else len(content)
        )

        query_sql = remove_comments(content[start:end])

        if query_id in queries:
            raise ValueError(
                f"Duplicate question marker: {query_id} "
                f"in {filepath}"
            )

        # Ignore question headings that contain no SQL answer.
        if query_sql:
            queries[query_id] = query_sql

    return queries


# ---------------------------------------------------------
# Database fixture
# ---------------------------------------------------------

@pytest.fixture(scope="module")
def db_cursor():
    """Connect to PostgreSQL and provide a cursor for the tests."""
    connection = psycopg2.connect(**DB_CONFIG)
    connection.autocommit = False

    cursor = connection.cursor()

    yield cursor

    connection.rollback()
    cursor.close()
    connection.close()


# ---------------------------------------------------------
# Query execution and result comparison
# ---------------------------------------------------------

def normalize_value(value):
    """
    Convert values into comparable structures.
    This also handles JSON/dictionary results.
    """
    if isinstance(value, dict):
        return tuple(
            sorted(
                (key, normalize_value(val))
                for key, val in value.items()
            )
        )

    if isinstance(value, list):
        return tuple(normalize_value(item) for item in value)

    if isinstance(value, tuple):
        return tuple(normalize_value(item) for item in value)

    return value


def execute_and_capture(cursor, sql):
    """Execute SQL and capture its column names and result rows."""
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
    Execute both queries in isolated savepoints.
    Roll back each execution to avoid persistent data changes.
    """

    savepoint = f"question_{query_id}"
    cursor.execute(f"SAVEPOINT {savepoint}")

    try:
        try:
            user_columns, user_rows = execute_and_capture(
                cursor, user_sql
            )
        except Exception as error:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            pytest.fail(
                f"Question {query_id}: Your query raised an error:\n"
                f"{error}"
            )

        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")

        try:
            reference_columns, reference_rows = execute_and_capture(
                cursor, reference_sql
            )
        except Exception as error:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            pytest.fail(
                f"Question {query_id}: The reference solution "
                f"raised an error:\n{error}"
            )

        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")

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
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")


# ---------------------------------------------------------
# Load both SQL files once
# ---------------------------------------------------------

@pytest.fixture(scope="module")
def query_files():
    user_queries = load_numbered_queries(WORKSPACE_FILE)
    reference_queries = load_numbered_queries(SOLUTION_FILE)

    return user_queries, reference_queries


# ---------------------------------------------------------
# Database connection test
# ---------------------------------------------------------

def test_sandbox_connection(db_cursor):
    db_cursor.execute("SELECT COUNT(*) FROM students")
    student_count = db_cursor.fetchone()[0]

    assert student_count > 0, (
        "The database has no students. "
        "Check whether the seed script has run."
    )


# ---------------------------------------------------------
# Compare each answer against the reference
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query_id",
    COMPARABLE_QUERY_IDS
)
def test_query_match_solution(db_cursor, query_files, query_id):
    user_queries, reference_queries = query_files

    assert query_id in user_queries, (
        f"Question {query_id}: No SQL answer found in "
        f"{WORKSPACE_FILE}"
    )

    assert query_id in reference_queries, (
        f"Question {query_id}: No reference answer found in "
        f"{SOLUTION_FILE}"
    )

    compare_queries(
        cursor=db_cursor,
        user_sql=user_queries[query_id],
        reference_sql=reference_queries[query_id],
        query_id=query_id,
    )


# ---------------------------------------------------------
# Query 30 requires a separate manual performance review
# ---------------------------------------------------------

def test_query_30_has_two_explain_analyze_statements(query_files):
    user_queries, reference_queries = query_files

    assert 30 in user_queries, (
        "Question 30: Add your answer to the workspace first."
    )

    assert 30 in reference_queries, (
        "Question 30: Reference solution is missing."
    )

    user_count = len(
        re.findall(
            r"\bEXPLAIN\s+ANALYZE\b",
            user_queries[30],
            flags=re.IGNORECASE
        )
    )

    reference_count = len(
        re.findall(
            r"\bEXPLAIN\s+ANALYZE\b",
            reference_queries[30],
            flags=re.IGNORECASE
        )
    )

    assert user_count >= 2, (
        "Question 30: Include EXPLAIN ANALYZE for both "
        "the correlated and optimized queries."
    )

    assert reference_count >= 2, (
        "Question 30: The reference must contain both plans."
    )
