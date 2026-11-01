-- CREATE DATABASE hogwarts_sandbox;

DROP TABLE IF EXISTS exams, students, courses, houses CASCADE;

CREATE TABLE houses (
    house_id SERIAL PRIMARY KEY,
    house_name VARCHAR(15) UNIQUE NOT NULL,
    head_of_house VARCHAR(50) NOT NULL
);

CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    first_name VARCHAR(20) NOT NULL,
    last_name VARCHAR(20) NOT NULL,
    hogwarts_year INTEGER NOT NULL CHECK(hogwarts_year BETWEEN 1 AND 7),
    house_id INT REFERENCES houses(house_id) 
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_name VARCHAR(30) NOT NULL,
    professor_name VARCHAR(50) NOT NULL
);

CREATE TABLE exams (
    exam_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
    course_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    exam_date DATE NOT NULL,
    grade_result VARCHAR(10) NOT NULL CHECK (grade_result IN ('o++', 'o+', 'o', 'ee', 'a', 'p', 'troll')),
    UNIQUE (student_id, course_id, exam_date)
);