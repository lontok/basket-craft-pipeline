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
