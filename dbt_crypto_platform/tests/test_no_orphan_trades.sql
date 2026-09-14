-- Singular test: no orphan trades (every trade must match a valid order)
select
    t.trade_id,
    t.order_id
from {{ ref('stg_postgres__trades') }} t
left join {{ ref('stg_postgres__orders') }} o on t.order_id = o.order_id
where o.order_id is null
