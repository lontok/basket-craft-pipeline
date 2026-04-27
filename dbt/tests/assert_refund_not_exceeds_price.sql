-- Returns rows where refund exceeds the original price.
-- Should always be empty: you can't refund more than you charged.
select
    order_item_id,
    price_usd,
    refund_amount_usd
from {{ ref('fct_order_items') }}
where refund_amount_usd > price_usd
