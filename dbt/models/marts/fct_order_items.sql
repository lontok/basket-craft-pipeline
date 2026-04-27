{{ config(materialized='table') }}

with order_context as (
    select
        order_id,
        primary_product_id,
        user_id
    from {{ ref('stg_orders') }}
)

select
    -- Degenerate dimensions
    oi.order_item_id,
    oi.order_id,
    o.user_id,

    -- Foreign keys to dimensions
    oi.created_at::date as date_key,
    oi.product_id,
    o.primary_product_id,

    -- Atomic measures
    oi.price_usd,
    oi.cogs_usd,
    oi.refund_amount_usd,
    oi.is_primary_item,

    -- Derived measures
    (oi.price_usd - oi.cogs_usd)::numeric(12, 2) as gross_profit_usd,
    (oi.price_usd - oi.refund_amount_usd)::numeric(12, 2) as net_revenue_usd,
    (oi.price_usd - oi.cogs_usd - oi.refund_amount_usd)::numeric(12, 2) as net_profit_usd,
    oi.refund_amount_usd > 0 as has_refund,

    -- Timestamp
    oi.created_at
from {{ ref('int_order_items_with_refunds') }} oi
inner join order_context o on oi.order_id = o.order_id
