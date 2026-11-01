# Query Optimization & `EXPLAIN ANALYZE`

## 1. The Engineering Problem: Understanding Query Performance

As database tables grow from hundreds of rows to millions of records, inefficient SQL queries can increase execution time, CPU utilization, memory consumption, and database load.

Query optimization is not simply about rewriting SQL until it looks cleaner. It is about understanding how PostgreSQL plans and executes a query, identifying expensive operations, and measuring whether a change actually improves performance.

PostgreSQL uses a **query planner and optimizer** to determine an execution strategy based on factors such as:

- Table sizes and available statistics.
- Available indexes.
- Join conditions and filter selectivity.
- Estimated number of rows.
- Estimated execution costs.

The `EXPLAIN` and `EXPLAIN ANALYZE` commands help us inspect these decisions.

---

## 2. `EXPLAIN` vs. `EXPLAIN ANALYZE`

These commands serve different purposes.

### A. `EXPLAIN`

`EXPLAIN` displays the execution plan PostgreSQL intends to use without executing the query.

```sql
EXPLAIN
SELECT *
FROM exams
WHERE student_id = 1;
```

It provides information about the planned operations, estimated costs, and estimated row counts.

Use it when you want to inspect the optimizer's proposed execution strategy without running the query.

### B. `EXPLAIN ANALYZE`

`EXPLAIN ANALYZE` executes the query and then displays the execution plan with actual runtime measurements.

```sql
EXPLAIN ANALYZE
SELECT *
FROM exams
WHERE student_id = 1;
```

It allows you to compare the planner's estimates with what actually happened during execution.

**Important:** `EXPLAIN ANALYZE` really executes the statement. For a `SELECT`, this means the query is run. For an `INSERT`, `UPDATE`, or `DELETE`, the database modification is performed.

### C. Useful Options

You can combine additional options to obtain more execution details.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT *
FROM exams
WHERE student_id = 1;
```

| Option | Purpose |
|---|---|
| `ANALYZE` | Executes the query and reports actual measurements |
| `BUFFERS` | Reports buffer activity, including shared buffer hits and reads |
| `VERBOSE` | Displays additional details about plan nodes |
| `COSTS` | Displays estimated startup and total costs (enabled by default) |
| `TIMING` | Controls per-node timing information (enabled by default with ANALYZE) |
| `FORMAT` | Controls output format, such as `TEXT`, `JSON`, or `YAML` |

A useful starting point for performance investigations is:

```sql
EXPLAIN (ANALYZE, BUFFERS)
-- Your SELECT query
;
```

---

## 3. Understanding the Execution Plan

PostgreSQL displays an execution plan as a tree of operations. Each node represents an operation performed by the database.

### A. Scan Operations

**1. Sequential Scan (`Seq Scan`)**

PostgreSQL reads the table's rows sequentially.

```text
Seq Scan on exams
```

This is not automatically inefficient. A sequential scan can be the best choice when:

- The table is small.
- A query needs a large proportion of the table.
- An index lookup would cost more than scanning the table.

**2. Index Scan**

PostgreSQL uses an index to locate matching rows and retrieves the corresponding table rows.

```text
Index Scan using exams_student_id_idx on exams
```

It can be beneficial when a query retrieves a relatively small subset of a large table.

**3. Index Only Scan**

PostgreSQL can retrieve the required values directly from an index without needing to access the table for every matching row, provided the visibility information allows it.

### B. Join Operations

PostgreSQL can choose different join strategies depending on the data and query.

| Join type | How it works |
|---|---|
| Nested Loop | Iterates through one input and searches the other for matching rows |
| Hash Join | Builds a hash table from one input and probes it using the other |
| Merge Join | Uses sorted inputs to match rows efficiently |

No join strategy is universally fastest. The planner selects one based on estimated costs and available information.

### C. Cost Metrics

An execution plan commonly contains information such as:

```text
(cost=0.00..12.50 rows=10 width=32)
```

- **Startup cost:** Estimated cost before the first row can be returned.
- **Total cost:** Estimated cost to complete the operation.
- **Rows:** Estimated number of rows produced.
- **Width:** Estimated average size of each output row, in bytes.

Cost values are planner estimates expressed in PostgreSQL's internal cost units. They are not milliseconds.

### D. Actual Time and Rows

With `EXPLAIN ANALYZE`, you may see:

```text
(actual time=0.015..0.032 rows=10 loops=1)
```

- **Actual time:** Measured time in milliseconds.
- **Actual rows:** Number of rows produced per loop.
- **Loops:** Number of times the operation was executed.

When comparing estimated and actual row counts, large discrepancies can indicate inaccurate statistics or assumptions made by the planner.

### E. Buffer Information

With the `BUFFERS` option, PostgreSQL reports information about data access.

- **Shared hit:** Required data was already found in shared buffers.
- **Shared read:** Data had to be read into shared buffers.
- **Temp read/write:** Temporary files were read or written, often indicating disk-backed intermediate operations.

Buffer information helps identify I/O activity, but a shared buffer read does not necessarily mean a physical disk read; the operating system may already have cached the data.

### F. Planning Time and Execution Time

At the end of an execution plan, PostgreSQL may report:

```text
Planning Time: 0.120 ms
Execution Time: 0.450 ms
```

- **Planning Time:** Time spent generating the execution plan.
- **Execution Time:** Time spent executing the query, including executor startup and shutdown.

These measurements help evaluate the actual cost of running a query.

---

## 4. Query Optimization: Correlated Subquery vs. Set-Based Aggregation

A common optimization exercise is comparing a correlated subquery with a grouped query.

A **correlated subquery** references a column from the outer query. Its result depends on the current outer row.

Consider calculating the average GPA of every student using the exam records.

### A. Unoptimized Candidate: Correlated Subquery

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    s.student_id,
    s.first_name || ' ' || s.last_name AS student_name,
    (
        SELECT ROUND(
            AVG(
                CASE
                    WHEN e.grade_result = 'o++' THEN 6.0
                    WHEN e.grade_result = 'o+'  THEN 5.0
                    WHEN e.grade_result = 'o'   THEN 4.0
                    WHEN e.grade_result = 'ee'  THEN 3.0
                    WHEN e.grade_result = 'a'   THEN 2.0
                    WHEN e.grade_result = 'p'   THEN 1.0
                    ELSE 0.0
                END
            ),
            2
        )
        FROM exams e
        WHERE e.student_id = s.student_id
    ) AS avg_gpa
FROM students s
WHERE EXISTS (
    SELECT 1
    FROM exams e
    WHERE e.student_id = s.student_id
)
ORDER BY avg_gpa DESC;
```

