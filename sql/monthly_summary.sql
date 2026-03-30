-- Truncate and rebuild the monthly sales summary from raw data.
TRUNCATE TABLE analytics.monthly_sales_summary;

INSERT INTO analytics.monthly_sales_summary
    (month, product_name, total_revenue, order_count, avg_order_value, total_items_sold, loaded_at)
SELECT
    DATE_TRUNC('month', oi.created_at)::DATE AS month,
    p.product_name,
    SUM(oi.price_usd)                        AS total_revenue,
    COUNT(DISTINCT oi.order_id)              AS order_count,
    ROUND(SUM(oi.price_usd) / COUNT(DISTINCT oi.order_id), 2) AS avg_order_value,
    COUNT(*)                                  AS total_items_sold,
    NOW()                                     AS loaded_at
FROM raw.order_items oi
JOIN raw.products p ON oi.product_id = p.product_id
GROUP BY DATE_TRUNC('month', oi.created_at)::DATE, p.product_name
ORDER BY month, product_name;
