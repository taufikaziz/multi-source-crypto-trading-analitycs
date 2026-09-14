{{ config(materialized="view") }}

-- Staging model for PostgreSQL transactions

with source as (
    select
        transaction_id,
        account_id,
        amount,
        type,
        status,
        created_at
    from {{ source('bronze', 'transactions') }}
)

select
    cast(transaction_id as string) as transaction_id,
    cast(account_id as string) as account_id,
    cast(amount as decimal(18,8)) as amount,
    cast(type as string) as type,
    cast(status as string) as status,
    {{ as_timestamptz('created_at') }} as created_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
