# Recursive CTEs & Sequential State Tracking

## 1. The Engineering Challenge: Tracking State Over Time

In relational database systems, tables store static records rather than temporal event streams. When you need to track a **running sequence or consecutive streak**—such as tracking consecutive failing grades, financial transaction fraud alerts, or user login streaks—standard aggregate functions often fall short because they lack row-to-row state awareness.

To solve this, database engineers utilize **Recursive Common Table Expressions (CTEs)**. A recursive CTE acts like a programmable loop or state machine inside SQL, allowing rows to reference the results of previous iterations step-by-step.

## 2. Anatomy of a Recursive CTE

A recursive CTE consists of two primary components separated by a `UNION ALL`:

1. **The Anchor Member:** Runs only once at the very beginning. It establishes the baseline starting point or initial state of the loop (e.g., the very first exam a student took, where $rn = 1$).

2. **The Recursive Member:** References the working table (the name of the CTE itself) and joins it against physical tables to step forward to the next logical record (e.g., moving from exam $rn$ to exam $rn + 1$).

## 3. The Sequencing Trap & Solution

Without proper constraints, a recursive join across an entire table can cause a **combinatorial row explosion** or an infinite loop. 

To safely track a sequence chronologically:
* **Step 1 (Pre-Sequencing):** Use a window function like `ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY exam_date ASC)` to assign an explicit integer index ($1, 2, 3, \dots$) to every event per entity.
* **Step 2 (Constrained Step-Forward):** In the recursive member, join the next dataset on an exact ordinal step: `e.rn = rp.rn + 1`. This guarantees the recursion marches forward in a strict, linear timeline.

## 4. Query 28: Complete Implementation & State Machine Logic

Here is the production-grade query implementing recursive academic probation tracking:

```sql
WITH RECURSIVE numbered_exams AS (
    -- Step 1: Assign a chronological row number to every exam taken by each student
    SELECT
        students.student_id,
        first_name || ' ' || last_name AS student_name,
        exam_date,
        grade_result,
        ROW_NUMBER() OVER (PARTITION BY students.student_id ORDER BY exam_date ASC) AS rn
    FROM students
    JOIN exams ON students.student_id = exams.student_id
),
recursive_probation AS (
    -- Step 2: Anchor Member - Evaluate the student's very first exam (rn = 1)
    SELECT
        student_id,
        student_name,
        exam_date,
        grade_result,
        rn,
        CASE WHEN grade_result IN ('p', 'troll') THEN 1 ELSE 0 END AS warning_level
    FROM numbered_exams
    WHERE rn = 1
    
    UNION ALL
    
    -- Step 3: Recursive Member - Step forward one exam at a time (rn + 1)
    SELECT
        e.student_id,
        e.student_name,
        e.exam_date,
        e.grade_result,
        e.rn,
        -- State Machine: Escalate warning level on failure, or reset to 0 on a pass
        CASE 
            WHEN e.grade_result IN ('p', 'troll') THEN rp.warning_level + 1 
            ELSE 0 
        END AS warning_level
    FROM numbered_exams e
    JOIN recursive_probation rp 
      ON e.student_id = rp.student_id 
     AND e.rn = rp.rn + 1
)
SELECT 
    student_name,
    exam_date,
    grade_result,
    warning_level
FROM recursive_probation
WHERE warning_level > 0  -- Filter to isolate active probation escalation warnings
ORDER BY student_name, exam_date;
```

## 5. Production Benefits for Data Engineering

* **In-Database State Machines:** Eliminates the need to pull time-series event logs into external application code (like Python loops) to calculate streak metrics.
* **Conditional Resets:** The `CASE` logic allows complex business rules (such as resetting warning counters upon passing an exam) to execute cleanly within the database kernel.
* **Deterministic Execution:** Pre-sequenced row numbers ensure performance remains fast and bounded.