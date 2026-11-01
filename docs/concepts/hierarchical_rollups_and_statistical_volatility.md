# Architectural Guide: Hierarchical Rollups & Statistical Volatility

## 1. Multi-Dimensional Hierarchical Rollups (`GROUP BY ROLLUP`)

### **The Engineering Challenge: Reporting Hierarchies**
In business intelligence and enterprise reporting, stakeholders rarely want just a flat breakdown of metrics. They require hierarchical rollups: subtotals by category (e.g., House), subtotals by sub-category (e.g., Year), and a grand total for the entire institution. 

Historically, developers had to write multiple queries combined with `UNION ALL` clauses to achieve this, leading to redundant table scans and bloated code.

### **The Solution: `GROUP BY ROLLUP`**
PostgreSQL provides advanced grouping modifiers like `ROLLUP` to generate multi-dimensional hierarchical reports in a **single pass**. 

When you pass a list of columns to `ROLLUP`, the database automatically computes successive levels of aggregation from left to right:
1. Grouped by both columns: `(house_name, hogwarts_year)`
2. Grouped by the first column only (Subtotal per house across all years): `(house_name, NULL)`
3. Grand total across all houses and years: `(NULL, NULL)`

### **Query 21 Implementation**
```sql
SELECT
    house_name AS "house",
    hogwarts_year AS "Year",
    COUNT(exam_id) AS exams_taken
FROM houses
JOIN students ON houses.house_id = students.house_id
JOIN exams ON students.student_id = exams.student_id
GROUP BY ROLLUP(house_name, hogwarts_year);
```

---

## 2. Statistical Anomaly Detection & Volatility (`STDDEV()`)

### **The Engineering Challenge: Spotting Performance Inconsistency**
A simple arithmetic mean (Average GPA) can be deeply deceptive. For example, a student who scores straight mid-tier grades (`ee`, `ee`) and a student who swings wildly between top marks (`o++`) and failing marks (`troll`) might both end up with the exact same average GPA. 

To identify risky performance volatility or educational anomalies, data engineers must measure **dispersion** rather than central tendency.

### **The Mathematical Foundation: Standard Deviation**
Standard deviation ($\sigma$) measures the amount of variation or dispersion of a set of data values around its mean ($\mu$):

$$\sigma = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (x_i - \mu)^2}$$

* **Low Standard Deviation:** Consistent performance (grades cluster tightly around the average).
* **High Standard Deviation:** Volatile, erratic performance (extreme swings between brilliant successes and severe failures).

### **Query 22 Implementation**
```sql
WITH tmp_data AS (
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
    JOIN exams ON exams.student_id = students.student_id
)
SELECT
    student_id,
    student_name,
    ROUND(STDDEV(marks), 2) AS volatility_score
FROM tmp_data
GROUP BY student_id, student_name
ORDER BY volatility_score DESC, student_name ASC;
```

## 3. Production Benefits for Data Engineering

1. **In-Engine Analytics:** Leveraging native statistical functions like `STDDEV()` avoids pulling massive raw transaction streams into application runtimes (Python/Pandas) for basic anomaly detection.
2. **Single-Pass Aggregations:** `ROLLUP` minimizes database load by calculating complex multi-tier reporting summaries in a single optimized execution plan.