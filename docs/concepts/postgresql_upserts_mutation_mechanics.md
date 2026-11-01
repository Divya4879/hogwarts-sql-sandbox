# PostgreSQL Upserts & Mutation Mechanics

## 1. The Engineering Problem: Handling Duplicate Records and Retakes

In a relational database, **unique constraints** prevent duplicate records from being inserted.

Consider an `exams` table where a student should have only one exam record per course on a particular date. A unique constraint might be defined on:

```sql
UNIQUE (student_id, course_id, exam_date)
```

Now imagine two scenarios:

- A student retakes an exam, and the system needs to update the existing record.
- A data ingestion pipeline processes the same batch more than once, attempting to insert records that already exist.

A normal `INSERT` will fail when a row violates the unique constraint:

```sql
INSERT INTO exams (
    student_id,
    course_id,
    exam_date,
    grade_result
)
VALUES (1, 3, '2004-05-26', 'ee');
```

If that combination of `student_id`, `course_id`, and `exam_date` already exists, PostgreSQL raises a unique constraint violation.

One solution is to check whether the record exists and then decide whether to run an `INSERT` or an `UPDATE`. However, this requires additional queries and can introduce race conditions when multiple transactions attempt the same operation concurrently.

PostgreSQL provides a more efficient solution: **UPSERT**.

An upsert combines:

- `INSERT`: Create a new record if it does not exist.
- `UPDATE`: Modify the existing record if a specified uniqueness conflict occurs.

---

## 2. Core Concepts & Mechanics

### A. The `ON CONFLICT` Clause

`ON CONFLICT` specifies what PostgreSQL should do when an attempted insertion violates a unique constraint or unique index.

It supports two main actions:

**1. `DO NOTHING`**

Ignore the conflicting insertion.

```sql
INSERT INTO exams (
    student_id,
    course_id,
    exam_date,
    grade_result
)
VALUES (1, 3, '2004-05-26', 'ee')
ON CONFLICT (student_id, course_id, exam_date)
DO NOTHING;
```

If the record already exists, PostgreSQL skips the insertion instead of raising a duplicate-key error.

**2. `DO UPDATE`**

Update the existing record when a conflict occurs.

```sql
INSERT INTO exams (
    student_id,
    course_id,
    exam_date,
    grade_result
)
VALUES (1, 3, '2004-05-26', 'ee')
ON CONFLICT (student_id, course_id, exam_date)
DO UPDATE
SET grade_result = EXCLUDED.grade_result;
```

If the specified combination already exists, PostgreSQL updates its grade instead of inserting another record.

**Important:** The conflict target must correspond to an appropriate unique constraint or unique index. PostgreSQL cannot use `ON CONFLICT` to handle arbitrary conflicts, such as a foreign-key violation.

### B. The `EXCLUDED` Pseudo-Table

When PostgreSQL encounters a conflict, it needs to distinguish between:

- The existing row already stored in the table.
- The incoming row that was proposed for insertion.

`EXCLUDED` represents the incoming row that could not be inserted because of the conflict.

For example:

```sql
ON CONFLICT (student_id, course_id, exam_date)
DO UPDATE
SET grade_result = EXCLUDED.grade_result;
```

Here:

- `grade_result` refers to the existing row's column.
- `EXCLUDED.grade_result` refers to the incoming row's grade.

This allows PostgreSQL to update existing records using values from the attempted insertion.

### C. The `RETURNING` Clause

Normally, an application might need another `SELECT` query to retrieve a row after inserting or updating it.

PostgreSQL's `RETURNING` clause returns values from rows affected by a data modification statement.

```sql
INSERT INTO exams (...)
VALUES (...)
ON CONFLICT (...)
DO UPDATE
SET grade_result = EXCLUDED.grade_result
RETURNING student_id, course_id, exam_date, grade_result;
```

It returns the resulting rows from successful insertions and updates.

**Important:** Rows skipped by `DO NOTHING`, or rows excluded by a `DO UPDATE ... WHERE` condition, are not returned.

This is particularly useful in backend APIs because the application can retrieve the modified record without issuing a separate query.

### D. Conditional Updates with `WHERE`

An upsert does not have to update every conflicting row.

A `WHERE` condition can restrict when the update should happen.

For example, suppose a student is retaking an exam. We only want to replace the existing grade if the previous grade was a failure.

```sql
ON CONFLICT (student_id, course_id, exam_date)
DO UPDATE
SET grade_result = EXCLUDED.grade_result
WHERE exams.grade_result IN ('p', 'troll');
```

Here, `exams.grade_result` refers to the existing stored grade.

If the existing grade is not a failure, PostgreSQL does not update that row.

This prevents an incoming retake record from unnecessarily overwriting a non-failing grade.

