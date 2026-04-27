select
    order_id,
    user_id,
    website_session_id,
    primary_product_id,
    items_purchased,
    price_usd::numeric(12, 2) as price_usd,
    cogs_usd::numeric(12, 2) as cogs_usd,
    created_at
from {{ source('raw', 'orders') }}
