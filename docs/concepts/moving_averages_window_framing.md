# Moving Averages & Window Framing

## 1. What Is a Moving Average?

A moving average (also called a rolling average) calculates the average of a metric over a sliding window of observations.

It is useful in time-series analytics because raw data can fluctuate significantly from one day to another. A moving average smooths short-term variations and makes longer-term trends easier to identify.

**Example use cases:**
- Monitoring daily server errors.
- Tracking daily sales.
- Analysing website traffic.
- Monitoring daily exam grades.

For this challenge, we want to calculate the **3-day rolling average of the total `o` and `o++` grades awarded across the school**.

---

## 2. The Two-Step Approach

Calculating a moving average from transaction-level data generally involves two stages.

### Step 1: Aggregate data to the required time grain

The `exams` table contains individual exam records. We first aggregate these records into one row per calendar date.

For example:

| exam_date | daily_top_grades |
|---|---:|
| 2026-10-01 | 5 |
| 2026-10-02 | 8 |
| 2026-10-03 | 3 |

This produces a consistent daily metric.

### Step 2: Apply a window function

Once we have one row per date, we use `AVG()` as a window function to calculate the moving average.

```sql
AVG(daily_top_grades) OVER (
    ORDER BY exam_date
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
)
```

This calculates the average using the current row and the two preceding rows.

**Important:** The meaning of those rows depends on the input data. If dates are missing, the preceding rows might not represent the preceding calendar days.

---

## 3. Understanding Window Frames

A window frame determines which rows are included in a window function's calculation for the current row.

PostgreSQL supports two important frame types: `ROWS` and `RANGE`.

### A. ROWS — Physical row-based framing

```sql
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
```

Includes:
- The current row.
- The immediately preceding row.
- The second preceding row.

That is exactly three rows, except at the beginning of the dataset, where fewer rows are available.

**Example:**

| Date | Value | Rows included | Moving average |
|---|---:|---|---:|
| Oct 1 | 5 | 5 | 5.00 |
| Oct 2 | 8 | 5, 8 | 6.50 |
| Oct 3 | 3 | 5, 8, 3 | 5.33 |
| Oct 4 | 7 | 8, 3, 7 | 6.00 |

Notice that the first two rows have partial windows because there are not yet three preceding/current rows available.

### B. RANGE — Value-based framing

`RANGE` defines a frame based on the values in the window's `ORDER BY` expression rather than a fixed number of physical rows.

For example, with a timestamp ordering:

```sql
ORDER BY exam_date::timestamp
RANGE BETWEEN INTERVAL '2 days' PRECEDING AND CURRENT ROW
```

This includes rows whose ordering values fall within the preceding two-day interval, including the current date.

Unlike `ROWS`, the number of included rows can vary.

**Key distinction:**

| Feature | ROWS | RANGE |
|---|---|---|
| Based on | Physical rows | Ordering values |
| Fixed number of rows | Yes, when enough rows exist | No |
| Missing dates | Does not automatically account for them | Date interval still applies |
| Typical use | Last N observations | Last N units of time/value |

For a calendar-day moving average, a continuous calendar table combined with `ROWS` is often a straightforward and predictable approach.

---

## 4. Why Missing Dates Matter

Consider the following daily data:

| Date | Daily top grades |
|---|---:|
| Oct 1 | 5 |
| Oct 2 | 8 |
| Oct 7 | 3 |
| Oct 8 | 7 |

If we directly apply:

```sql
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
```

the window for October 7 includes October 1, October 2 and October 7.

That is a three-row window, but it is not a three-calendar-day window.

If the requirement is a rolling average across consecutive calendar days, we need to generate missing dates and assign zero to dates without qualifying grades.

### Generating a continuous calendar

PostgreSQL provides `generate_series()` for generating a sequence of dates.

```sql
SELECT generate_series(
    DATE '2026-10-01',
    DATE '2026-10-07',
    INTERVAL '1 day'
)::date AS exam_date;
```

This generates every calendar date from October 1 through October 7, including dates with no exam records.

We can then `LEFT JOIN` the daily aggregates and use `COALESCE()` to replace missing counts with zero.

---

## 5. Complete Implementation — Query 25

**Challenge:** Calculate a 3-day rolling average of total `o` and `o++` grades awarded across the school.