**What makes it correlated?**

The inner query references:

```sql
WHERE e.student_id = s.student_id
```

The value of `s.student_id` comes from the outer query.

The plan may show a `SubPlan` with multiple loops, indicating repeated execution of the subquery.

However, do not automatically assume that every correlated subquery has quadratic complexity. Its actual performance depends on the execution plan, indexes, table sizes, and the number of rows processed.

### B. Alternative Candidate: Grouped Aggregation and JOIN

We can calculate each student's GPA by grouping the exam records once and then joining the result to the students table.

```sql
EXPLAIN (ANALYZE, BUFFERS)
WITH student_gpa AS (
    SELECT
        student_id,
        ROUND(
            AVG(
                CASE
                    WHEN grade_result = 'o++' THEN 6.0
                    WHEN grade_result = 'o+'  THEN 5.0
                    WHEN grade_result = 'o'   THEN 4.0
                    WHEN grade_result = 'ee'  THEN 3.0
                    WHEN grade_result = 'a'   THEN 2.0
                    WHEN grade_result = 'p'   THEN 1.0
                    ELSE 0.0
                END
            ),
            2
        ) AS avg_gpa
    FROM exams
    GROUP BY student_id
)
SELECT
    s.student_id,
    s.first_name || ' ' || s.last_name AS student_name,
    sg.avg_gpa
FROM students s
JOIN student_gpa sg
    ON s.student_id = sg.student_id
ORDER BY sg.avg_gpa DESC;
```

**Why consider this approach?**

1. Exam records are grouped by student.
2. GPA is calculated for each student.
3. The aggregated result is joined to the students table.
4. The results are sorted by GPA.

This is a set-based approach and may perform better when the correlated subquery requires repeated work.

However, PostgreSQL can optimize correlated subqueries, and a grouped query is not guaranteed to be faster. The actual execution plans must be compared.

**Important:** Both queries calculate GPA only for students who have at least one exam record. This keeps the comparison equivalent.

---

## 5. Benchmarking and Comparing Execution Plans

To compare two query implementations:

**Step 1: Run the first query**

```sql
EXPLAIN (ANALYZE, BUFFERS)
-- Correlated subquery
;
```

**Step 2: Run the alternative query**

```sql
EXPLAIN (ANALYZE, BUFFERS)
-- Grouped aggregation and JOIN
;
```

**Step 3: Inspect the important metrics**

| Metric | What to investigate |
|---|---|
| Execution Time | Which query completed faster? |
| Actual Rows | How many rows were produced? |
| Loops | Were operations executed repeatedly? |
| Estimated vs. Actual Rows | Were planner estimates accurate? |
| Buffer Hits | How much data was already cached? |
| Buffer Reads | How much data had to be loaded into shared buffers? |
| Join Strategy | Which join operation did PostgreSQL select? |
| SubPlan | Did the correlated subquery result in repeated work? |

