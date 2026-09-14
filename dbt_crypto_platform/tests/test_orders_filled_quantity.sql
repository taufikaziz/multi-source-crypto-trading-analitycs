-- Singular test: filled_quantity must not exceed total order quantity
select
    order_id,
    quantity,
    filled_quantity
from {{ ref('stg_postgres__orders') }}
where filled_quantity > quantity
