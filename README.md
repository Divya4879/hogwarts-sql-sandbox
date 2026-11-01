# Hogwarts SQL Sandbox

A PostgreSQL practice repository built around a fictional Hogwarts database. It contains 30 SQL challenges, reference solutions, a Python-based test runner, and notes on selected PostgreSQL concepts.

The exercises progress from basic queries and aggregations to window functions, CTEs, JSONB, arrays, recursive queries, materialized views, and query analysis.

**Repository:** [Divya4879/hogwarts-sql-sandbox](https://github.com/Divya4879/hogwarts-sql-sandbox)

## Repository Structure

| Path | Description |
|---|---|
| [`init/`](init/) | Database schema and seed data |
| [`workspace/03_challenges.sql`](workspace/03_challenges.sql) | 30 SQL challenge prompts and workspace for answers |
| [`solutions/04_solutions.sql`](solutions/04_solutions.sql) | Reference solutions |
| [`test_runner.py`](test_runner.py) | Pytest-based SQL validation |
| [`docs/concepts/`](docs/concepts/) | Notes on selected PostgreSQL concepts |
| [`docker-compose.yml`](docker-compose.yml) | PostgreSQL container configuration |
| [`requirements.txt`](requirements.txt) | Python dependencies |

## Database

The sandbox uses **PostgreSQL 15** and a relational dataset containing four tables:

- `houses` — Hogwarts houses and their heads.
- `students` — student details, year, and house.
- `courses` — courses and professors.
- `exams` — exam dates, students, courses, and grades.

The schema defines primary keys, foreign keys, uniqueness constraints, and grade/year checks. The seed script inserts the sample records used by the exercises.

## Getting Started

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-started/get-docker/) or Docker Engine with the Docker Compose plugin.
- [Python 3](https://www.python.org/downloads/).
- Git.

### 1. Clone the repository

```bash
git clone https://github.com/Divya4879/hogwarts-sql-sandbox.git
cd hogwarts-sql-sandbox
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

This starts the `postgres-sandbox` service using the `postgres:15-alpine` image.

The database uses the following local development credentials:

| Setting | Value |
|---|---|
| Database | `hogwarts` |
| User | `wizard` |
| Password | `password` |
| Host | `localhost` |
| Port | `5432` |

On the first startup with an empty PostgreSQL data directory, the SQL files in `init/` are executed in alphabetical order:

1. `01_schema.sql`
2. `02_seed.sql`

Check that PostgreSQL is ready:

```bash
docker compose exec postgres-sandbox pg_isready -U wizard -d hogwarts
```

### 3. Install Python dependencies

Create and activate a virtual environment.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

### 4. Run the tests

```bash
pytest -v
```

The test runner connects to the local PostgreSQL database and validates the SQL queries.

By default, it uses the database settings listed above. You can override them with these environment variables:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Working on the Challenges

Open [`workspace/03_challenges.sql`](workspace/03_challenges.sql) and write your answers below the corresponding question markers.

Keep the marker format intact:

```sql
-- QUESTION 1: Description of the challenge

SELECT ...;
```

The test runner uses these markers to identify and compare individual answers.

### Running Specific Tests

Run the full test suite:

```bash
pytest -v
```

Run a specific question, for example Question 25:

```bash
pytest -v -k query_25
```

Run Question 29:

```bash
pytest -v -k query_29
```

Run Question 30 with its execution-plan output:

```bash
pytest -v -s -k query_30
```

### What the Tests Check

- **Q1–Q28:** Compare query column names and result rows against the corresponding reference solutions. Row order is ignored, but duplicate rows are considered.
- **Q29:** Execute the materialized-view definition and validate its columns and contents against independently calculated daily metrics.
- **Q30:** Execute both `EXPLAIN ANALYZE` queries, compare their results, and display planning and execution metrics. The test does not assume that one query must always be faster.

The test suite also checks that both SQL files contain exactly one marker for each question from 1 to 30.

**Note:** The workspace contains the challenge descriptions. Add your SQL answers before expecting the query tests to pass.

## PostgreSQL Concept Notes

The [`docs/concepts/`](docs/concepts/) directory contains focused notes on selected topics:

1. [Hierarchical Rollups and Statistical Volatility](docs/concepts/hierarchical_rollups_and_statistical_volatility.md)
2. [Moving Averages and Window Framing](docs/concepts/moving_averages_window_framing.md)
3. [Nested JSONB](docs/concepts/nested_jsonb_architectural_guide.md)
4. [PostgreSQL Native Arrays](docs/concepts/postgresql_native_arrays_array_operations.md)
5. [PostgreSQL Upserts](docs/concepts/postgresql_upserts_mutation_mechanics.md)
6. [EXPLAIN ANALYZE](docs/concepts/query_explain_analyze.md)
7. [Recursive CTEs and State Tracking](docs/concepts/recursive_ctes_state_tracking.md)
8. [Time-Series Gap Analysis](docs/concepts/time_series_gap_analysis.md)

## Stopping and Resetting the Database

Stop the running container without removing it:

```bash
docker compose stop
```

Start it again:

```bash
docker compose start
```

To remove the container and its associated volumes and recreate the database from the initialization scripts:

```bash
docker compose down -v
docker compose up -d
```

**Warning:** The reset command deletes the PostgreSQL data stored in the container's volumes. Use it only when you want a fresh database.

---

## Tech Stack

- **Database:** PostgreSQL 15
- **Containerization:** Docker Compose
- **Languages:** SQL, Python
- **Testing:** pytest, psycopg2