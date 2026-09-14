{{ config(materialized="view") }}

-- Staging model for PostgreSQL orders

with source as (
    select
        order_id,
        user_id,
        pair,
        order_type,
        price,
        quantity,
        filled_quantity,
        status,
        created_at,
        updated_at
    from {{ source('bronze', 'orders') }}
)

select
    cast(order_id as string) as order_id,
    cast(user_id as string) as user_id,
    cast(pair as string) as pair,
    cast(order_type as string) as order_type,
    cast(price as decimal(18,8)) as price,
    cast(quantity as decimal(18,8)) as quantity,
    cast(filled_quantity as decimal(18,8)) as filled_quantity,
    cast(status as string) as status,
    {{ as_timestamptz('created_at') }} as created_at,
    {{ as_timestamptz('updated_at') }} as updated_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
