select
    product_id,
    product_name,
    description as product_description,
    created_at
from {{ source('raw', 'products') }}
