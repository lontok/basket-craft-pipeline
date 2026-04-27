{{ config(materialized='view') }}

with refunds_per_item as (
    select
        order_item_id,
        sum(refund_amount_usd) as refund_amount_usd
    from {{ ref('stg_order_item_refunds') }}
    group by order_item_id
)

select
    oi.order_item_id,
    oi.order_id,
    oi.product_id,
    oi.is_primary_item,
    oi.price_usd,
    oi.cogs_usd,
    coalesce(r.refund_amount_usd, 0)::numeric(12, 2) as refund_amount_usd,
    oi.created_at
from {{ ref('stg_order_items') }} oi
left join refunds_per_item r
    on oi.order_item_id = r.order_item_id
