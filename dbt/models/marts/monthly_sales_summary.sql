-- DEPRECATED 2026-04-26: superseded by fct_order_items + dim_product + dim_date.
-- Maya is validating existing dashboards against the new star schema.
-- Once she confirms numbers match, this file will be removed in a follow-up PR.
-- New equivalent query:
--   SELECT
--       date_trunc('month', f.date_key)::date AS month,
--       p.product_name,
--       SUM(f.price_usd) AS total_revenue,
--       COUNT(DISTINCT f.order_id) AS order_count
--   FROM ANALYTICS.fct_order_items f
--   JOIN ANALYTICS.dim_product p USING (product_id)
--   GROUP BY 1, 2
--   ORDER BY 1, 2;

{{
    config(
        materialized='table'
    )
}}

select
    date_trunc('month', oi.created_at)::date                      as month,
    p.product_name                                                as product_name,
    sum(oi.price_usd)                                             as total_revenue,
    count(distinct oi.order_id)                                   as order_count,
    round(sum(oi.price_usd) / count(distinct oi.order_id), 2)     as avg_order_value,
    count(*)                                                      as total_items_sold,
    current_timestamp()                                           as loaded_at
from {{ ref('stg_order_items') }} oi
join {{ ref('stg_products') }} p
    on oi.product_id = p.product_id
group by 1, 2
order by 1, 2
