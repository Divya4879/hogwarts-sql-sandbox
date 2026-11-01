-- ==============================================================================
-- BASIC LEVEL (Warm Up & Filtering)
-- ==============================================================================


-- 1. List all students enrolled in Gryffindor, ordered alphabetically by last name.

-- 2. Retrieve all courses taught by Severus Snape.

-- 3. Find all students who received an 'o++' in Defense Against the Dark Arts.

-- 4. Count the total number of students in each house.

-- 5. List all exams taken on or after May 28, 2004.

-- 6. Find the names of students who have taken exactly 8 exams.


-- ==============================================================================
-- Intermediate Level (Aggregations, Conditional Logic, & Subqueries)
-- ==============================================================================


-- 7. Calculate the pass/fail distribution for Potions (Pass = 'o++', 'o+', 'o', 'ee', 'a' | Fail = 'p', 'troll').

-- 8. Identify the house with the highest total number of passing grades.

-- 9. Find any students who did NOT take the 'History of Magic' exam.

-- 10. Determine the most popular elective (the course with the highest number of distinct students enrolled, 
-- excluding core classes).

-- 11. Calculate the overall percentage of 'troll' grades given out across the entire school.

-- 12. Find the student(s) who received the highest number of 'ee' grades.

-- 13. Create a query that maps string grades to a numeric GPA 
-- (e.g., o++=6, o+=5, o=4, ee=3, a=2, p=1, troll=0) and calculates the average GPA for the Slytherin house.

-- ==============================================================================
-- Advanced Level (Window Functions, CTEs, & Real-World Data Engineering)
-- ==============================================================================

-- 14. Rank Students: Use DENSE_RANK() to identify the top-performing student in each house 
-- based on their calculated numeric GPA.

-- 15. Temporal Windowing: Calculate the running cumulative total of 'o' and 'o++' grades 
-- awarded day-by-day throughout the exam period.

-- 16. Dynamic Pivoting: Transform the vertical exams table into a horizontal gradebook.
-- Output rows of student names and columns for 'Potions', 'Charms', and 'Transfiguration'
-- showing their specific grade.

-- 17. Nested JSONB (API Prep): Write a query using jsonb_agg and jsonb_build_object to output 
-- a single JSON document per house, nesting an array of students, 
-- which nests an array of their exams and grades.

-- 18. Relational Division: Find pairs of students who share the exact same academic profile 
-- (took the exact same courses and received the exact same grades).

-- 19. Relative Performance: Find students who scored lower in Potions than their own house's 
-- average GPA for Potions.

-- 20. The Flawless Record: Identify students who passed every single exam they took 
-- without a single 'p' or 'troll', using a HAVING clause with conditional aggregation.