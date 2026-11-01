-- ==============================================================================
-- BASIC LEVEL (Warm Up & Filtering)
-- ==============================================================================

-- 1. List all students enrolled in Gryffindor, ordered alphabetically by last name.

SELECT
    first_name || ' ' || last_name AS student_name,
    hogwarts_year
FROM students
WHERE house_id = (SELECT house_id FROM houses WHERE house_name = 'Gryffindor')
ORDER BY last_name;

-- 2. Retrieve all courses taught by Severus Snape.

SELECT
    course_name
FROM courses
WHERE professor_name = 'Severus Snape';

-- 3. Find all students who received an 'o++' in Defense Against the Dark Arts.

SELECT
    first_name || ' ' || last_name AS student_name,
    hogwarts_year,
    house_id,
    exam_id,
    course_name,
    grade_result
FROM students
JOIN exams ON exams.student_id = students.student_id
JOIN courses ON courses.course_id = exams.course_id
WHERE course_name = 'Defense Against the Dark Arts' AND grade_result = 'o++';

-- 4. Count the total number of students in each house.

SELECT
    house_name,
    COUNT(student_id) AS total_students
FROM students
JOIN houses ON students.house_id = houses.house_id
GROUP BY house_name;

-- 5. List all exams taken on or after May 28, 2004.

SELECT *
FROM exams
WHERE exam_date >= '2004-05-28';

-- 6. Find the names of students who have taken exactly 8 exams.

SELECT
    students.first_name || ' ' || students.last_name AS student_name
FROM students
JOIN exams ON students.student_id = exams.student_id
GROUP BY students.student_id
HAVING COUNT(exams.exam_id) = 8; 


-- ==============================================================================
-- Intermediate Level (Aggregations, Conditional Logic, & Subqueries)
-- ==============================================================================


-- 7. Calculate the pass/fail distribution for Potions (Pass = 'o++', 'o+', 'o', 'ee', 'a' | Fail = 'p', 'troll').

WITH tmp_results AS(
    SELECT
        CASE WHEN grade_result IN ('p', 'troll') THEN 'fail'
        ELSE 'pass'
        END AS result,
        exam_id,
        exams.student_id AS student_id,
        houses.house_name AS house_name
    FROM exams
    JOIN students
    ON exams.student_id = students.student_id
    JOIN courses 
    ON courses.course_id = exams.course_id
    JOIN houses
    On houses.house_id = students.house_id
    WHERE course_name = 'Potions'
    )

SELECT
    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS pass_count,
    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fail_count,
    house_name
FROM tmp_results
GROUP BY house_name;

-- 8. Identify the house with the highest total number of passing grades.

WITH tmp_grades AS(
    SELECT
        house_name,
        CASE WHEN grade_result IN ('p', 'troll') THEN 'fail'
        ELSE 'pass'
        END AS result
    FROM exams
    JOIN students
    ON exams.student_id = students.student_id
    JOIN houses
    ON houses.house_id = students.house_id
)

SELECT
    house_name,
    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes
FROM tmp_grades
GROUP BY house_name
ORDER BY passes DESC
LIMIT 1;

-- 9. Find any students who did NOT take the 'History of Magic' exam.

SELECT
    first_name || ' ' || last_name AS student
FROM students
WHERE student_id NOT IN(
    SELECT students.student_id
    FROM students
    JOIN exams
    ON students.student_id = exams.student_id
    JOIN courses 
    ON courses.course_id = exams.course_id
    WHERE course_name = 'History of Magic'
);


-- 10. Determine the most popular elective (the course with the highest number of distinct students enrolled, 
-- excluding core classes).

SELECT
    course_name,
    COUNT(DISTINCT students.student_id) AS students
FROM exams
JOIN students ON exams.student_id = students.student_id
JOIN courses ON exams.course_id = courses.course_id
WHERE course_name NOT IN (
    'Transfiguration', 
    'Charms', 
    'Potions', 
    'Defense Against the Dark Arts', 
    'Herbology', 
    'History of Magic', 
    'Astronomy'
)
GROUP BY course_name
ORDER BY students DESC
LIMIT 1;