```sql
WITH date_bounds AS (
    -- Find the first and last dates in the exam period
    SELECT
        MIN(exam_date) AS start_date,
        MAX(exam_date) AS end_date
    FROM exams
),

calendar AS (
    -- Generate every calendar date in the exam period
    SELECT
        generate_series(
            start_date,
            end_date,
            INTERVAL '1 day'
        )::date AS exam_date
    FROM date_bounds
    WHERE start_date IS NOT NULL
),

daily_top_grades AS (
    -- Aggregate qualifying grades for each date
    SELECT
        exam_date,
        COUNT(*) FILTER (
            WHERE grade_result IN ('o++', 'o')
        ) AS daily_count
    FROM exams
    GROUP BY exam_date
),

complete_daily_metrics AS (
    -- Preserve dates with no qualifying grades
    SELECT
        c.exam_date,
        COALESCE(d.daily_count, 0) AS daily_count
    FROM calendar c
    LEFT JOIN daily_top_grades d
        ON c.exam_date = d.exam_date
)

-- Calculate the rolling average over three consecutive calendar dates
SELECT
    exam_date,
    daily_count,
    ROUND(
        AVG(daily_count) OVER (
            ORDER BY exam_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS rolling_3day_avg
FROM complete_daily_metrics
ORDER BY exam_date;
```

### How the query works

1. **`date_bounds`:** Finds the earliest and latest exam dates.
2. **`calendar`:** Generates every calendar date within that range.
3. **`daily_top_grades`:** Counts only `o++` and `o` grades per date.
4. **`complete_daily_metrics`:** Uses `LEFT JOIN` to preserve dates without qualifying grades. `COALESCE()` converts missing counts to zero.
5. **Final SELECT:** Calculates the rolling average over the current date and the two preceding calendar dates.

### Important boundary behaviour

For the first date, the moving average uses one available day.

For the second date, it uses two available days.

From the third date onwards, it uses three consecutive calendar days.

This is standard partial-window behaviour. If a report should display results only when a complete three-day window exists, filter out the first two dates using an outer query and `ROW_NUMBER()`.

---

## 6. Understanding the Output

Suppose the daily counts are:

| Date | Daily count |
|---|---:|
| Oct 1 | 5 |
| Oct 2 | 8 |
| Oct 3 | 3 |
| Oct 4 | 7 |
| Oct 5 | 4 |

The rolling average is:

| Date | Calculation | Rolling average |
|---|---|---:|
| Oct 1 | 5 / 1 | 5.00 |
| Oct 2 | (5 + 8) / 2 | 6.50 |
| Oct 3 | (5 + 8 + 3) / 3 | 5.33 |
| Oct 4 | (8 + 3 + 7) / 3 | 6.00 |
| Oct 5 | (3 + 7 + 4) / 3 | 4.67 |

Each new row moves the window forward by one calendar day.

---

## 7. Important PostgreSQL Concepts to Remember

### `AVG()` as a window function

```sql
AVG(column_name) OVER (
    ORDER BY date_column
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
)
```

Unlike a regular aggregate, a window aggregate does not collapse the input rows into one output row per group.

### `COALESCE()`

```sql
COALESCE(daily_count, 0)
```

Returns zero when the joined value is `NULL`.

This is important when missing dates should contribute zero to the rolling average.

### `generate_series()`

```sql
generate_series(start_date, end_date, INTERVAL '1 day')
```

Generates a continuous sequence of dates or timestamps.

Useful for:
- Time-series analysis.
- Filling gaps in reporting.
- Daily, weekly or monthly calendars.

### Explicit window frames

Always understand the frame being used.

```sql
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
```

means three rows when three are available.

It does not inherently mean three calendar days.

---

## 8. Practical Takeaways

1. Aggregate raw records to the required time grain before calculating a moving average.
2. Use `ROWS` when the requirement is based on a fixed number of observations.
3. Use `RANGE` when the requirement is based on a range of ordering values.
4. Missing dates matter: generate a continuous calendar if the requirement is based on consecutive calendar days.
5. Use `LEFT JOIN` and `COALESCE()` to preserve dates with zero qualifying records.
6. Moving averages at the beginning of a dataset may use partial windows unless explicitly excluded.
7. Use an explicit window frame instead of relying on PostgreSQL's default frame.

**Core idea:** A moving average is only as meaningful as the window it represents. Always distinguish between the last three rows and the last three calendar days.