select
    order_item_refund_id,
    order_item_id,
    refund_amount_usd::numeric(12, 2) as refund_amount_usd,
    created_at
from {{ source('raw', 'order_item_refunds') }}