-- 11. Calculate the overall percentage of 'troll' grades given out across the entire school.

SELECT
    house_name,

    -- In PostgreSQL, dividing one integer by another (e.g., trolls / total) 
    -- strictly returns an integer. If the numerator is smaller than the denominator 
    -- (like 2 trolls out of 35 exams), Postgres truncates the remainder and returns 0.
    -- 
    -- Fix: Cast at least one operand to DECIMAL or NUMERIC (e.g., trolls::DECIMAL / total) 
    -- to force floating-point division and calculate accurate percentages.

    ROUND(SUM(CASE WHEN grade_result = 'troll' THEN 1 ELSE 0 END)::DECIMAL/COUNT(exam_id) * 100, 2) AS trolls_ratio
    
FROM exams
JOIN students
ON exams.student_id = students.student_id
JOIN houses
ON students.house_id = houses.house_id
GROUP BY house_name;


-- 12. Find the student(s) who received the highest number of 'ee' grades.

WITH tmp_ee AS(
    SELECT
        students.student_id AS student_id,
        first_name || ' ' || last_name AS student_name,
        SUM(CASE WHEN grade_result = 'ee' THEN 1 ELSE 0 END) AS ee_count
    FROM exams
    JOIN students
    ON students.student_id = exams.student_id
    GROUP BY students.student_id
    ORDER BY ee_count DESC
),

tmp_rank AS(
    SELECT
        student_id,
        student_name,
        ee_count,
        RANK() OVER(ORDER BY ee_count DESC) AS rnk
FROM tmp_ee
)

SELECT
    student_name,
    ee_count
FROM tmp_rank
WHERE rnk = 1;


-- 13. Create a query that maps string grades to a numeric GPA 
-- (e.g., o++=6, o+=5, o=4, ee=3, a=2, p=1, troll=0) and calculates the average GPA for the Slytherin house.

WITH student_gpas AS (
    SELECT
        houses.house_name,
        students.student_id,
        -- AVG() automatically handles floating points and normalizes 
        -- for students taking different numbers of elective courses
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
        ) AS individual_gpa
    FROM students
    JOIN exams ON students.student_id = exams.student_id
    JOIN houses ON students.house_id = houses.house_id
    GROUP BY houses.house_name, students.student_id
)
SELECT
    house_name,
    ROUND(AVG(individual_gpa), 2) AS house_avg_gpa
FROM student_gpas
WHERE house_name = 'Slytherin'
GROUP BY house_name;



-- ==============================================================================
-- Advanced Level (Window Functions, CTEs, & Real-World Data Engineering)
-- ==============================================================================



-- 14. Rank Students: Use DENSE_RANK() to identify the top-performing student in each house 
-- based on their calculated numeric GPA.

WITH tmp_marks AS(
    SELECT
        first_name || ' ' || last_name AS student_name,
        students.student_id AS student_id,
        house_name,
        AVG(
            CASE
                WHEN grade_result = 'o++' THEN 6.0
                WHEN grade_result = 'o+' THEN 5.0
                WHEN grade_result = 'o' THEN 4.0
                WHEN grade_result = 'ee' THEN 3.0
                WHEN grade_result = 'a' THEN 2.0
                WHEN grade_result = 'p' THEN 1.0
                ELSE 0.00
            END
        ) AS individual_gpa
    FROM students
    JOIN exams
    ON students.student_id = exams.student_id
    JOIN houses
    ON houses.house_id = students.house_id
    GROUP BY house_name, students.student_id
),

tmp_ranks AS(
    SELECT
        student_name,
        house_name,
        ROUND(individual_gpa, 2) AS gpa,
        DENSE_RANK() OVER(PARTITION BY house_name ORDER BY individual_gpa DESC) AS rnk
    FROM tmp_marks
)

SELECT
    student_name,
    house_name,
    gpa,
    rnk
FROM tmp_ranks
WHERE rnk = 1;


-- 15. Temporal Windowing: Calculate the running cumulative total of 'o' and 'o++' grades 
-- awarded day-by-day throughout the exam period.

WITH tmp_cumulative AS(
    SELECT
    exam_date,
    SUM(CASE WHEN grade_result IN ('o++', 'o') THEN 1 ELSE 0 END) AS top_grades
FROM exams
GROUP BY exam_date
)

