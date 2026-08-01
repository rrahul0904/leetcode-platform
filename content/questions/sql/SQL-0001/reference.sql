WITH eligible_users AS (
    SELECT user_id, cohort_week
    FROM users
    WHERE is_test = FALSE
),
deduplicated_activity AS (
    SELECT DISTINCT source_event_id, user_id, activity_week, event_name
    FROM activity
),
retained_users AS (
    SELECT DISTINCT u.user_id, u.cohort_week
    FROM eligible_users AS u
    JOIN deduplicated_activity AS a
      ON a.user_id = u.user_id
     AND a.activity_week = u.cohort_week + 1
     AND a.event_name = 'session_started'
)
SELECT
    u.cohort_week,
    COUNT(*) AS users,
    COUNT(r.user_id) AS retained_week_one
FROM eligible_users AS u
LEFT JOIN retained_users AS r
  ON r.user_id = u.user_id
 AND r.cohort_week = u.cohort_week
GROUP BY u.cohort_week
ORDER BY u.cohort_week;
