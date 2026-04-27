{{ config(materialized='table') }}

select
    product_id,
    product_name,
    product_description,
    created_at as product_created_at
from {{ ref('stg_products') }}
