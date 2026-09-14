-- Singular test: price must be strictly positive
select
    order_id,
    price
from {{ ref('stg_postgres__orders') }}
where price <= 0

union all

select
    pair_id,
    last_price as price
from {{ ref('stg_indodax__summaries') }}
where last_price <= 0