**Step 4: Record the findings**

Do not conclude that one query is faster based on SQL syntax alone.

Run both queries under comparable conditions and inspect their actual plans.

For more reliable comparisons:

- Use representative data volumes.
- Keep database statistics reasonably up to date.
- Run multiple measurements.
- Account for cache effects.
- Compare equivalent query results.
- Avoid comparing measurements taken under substantially different database loads.

---

## 6. Safe Benchmarking: Understanding Transactions and Rollback

`EXPLAIN ANALYZE` executes the statement being analyzed.

For a `SELECT`, this does not modify table data.

For a data-modification statement, however, the changes are actually performed. You can use a transaction to roll back ordinary transactional database changes after testing:

```sql
BEGIN;

EXPLAIN ANALYZE
UPDATE exams
SET grade_result = 'o'
WHERE student_id = 1;

ROLLBACK;
```

**Important limitations:**

- `ROLLBACK` undoes transactional changes, but does not reverse every possible side effect.
- Sequence values consumed by `nextval()` are not rolled back.
- External side effects performed by triggers or functions may not be reversible.
- Locks and resource usage can still affect other database sessions during execution.

For this reason, use a staging or disposable database for potentially expensive or destructive benchmarks whenever possible.

---

## 7. Indexes and Query Performance

Indexes can improve query performance by helping PostgreSQL locate rows without scanning an entire table.

For example:

```sql
CREATE INDEX idx_exams_student_id
ON exams(student_id);
```

This index may help queries that frequently filter or join on `student_id`.

Other useful considerations:

1. **Filter columns:** Index columns frequently used in selective `WHERE` conditions.
2. **Join columns:** Consider indexes on columns used in joins.
3. **Composite indexes:** Consider multi-column indexes when queries repeatedly filter using the same combination of columns.
4. **Index overhead:** Indexes consume storage and add work to `INSERT`, `UPDATE`, and `DELETE` operations.
5. **Selectivity:** An index may not help when a query needs most of the table's rows.

A foreign-key constraint does not automatically create an index on the referencing column in PostgreSQL.

Do not create indexes blindly. Inspect query patterns and execution plans first.

---

## 8. Database Statistics and `ANALYZE`

PostgreSQL's query planner relies on statistics to estimate the number of rows and select an execution strategy.

If statistics are outdated, the planner may make poor decisions.

The SQL command `ANALYZE` collects statistics about table contents:

```sql
ANALYZE exams;
```

This is different from the `ANALYZE` option in `EXPLAIN ANALYZE`.

| Term | Meaning |
|---|---|
| `ANALYZE exams` | Collects table statistics for the query planner |
| `EXPLAIN ANALYZE SELECT ...` | Executes a query and reports actual execution measurements |

PostgreSQL also runs automatic statistics collection through autovacuum's auto-analyze mechanism.

---

## 9. Production Best Practices

1. **Measure before optimizing:** Use execution plans to identify the actual bottleneck.
2. **Avoid assumptions:** A sequential scan is not always bad, and a join is not always faster than a subquery.
3. **Use indexes selectively:** Indexes can improve reads but introduce storage and write overhead.
4. **Inspect row estimates:** Large differences between estimated and actual rows may indicate inaccurate statistics.
5. **Watch repeated operations:** High loop counts can reveal expensive repeated work.
6. **Monitor buffer activity:** Use `BUFFERS` to understand data access patterns.
7. **Benchmark equivalent queries:** Ensure both versions return the same results before comparing performance.
8. **Test safely:** Run potentially destructive benchmarks in controlled environments.

---

## 10. Key Takeaways

| Concept | Purpose |
|---|---|
| `EXPLAIN` | Displays the planned execution strategy |
| `EXPLAIN ANALYZE` | Executes the query and reports actual measurements |
| `Seq Scan` | Reads table rows sequentially |
| `Index Scan` | Uses an index to locate matching rows |
| `Hash Join` | Uses a hash table to match rows |
| `Nested Loop` | Searches one input for matches for each row of another input |
| `Merge Join` | Matches sorted inputs |
| `SubPlan` | Represents a subquery execution plan |
| `BUFFERS` | Reports buffer access information |
| `ANALYZE` | Collects table statistics |
| `ROLLBACK` | Reverses transactional changes in the current transaction |

**Remember:**

Query optimization is an evidence-driven process.

The goal is not to make SQL look shorter or replace every subquery with a JOIN. The goal is to understand PostgreSQL's execution plan, identify unnecessary work, and verify that the revised query performs better without changing the intended results.