SELECT
    exam_date,
    top_grades,
    SUM(top_grades) OVER (
        ORDER BY exam_date ASC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_total
FROM tmp_cumulative;


-- 16. Dynamic Pivoting: Transform the vertical exams table into a horizontal gradebook.
-- Output rows of student names and columns for 'Potions', 'Charms', and 'Transfiguration'
-- showing their specific grade.

SELECT
    first_name || ' ' || last_name AS student,
    MAX(CASE WHEN course_name = 'Potions' THEN grade_result END) AS potions,
    MAX(CASE WHEN course_name = 'Charms' THEN grade_result END) AS charms,
    MAX(CASE WHEN course_name = 'Transfiguration' THEN grade_result END) AS transfiguration
FROM students
JOIN exams ON students.student_id = exams.student_id
JOIN courses ON courses.course_id = exams.course_id
WHERE course_name IN ('Potions', 'Charms', 'Transfiguration')
GROUP BY students.student_id, student
ORDER BY student ASC;

-- 17. Nested JSONB (API Prep): Write a query using jsonb_agg and jsonb_build_object to output 
-- a single JSON document per house, nesting an array of students, 
-- which nests an array of their exams and grades.


SELECT
    jsonb_build_object(
        'house_name', h.house_name,
        'head_of_house', h.head_of_house,
        'students', (
            -- Middle Layer: Aggregate students belonging to this specific house into a JSON array
            SELECT jsonb_agg(
                jsonb_build_object(
                    'student_name', s.first_name || ' ' || s.last_name,
                    'hogwarts_year', s.hogwarts_year,
                    'exams', (
                        -- Innermost Layer: Aggregate exams belonging to this specific student into a JSON array
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'course_name', c.course_name,
                                'grade', e.grade_result,
                                'exam_date', e.exam_date
                            )
                        )
                        FROM exams e
                        JOIN courses c ON e.course_id = c.course_id
                        WHERE e.student_id = s.student_id
                    )
                )
            )
            FROM students s
            WHERE s.house_id = h.house_id
        )
    ) AS house_json
FROM houses h;

-- Q18. Relational Division
-- Find pairs of students who share the exact same academic profile:
-- they must have taken the same courses and received the same grades.


-- Approach:
-- 1. Generate unique pairs of students (avoid comparing a student with themselves).
-- 2. Compare their course_id and grade_result records in both directions.
-- 3. EXCEPT ALL detects differences, including differences in duplicate attempts.
-- 4. Return a pair only when neither student has an unmatched record.


SELECT
    s1.student_id AS student_1_id,
    s1.first_name || ' ' || s1.last_name AS student_1,
    s2.student_id AS student_2_id,
    s2.first_name || ' ' || s2.last_name AS student_2
FROM students s1
JOIN students s2
    ON s1.student_id < s2.student_id

WHERE NOT EXISTS (
    -- Records belonging to student 1 but not student 2.
    SELECT e1.course_id, e1.grade_result
    FROM exams e1
    WHERE e1.student_id = s1.student_id

    EXCEPT ALL

    SELECT e2.course_id, e2.grade_result
    FROM exams e2
    WHERE e2.student_id = s2.student_id
)

AND NOT EXISTS (
    -- Records belonging to student 2 but not student 1.
    SELECT e2.course_id, e2.grade_result
    FROM exams e2
    WHERE e2.student_id = s2.student_id

    EXCEPT ALL

    SELECT e1.course_id, e1.grade_result
    FROM exams e1
    WHERE e1.student_id = s1.student_id
)

ORDER BY student_1_id, student_2_id;

-- 19. Relative Performance: Find students who scored lower in Potions than their own house's 
-- average GPA for Potions.

