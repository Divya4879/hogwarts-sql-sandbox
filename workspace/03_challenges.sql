
-- ==============================================================================
-- BASIC LEVEL (Warm Up & Filtering)
-- ==============================================================================

-- QUESTION 1: List all students enrolled in Gryffindor, ordered alphabetically by last name.

-- QUESTION 2: Retrieve all courses taught by Severus Snape.

-- QUESTION 3: Find all students who received an 'o++' in Defense Against the Dark Arts.

-- QUESTION 4: Count the total number of students in each house.

-- QUESTION 5: List all exams taken on or after May 28, 2004.

-- QUESTION 6: Find the names of students who have taken exactly 8 exams.


-- ==============================================================================
-- Intermediate Level (Aggregations, Conditional Logic, & Subqueries)
-- ==============================================================================

-- QUESTION 7: Calculate the pass/fail distribution for Potions (Pass = 'o++', 'o+', 'o', 'ee', 'a' | Fail = 'p', 'troll').

-- QUESTION 8: Identify the house with the highest total number of passing grades.

-- QUESTION 9: Find any students who did NOT take the 'History of Magic' exam.

-- QUESTION 10: Determine the most popular elective (the course with the highest number of distinct students enrolled,
-- excluding core classes).

-- QUESTION 11: Calculate the overall percentage of 'troll' grades given out across the entire school.

-- QUESTION 12: Find the student(s) who received the highest number of 'ee' grades.

-- QUESTION 13: Create a query that maps string grades to a numeric GPA
-- (e.g., o++=6, o+=5, o=4, ee=3, a=2, p=1, troll=0) and calculates the average GPA for the Slytherin house.


-- ==============================================================================
-- Advanced Level (Window Functions, CTEs, & Real-World Data Engineering)
-- ==============================================================================

-- QUESTION 14: Rank Students: Use DENSE_RANK() to identify the top-performing student in each house
-- based on their calculated numeric GPA.

-- QUESTION 15: Temporal Windowing: Calculate the running cumulative total of 'o' and 'o++' grades
-- awarded day-by-day throughout the exam period.

-- QUESTION 16: Dynamic Pivoting: Transform the vertical exams table into a horizontal gradebook.
-- Output rows of student names and columns for 'Potions', 'Charms', and 'Transfiguration'
-- showing their specific grade.

-- QUESTION 17: Nested JSONB (API Prep): Write a query using jsonb_agg and jsonb_build_object to output
-- a single JSON document per house, nesting an array of students,
-- which nests an array of their exams and grades.

-- QUESTION 18: Relational Division: Find pairs of students who share the exact same academic profile
-- (took the exact same courses and received the exact same grades).

-- QUESTION 19: Relative Performance: Find students who scored lower in Potions than their own house's
-- average GPA for Potions.

-- QUESTION 20: The Flawless Record: Identify students who passed every single exam they took
-- without a single 'p' or 'troll', using a HAVING clause with conditional aggregation.


-- ==============================================================================
-- Expert Level (Production Data Engineering & Anomaly Detection)
-- ==============================================================================

-- QUESTION 21: Multi-Dimensional Rollups: Use GROUP BY ROLLUP to generate a hierarchical report
-- showing total exams taken by house, by year, and the overall school total in a single query.

-- QUESTION 22: Anomaly Detection (Volatility): Calculate the standard deviation of numeric GPAs for each student
-- to identify who has the most inconsistent academic performance (e.g., scoring 'o++' in one class and 'troll' in another).

-- QUESTION 23: Array Operations: Aggregate a student's enrolled courses into a PostgreSQL array
-- and use the array "contains" operator (@>) to find students who took both 'Potions' and
-- 'Defense Against the Dark Arts'.

-- QUESTION 24: Gap Analysis (generate_series): Use generate_series() to create a complete calendar of the exam period,
-- then LEFT JOIN the exams table to find exactly which dates had zero exams scheduled.

-- QUESTION 25: Moving Averages: Calculate a 3-day rolling average of total 'o' and 'o++' grades awarded
-- across the school to spot grading trends.


-- ==============================================================================
-- PostgreSQL Mastery (Architecture & Performance)
-- ==============================================================================

-- QUESTION 26: Data Integrity Audit: Write a query to flag "suspicious" grading patterns,
-- such as a professor awarding more than 50% 'o++' or 'o' grades across all their exams.

-- QUESTION 27: The Upsert Simulation: Write an INSERT ... ON CONFLICT statement simulating a student retaking a failed exam.
-- Update the grade to the new score, and use the RETURNING clause to output the changes.

-- QUESTION 28: Recursive CTEs: Use a recursive query to generate a sequence of escalating "academic probation" warning levels for students
-- who accumulate consecutive 'p' or 'troll' grades.

-- QUESTION 29: Telemetry & Observability View: Design a materialized view that aggregates daily exam volume and failure rates,
-- structuring the output exactly as it would need to be formatted for scraping by an observability tool or metrics dashboard.

-- QUESTION 30: Query Optimization (EXPLAIN ANALYZE): Write a deliberately inefficient query utilizing a correlated subquery
-- to find top students. Then, write the optimized JOIN equivalent and document the EXPLAIN ANALYZE cost difference in the comments.
