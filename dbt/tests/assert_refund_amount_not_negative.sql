-- Returns rows where refund_amount_usd is negative.
-- Should always be empty.
select
    order_item_id,
    refund_amount_usd
from {{ ref('fct_order_items') }}
where refund_amount_usd < 0