WITH student_gpas AS (
    SELECT
        houses.house_name AS house_name,
        students.student_id AS student_id,
        exams.course_id AS course_id,
        course_name,
        first_name || ' ' || last_name AS full_name,
        CASE
            WHEN grade_result = 'o++' THEN 6.0
            WHEN grade_result = 'o+'  THEN 5.0
            WHEN grade_result = 'o'   THEN 4.0
            WHEN grade_result = 'ee'  THEN 3.0
            WHEN grade_result = 'a'   THEN 2.0
            WHEN grade_result = 'p'   THEN 1.0
            ELSE 0.0
        END AS marks
    FROM students
    JOIN exams ON students.student_id = exams.student_id
    JOIN houses ON houses.house_id = students.house_id
    JOIN courses ON courses.course_id = exams.course_id
    WHERE course_name = 'Potions'
    GROUP BY houses.house_name, exams.course_id, students.student_id, course_name, marks  
),

house_gpas AS(
    SELECT
        house_name,
        ROUND(SUM(marks)::DECIMAL/COUNT(student_id), 2) AS house_gpa
    FROM student_gpas
    GROUP BY house_name
)

SELECT
    full_name,
    student_gpas.house_name
FROM student_gpas
JOIN house_gpas
ON student_gpas.house_name = house_gpas.house_name
WHERE marks < house_gpa;



-- 20. The Flawless Record: Identify students who passed every single exam they took 
-- without a single 'p' or 'troll', using a HAVING clause with conditional aggregation.

SELECT
    a.student_id,
    first_name || ' ' || last_name AS full_name
FROM students a
JOIN exams
ON a.student_id = exams.student_id
GROUP BY a.student_id
HAVING SUM(CASE WHEN grade_result IN('p', 'troll') THEN 1 ELSE 0 END) = 0
ORDER BY full_name ASC;



-- =============================================================================
-- Expert Level (Production Data Engineering & Anomaly Detection)
-- =============================================================================



-- 21. Multi-Dimensional Rollups: Use GROUP BY ROLLUP to generate a hierarchical report 
-- showing total exams taken by house, by year, and the overall school total in a single query.

SELECT
    house_name AS "house",
    hogwarts_year AS "Year",
    COUNT(exam_id) AS exams_taken
FROM houses
JOIN students
ON houses.house_id = students.house_id
JOIN exams ON students.student_id = exams.student_id
GROUP BY ROLLUP(house_name, hogwarts_year);

-- 22. Anomaly Detection (Volatility): Calculate the standard deviation of numeric GPAs for each student 
-- to identify who has the most inconsistent academic performance (e.g., scoring 'o++' in one class and 'troll' in another).

WITH tmp_data AS(
    SELECT
        first_name || ' ' || last_name AS student_name,
        students.student_id AS student_id,
        exams.course_id AS course_id,
        CASE
            WHEN grade_result = 'o++' THEN 6.0
            WHEN grade_result = 'o+'  THEN 5.0
            WHEN grade_result = 'o'   THEN 4.0
            WHEN grade_result = 'ee'  THEN 3.0
            WHEN grade_result = 'a'   THEN 2.0
            WHEN grade_result = 'p'   THEN 1.0
            ELSE 0.0
        END AS marks
    FROM students
    JOIN exams
    ON exams.student_id = students.student_id
)

SELECT
    student_id,
    student_name,
    ROUND(STDDEV(marks), 2) AS volatility_score
FROM tmp_data
GROUP BY student_id, student_name
ORDER BY volatility_score DESC, student_name ASC;


-- 23. Array Operations: Aggregate a student's enrolled courses into a PostgreSQL array 
-- and use the array "contains" operator (@>) to find students who took both 'Potions' and 
-- 'Defense Against the Dark Arts'.

WITH student_courses AS (
    SELECT
        students.student_id,
        first_name || ' ' || last_name AS student_name,
        -- Use ARRAY_AGG() to build a native PostgreSQL text array
        -- Explicitly cast the aggregated array to TEXT[]
        ARRAY_AGG(course_name)::TEXT[] AS enrolled_courses
    FROM students
    JOIN exams ON students.student_id = exams.student_id
    JOIN courses ON exams.course_id = courses.course_id
    GROUP BY students.student_id, students.first_name, students.last_name
)
SELECT
    student_name,
    enrolled_courses
FROM student_courses
-- Use the native array containment operator (@>) with the ARRAY constructor
WHERE enrolled_courses @> ARRAY['Potions', 'Defense Against the Dark Arts'];

