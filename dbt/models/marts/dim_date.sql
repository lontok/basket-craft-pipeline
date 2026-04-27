{{ config(materialized='table') }}

with date_spine as (
    select dateadd(day, seq4(), '2010-01-01'::date)::date as full_date
    from table(generator(rowcount => 11000))
)

select
    full_date as date_key,
    full_date,
    year(full_date) as year,
    quarter(full_date) as quarter,
    month(full_date) as month,
    monthname(full_date) as month_name,
    day(full_date) as day_of_month,
    dayofweekiso(full_date) as day_of_week,
    dayname(full_date) as day_name,
    iff(dayofweekiso(full_date) in (6, 7), true, false) as is_weekend
from date_spine
