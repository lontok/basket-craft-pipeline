select
    employee_id,
    first_name,
    last_name,
    department,
    salary::numeric(12, 2) as salary,
    email
from {{ source('raw', 'employees') }}
