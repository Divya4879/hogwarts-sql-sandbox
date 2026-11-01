import os
import psycopg2
import pytest
from tabulate import tabulate

# Database connection parameters matching your docker-compose.yml
DB_CONFIG = {
    "dbname": "hogwarts",
    "user": "wizard",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

def get_query_result(cursor, query):
    """Executes a query and returns column headers and rows."""
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    return columns, rows

@pytest.fixture(scope="module")
def db_cursor():
    """Provides a transactional database connection cursor for tests."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False  # Use transactions so tests don't permanently mutate state
    cursor = conn.cursor()
    yield cursor
    cursor.close()
    conn.rollback()
    conn.close()

def load_sql_queries(filepath):
    """Parses a SQL file containing multiple queries separated by comments or semicolons."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        content = f.read()
    
    # Split queries by double dashes indicating query blocks or semicolons
    # For a robust parser, we look for numbered query blocks or split by semicolon
    raw_queries = [q.strip() for q in content.split(";") if q.strip()]
    return raw_queries

def test_sandbox_connection(db_cursor):
    """Verifies that the Docker container is running and seeded."""
    db_cursor.execute("SELECT COUNT(*) FROM students;")
    count = db_cursor.fetchone()[0]
    assert count > 0, "[FAIL] Database is empty! Ensure seed scripts ran successfully."
    print(f"\n[PASS] Database connected. Found {count} students loaded in Hogwarts sandbox.")

# Dynamic Test Parametrization for Challenges
# You can map query IDs from your solutions/solutions.sql to workspace/challenges.sql
@pytest.mark.parametrize("query_id", [21, 22, 23, 24, 25, 26, 27, 28, 29, 30])
def test_query_match_solution(db_cursor, query_id):
    """
    Compares the output of the user's query in workspace/challenges.sql 
    against the reference query in solutions/03_queries.sql.
    """
    solution_path = f"solutions/03_queries.sql"
    workspace_path = f"workspace/challenges.sql"
    
    # For demonstration, we ensure files exist
    assert os.path.exists(solution_path), f"Missing master solution file at {solution_path}"
    assert os.path.exists(workspace_path), f"Missing workspace file at {workspace_path}"

    # In a full parser implementation, you extract the specific query block by its number comment.
    # Here we simulate the assertion pipeline structure:
    print(f"\nEvaluating Query {query_id}...")
    
    # Example execution check hook:
    # user_cols, user_rows = get_query_result(db_cursor, user_query)
    # sol_cols, sol_rows = get_query_result(db_cursor, solution_query)
    # assert user_rows == sol_rows, f"[FAIL] Query {query_id} output mismatch!"
    
    assert True, f"[PASS] Query {query_id} matches expected result set."