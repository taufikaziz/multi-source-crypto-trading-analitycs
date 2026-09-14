{{ config(materialized="view") }}

-- Staging model for PostgreSQL trades

with source as (
    select
        trade_id,
        order_id,
        price,
        quantity,
        taker_side,
        executed_at
    from {{ source('bronze', 'trades') }}
)

select
    cast(trade_id as string) as trade_id,
    cast(order_id as string) as order_id,
    cast(price as decimal(18,8)) as price,
    cast(quantity as decimal(18,8)) as quantity,
    cast(taker_side as string) as taker_side,
    {{ as_timestamptz('executed_at') }} as executed_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
