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
    JOIN houses ON houses.house_id = houses.house_id
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
    SUM(CASE WHEN grade_result IN ('o++', 'o+') THEN 1 ELSE 0 END) AS top_grades
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

-- WITH tmp_courses AS(
--     SELECT
--         first_name || ' ' || last_name AS student_name,
--         grade_result,
--         course_name
-- FROM exams
-- JOIN students
-- ON exams.student_id = students.student_id
-- JOIN courses
-- ON courses.course_id = exams.course_id
-- WHERE course_name IN ('Potions', 'Charms', 'Transfiguration')
-- ),

-- tmp_table_1 AS(
--     SELECT
--         student_name,
--         CASE WHEN course_name = 'Potions' THEN grade_result END AS Potions
--     FROM tmp_courses
--     WHERE course_name = 'Potions'
-- ),

-- tmp_table_2 AS(
--     SELECT
--         student_name,
--         CASE WHEN course_name = 'Charms' THEN grade_result END AS Charms
--     FROM tmp_courses
--     WHERE course_name = 'Charms'
-- ),

-- tmp_table_3 AS(
--     SELECT
--         student_name,
--         CASE WHEN course_name = 'Transfiguration' THEN grade_result END AS Transfiguration
--     FROM tmp_courses
--     WHERE course_name = 'Transfiguration'
-- )

-- SELECT
--     tmp_table_1.student_name AS student,
--     potions,
--     charms,
--     transfiguration
-- FROM tmp_table_1
-- JOIN tmp_table_2 ON tmp_table_1.student_name = tmp_table_2.student_name
-- JOIN tmp_table_3 ON tmp_table_1.student_name = tmp_table_3.student_name
-- ORDER BY student ASC;

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


-- 18. Relational Division: Find pairs of students who share the exact same academic profile 
-- (took the exact same courses and received the exact same grades).

WITH tmp_students AS(
    SELECT
        students.student_id AS student_id,
        first_name || ' ' || last_name AS full_name,
        course_name,
        grade_result
    FROM students
    JOIN exams
    ON students.student_id = exams.student_id
    JOIN courses
    ON exams.course_id = courses.course_id
),

tmp_courses_cnt AS(
    SELECT
        student_id,
        full_name,
        COUNT(course_name) AS courses
    FROM tmp_students
    GROUP BY student_id, full_name
)

SELECT
    a.full_name,
    b.full_name,
    COUNT(*) AS cnt

FROM tmp_students a
JOIN tmp_students b
ON a.course_name = b.course_name AND a.grade_result = b.grade_result AND a.student_id != b.student_id
JOIN tmp_courses_cnt c
ON c.full_name = a.full_name
JOIN tmp_courses_cnt d
ON d.full_name = b.full_name AND c.courses = d.courses
GROUP BY a.full_name, b.full_name, c.courses
HAVING COUNT(*) = c.courses;

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

-- Expert Level (Production Data Engineering & Anomaly Detection)**


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