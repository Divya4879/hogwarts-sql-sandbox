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