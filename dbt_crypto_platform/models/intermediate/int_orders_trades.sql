{{ config(materialized="view") }}

-- Enriched order-trade join (reusable, no business presentation logic).
-- Grain: 1 row per order + trade (orders without trades have null trade fields).

with orders as (
    select
        order_id,
        user_id,
        pair as symbol,
        order_type,
        price as order_price,
        quantity as order_quantity,
        filled_quantity,
        status,
        created_at as order_created_at,
        updated_at as order_updated_at
    from {{ ref("stg_postgres__orders") }}
),

trades as (
    select
        trade_id,
        order_id,
        price as trade_price,
        quantity as trade_quantity,
        taker_side,
        executed_at
    from {{ ref("stg_postgres__trades") }}
)

select
    o.order_id,
    o.user_id,
    o.symbol,
    o.order_type,
    o.order_price,
    o.order_quantity,
    o.filled_quantity,
    o.status,
    o.order_created_at,
    o.order_updated_at,
    t.trade_id,
    t.trade_price,
    t.trade_quantity,
    t.taker_side,
    t.executed_at
from orders o
left join trades t on o.order_id = t.order_id
