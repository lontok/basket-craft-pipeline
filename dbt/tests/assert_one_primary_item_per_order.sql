-- Each order should have exactly one row with is_primary_item = true.
-- Returns rows where the count is anything other than 1.
select
    order_id,
    count(*) as primary_item_count
from {{ ref('fct_order_items') }}
where is_primary_item = true
group by order_id
having count(*) <> 1
