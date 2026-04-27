-- Each order should have exactly one row with is_primary_item = true.
-- Returns rows where the count is anything other than 1, including zero.
-- Filtering with WHERE before GROUP BY would silently drop orders with no
-- primary item, so we count_if inside the aggregation to catch both
-- zero-primary and multi-primary orders.
select
    order_id,
    count_if(is_primary_item = true) as primary_item_count
from {{ ref('fct_order_items') }}
group by order_id
having count_if(is_primary_item = true) <> 1
