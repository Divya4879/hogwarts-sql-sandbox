# Time-Series Moving Averages & Window Framing

## 1. The Engineering Challenge: Smoothing Volatile Data
In production time-series telemetry, financial analytics, and educational observability, raw metrics (such as daily exam scores or system error counts) are often noisy and volatile. Spikes on a single day can distort trends, making it difficult to spot underlying upward or downward trajectories.

To counteract this, systems rely on **Moving Averages** (or rolling averages). A moving average smooths out short-term fluctuations by creating a constantly updating mean across a defined sliding window of time or sequence.

## 2. The Two-Step Architectural Pattern
Calculating a moving average in PostgreSQL requires a two-phase architecture to separate grain aggregation from window transformations:

1. **Phase 1: Grain Normalization (The Base CTE):** Aggregate raw transaction rows into a consistent temporal grain (e.g., one row per calendar date with a total count).
2. **Phase 2: Sliding Window Frame (The Window Function):** Apply an analytical window function with an explicit boundary clause to evaluate a subset of preceding and current rows.

## 3. Anatomy of a Window Frame (`ROWS BETWEEN`)
The power of PostgreSQL window functions lies in the `ROWS` or `RANGE` frame clause. When calculating a 3-day rolling average, you instruct the database engine how many rows to include relative to the current row pointer:

$$\text{Moving Average}_t = \frac{1}{3} \sum_{i=0}^{2} \text{Daily Count}_{t-i}$$

* **`ORDER BY exam_date ASC`**: Ensures chronological sorting so the window moves forward correctly in time.
* **`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`**: Tells PostgreSQL to look at the current row plus the two immediately preceding rows, forming an exact 3-day sliding window.

## 4. Complete Implementation: Query 25
Here is the production-grade query implementing the sliding window moving average:

```sql
WITH daily_top_grades AS (
    -- Step 1: Normalize raw exam rows into daily aggregate counts
    SELECT
        exam_date,
        SUM(CASE WHEN grade_result IN ('o++', 'o') THEN 1 ELSE 0 END) AS daily_count
    FROM exams
    GROUP BY exam_date
)
-- Step 2: Apply a 3-day sliding window frame over the daily aggregates
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
```

## 5. Production Benefits for Data Engineering
* **Dashboard Continuity:** Feeds time-series metrics directly into frontend visualization libraries (like Grafana or custom React charts) with clean trendlines.
* **In-Engine Optimization:** Avoids heavy application-layer iteration loops by leveraging PostgreSQL's highly optimized internal window buffering algorithms.
* **Precision Control:** Explicit row frame definitions give engineers exact command over how windows behave at boundaries and gaps.