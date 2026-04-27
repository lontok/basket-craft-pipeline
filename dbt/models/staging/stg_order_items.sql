select
    order_item_id,
    order_id,
    product_id,
    is_primary_item::boolean as is_primary_item,
    price_usd::numeric(12, 2) as price_usd,
    cogs_usd::numeric(12, 2) as cogs_usd,
    created_at
from {{ source('raw', 'order_items') }}
