{{ config(materialized="view") }}

-- Staging model for PostgreSQL accounts

with source as (
    select
        account_id,
        user_id,
        currency,
        balance,
        locked_balance,
        created_at,
        updated_at
    from {{ source('bronze', 'accounts') }}
)

select
    cast(account_id as string) as account_id,
    cast(user_id as string) as user_id,
    cast(currency as string) as currency,
    cast(balance as decimal(18,8)) as balance,
    cast(locked_balance as decimal(18,8)) as locked_balance,
    {{ as_timestamptz('created_at') }} as created_at,
    {{ as_timestamptz('updated_at') }} as updated_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