---

## 3. Query 27: The Upsert Simulation

**Challenge:** Simulate students retaking failed exams. Insert the new exam records, update existing records when a uniqueness conflict occurs, and return the resulting records.

```sql
INSERT INTO exams (
    student_id,
    course_id,
    exam_date,
    grade_result
)
VALUES
    (1, 3, '2004-05-26', 'ee'),
    (1, 6, '2004-05-29', 'a'),
    (1, 8, '2004-05-31', 'o+')

ON CONFLICT (student_id, course_id, exam_date)

DO UPDATE
SET grade_result = EXCLUDED.grade_result
WHERE exams.grade_result IN ('p', 'troll')

RETURNING
    student_id,
    course_id,
    exam_date,
    grade_result;
```

### Query Breakdown

**Step 1: Attempt the insertion**

```sql
INSERT INTO exams (...)
VALUES (...), (...), (...);
```

PostgreSQL attempts to insert all three proposed records.

**Step 2: Identify uniqueness conflicts**

```sql
ON CONFLICT (student_id, course_id, exam_date)
```

PostgreSQL checks whether an existing record has the same combination of these three columns.

**Step 3: Update the existing record**

```sql
DO UPDATE
SET grade_result = EXCLUDED.grade_result
```

If a conflict occurs, the existing record's grade is replaced with the incoming grade.

**Step 4: Protect non-failing grades**

```sql
WHERE exams.grade_result IN ('p', 'troll')
```

The update happens only if the existing grade is `p` or `troll`.

**Step 5: Return the affected records**

```sql
RETURNING
    student_id,
    course_id,
    exam_date,
    grade_result;
```

The query returns successfully inserted or updated records.

Note: The sample values are illustrative. Whether each row is inserted or updated depends on the existing data and the unique constraint.

---

## 4. Important PostgreSQL Behaviours

### A. Atomicity and Concurrency

An `INSERT ... ON CONFLICT DO UPDATE` statement provides an atomic insert-or-update outcome.

This means PostgreSQL handles the conflict as part of the same database statement rather than requiring the application to perform a separate existence check followed by an update.

It is particularly useful when multiple transactions attempt to insert the same unique key concurrently.

### B. Idempotency

An operation is idempotent when repeating it produces the same intended final state as executing it once.

Upserts can help build idempotent data-ingestion workflows.

For example, processing the same incoming record repeatedly can leave the stored grade unchanged after the first successful update.

However, an upsert is not automatically idempotent in every situation. Triggers, timestamps, counters, or other update-side effects can change the outcome of repeated executions.

### C. Batch Upserts

PostgreSQL allows multiple rows to be inserted or upserted in one statement.

This reduces the number of database round-trips when processing batches.

One important restriction: a single `INSERT ... ON CONFLICT DO UPDATE` statement cannot affect the same existing row more than once. If the input batch contains duplicate values for the conflict key, PostgreSQL can raise a cardinality violation.

Therefore, deduplicate incoming records when necessary.

### D. `RETURNING` Is Not a Separate `SELECT`

`RETURNING` retrieves the resulting values directly from the data-modification statement.

It works with:

- `INSERT`
- `UPDATE`
- `DELETE`
- `MERGE` (supported in PostgreSQL 15 and later)

---

## 5. Production Applications

Upserts are useful in several real-world scenarios:

1. **Data ingestion:** Reprocessing incoming records without repeatedly failing on duplicate keys.
2. **Webhook handling:** Processing repeated webhook events while maintaining the intended database state.
3. **Backend APIs:** Creating a record if it does not exist, or updating it if it already exists.
4. **Synchronization:** Keeping local database records aligned with incoming data from external systems.
5. **Batch processing:** Inserting or updating multiple records in a single database operation.

---

## 6. Key Takeaways

| Concept | Purpose |
|---|---|
| `INSERT` | Adds new records |
| `ON CONFLICT` | Defines what happens when a uniqueness conflict occurs |
| `DO NOTHING` | Skips the conflicting insertion |
| `DO UPDATE` | Updates the existing record |
| `EXCLUDED` | References the incoming proposed row |
| `WHERE` | Restricts when a conflicting row is updated |
| `RETURNING` | Returns rows affected by the operation |

**Remember:**

- An upsert is an `INSERT` with conflict-handling logic.
- `ON CONFLICT` requires a suitable unique constraint or index.
- `EXCLUDED` refers to the incoming row, not the existing stored row.
- `DO UPDATE ... WHERE` allows conditional updates.
- `RETURNING` retrieves affected rows without a separate `SELECT`.
- Upserts help with atomicity and idempotent workflows, but do not automatically guarantee that every application-level operation is idempotent.