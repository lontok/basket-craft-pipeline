-- The fact's INNER JOIN to stg_orders could silently drop rows if any line item
-- references a missing order. Cross-join the row counts; this returns rows
-- only when fct and stg disagree.
with fct_count as (
    select count(*) as n from {{ ref('fct_order_items') }}
),
stg_count as (
    select count(*) as n from {{ ref('stg_order_items') }}
)
select
    fct_count.n as fct_n,
    stg_count.n as stg_n
from fct_count
cross join stg_count
where fct_count.n <> stg_count.n