-- 24. Gap Analysis (generate_series): Use generate_series() to create a complete calendar of the exam period, 
-- then LEFT JOIN the exams table to find exactly which dates had zero exams scheduled.

WITH tmp_table AS(
    SELECT
        MIN(exam_date) AS min_date,
        MAX(exam_date) AS max_date
    FROM exams
),

all_dates AS(
    SELECT
        generate_series(min_date::date, max_date::date, '1 day'::interval)::date AS exam_date
    FROM tmp_table
)

SELECT
    all_dates.exam_date,
    COUNT(exam_id) AS exams
FROM all_dates
LEFT JOIN exams
ON all_dates.exam_date = exams.exam_date
GROUP BY all_dates.exam_date
ORDER BY all_dates.exam_date;


-- 25. Moving Averages: Calculate a 3-day rolling average of total 'o' and 'o++' grades awarded 
-- across the school to spot grading trends.

WITH daily_top_grades AS (
    SELECT
        exam_date,
        SUM(CASE WHEN grade_result IN ('o++', 'o') THEN 1 ELSE 0 END) AS daily_count
    FROM exams
    GROUP BY exam_date
)

SELECT
    exam_date,
    daily_count,
    ROUND(
        AVG(daily_count) OVER (
            ORDER BY exam_date ASC
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 
        2
    ) AS rolling_3day_avg
FROM daily_top_grades
ORDER BY exam_date ASC;



-- =============================================================================
-- PostgreSQL Mastery (Architecture & Performance)
-- =============================================================================



-- Q26. Data Integrity Audit
-- Flag professors who award more than 50% of their grades as either 'o++' or 'o'.


-- Approach:
-- 1. Group all exam records by professor.
-- 2. Count the total exams conducted by each professor.
-- 3. Count the combined number of 'o++' and 'o' grades.
-- 4. Calculate their combined percentage.
-- 5. Return only professors whose percentage exceeds 50%.


-- Important:
-- The percentage is calculated using the combined count.
-- We do NOT calculate separate percentages for each grade.


SELECT
    c.professor_name,
    COUNT(e.exam_id) AS total_exams,

    COUNT(e.exam_id) FILTER (
        WHERE e.grade_result IN ('o++', 'o')
    ) AS top_grade_count,

    ROUND(
        100.0 * COUNT(e.exam_id) FILTER (
            WHERE e.grade_result IN ('o++', 'o')
        ) / NULLIF(COUNT(e.exam_id), 0),
        2
    ) AS top_grade_percentage

FROM courses c
JOIN exams e
    ON e.course_id = c.course_id

GROUP BY c.professor_name

HAVING
    100.0 * COUNT(e.exam_id) FILTER (
        WHERE e.grade_result IN ('o++', 'o')
    ) / NULLIF(COUNT(e.exam_id), 0) > 50

ORDER BY top_grade_percentage DESC, c.professor_name;


-- 27. The Upsert Simulation: Write an INSERT ... ON CONFLICT statement simulating a student retaking a failed exam.
-- Update the grade to the new score, and use the RETURNING clause to output the changes.

INSERT INTO exams (student_id, course_id, exam_date, grade_result) VALUES
    (1, 3, '2004-05-26', 'ee'),    -- Potions 
    (1, 6, '2004-05-29', 'a'),     -- History of Magic
    (1, 8, '2004-05-31', 'o+')     -- Care of Magical Creatures

ON CONFLICT (student_id, course_id, exam_date)

DO UPDATE SET grade_result = EXCLUDED.grade_result

RETURNING student_id, course_id, exam_date, grade_result;

-- Q28. Recursive CTEs
-- Generate escalating academic probation warning levels
-- for students who accumulate consecutive 'p' or 'troll' grades.


-- Approach:

-- 1. Assign a chronological row number to every student's exams.
-- 2. Start the recursive process with each student's first exam.
-- 3. Move to the next exam using student_id and row number.
-- 4. Increase the warning level for a failed grade.
-- 5. Reset the warning level to zero after a passing grade.
-- 6. Display only records where the warning level is greater than zero.

-- Grade interpretation follows the pass/fail definition in Q7:
-- 'p' and 'troll' are failures.


WITH RECURSIVE numbered_exams AS (

    -- Step 1: Establish a deterministic chronological sequence.
    SELECT
        s.student_id,
        s.first_name || ' ' || s.last_name AS student_name,
        e.exam_id,
        e.exam_date,
        e.grade_result,

        ROW_NUMBER() OVER (
            PARTITION BY s.student_id
            ORDER BY e.exam_date, e.exam_id
        ) AS rn

    FROM students s
    JOIN exams e
        ON e.student_id = s.student_id
),

probation AS (

    -- Step 2: Anchor member.
    -- Evaluate the student's first exam.

    SELECT
        student_id,
        student_name,
        exam_id,
        exam_date,
        grade_result,
        rn,

        CASE
            WHEN grade_result IN ('p', 'troll') THEN 1
            ELSE 0
        END AS warning_level

    FROM numbered_exams
    WHERE rn = 1

    UNION ALL

    -- Step 3: Recursive member.
    -- Process the next exam for the same student.

    SELECT
        e.student_id,
        e.student_name,
        e.exam_id,
        e.exam_date,
        e.grade_result,
        e.rn,

        CASE
            WHEN e.grade_result IN ('p', 'troll')
                THEN p.warning_level + 1
            ELSE 0
        END AS warning_level

    FROM numbered_exams e
    JOIN probation p
        ON e.student_id = p.student_id
       AND e.rn = p.rn + 1
)

-- Step 4: Display only students with active probation warnings.

SELECT
    student_id,
    student_name,
    exam_id,
    exam_date,
    grade_result,
    warning_level AS consecutive_failure_count

FROM probation
WHERE warning_level > 0

ORDER BY student_name, exam_date, exam_id;


-- 29. Telemetry & Observability View: Design a materialized view that aggregates daily exam volume and failure rates,
-- structuring the output exactly as it would need to be formatted for scraping by an observability tool or metrics dashboard.

CREATE MATERIALIZED VIEW daily_exam_metrics AS
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
GROUP BY exam_date;

-- 30. Query Optimization (EXPLAIN ANALYZE): Write a deliberately inefficient query utilizing a correlated subquery 
-- to find top students. Then, write the optimized JOIN equivalent and document the EXPLAIN ANALYZE cost difference in the comments.

BEGIN;

EXPLAIN ANALYZE

WITH tmp_table AS(
    SELECT
        students.student_id,
        first_name || ' ' || last_name AS student_name,
        SUM(
            CASE
                WHEN grade_result = 'o++' THEN 6.0
                WHEN grade_result = 'o+'  THEN 5.0
                WHEN grade_result = 'o'   THEN 4.0
                WHEN grade_result = 'ee'  THEN 3.0
                WHEN grade_result = 'a'   THEN 2.0
                WHEN grade_result = 'p'   THEN 1.0
                ELSE 0.0
            END
        ) AS marks,
        COUNT(course_id) AS courses
    FROM students
    JOIN exams
    ON students.student_id = exams.student_id
    GROUP BY students.student_id, student_name
)

SELECT
    student_name,
    ROUND(marks/courses, 2) AS avg_gpa
FROM tmp_table
ORDER BY avg_gpa DESC;

ROLLBACK;

---

BEGIN;

EXPLAIN ANALYZE

SELECT
    s.first_name || ' ' || s.last_name AS student_name,
    ROUND((
        SELECT AVG(
            CASE
                WHEN e.grade_result = 'o++' THEN 6.0
                WHEN e.grade_result = 'o+'  THEN 5.0
                WHEN e.grade_result = 'o'   THEN 4.0
                WHEN e.grade_result = 'ee'  THEN 3.0
                WHEN e.grade_result = 'a'   THEN 2.0
                WHEN e.grade_result = 'p'   THEN 1.0
                ELSE 0.0
            END
        )
        FROM exams e
        WHERE e.student_id = s.student_id
    ), 2) AS avg_gpa
FROM students s
WHERE EXISTS (
    SELECT 1
    FROM exams e
    WHERE e.student_id = s.student_id
)
ORDER BY avg_gpa DESC;

ROLLBACK;