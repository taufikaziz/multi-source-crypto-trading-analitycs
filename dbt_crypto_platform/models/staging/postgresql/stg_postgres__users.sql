{{ config(materialized="view") }}

-- Staging model for PostgreSQL users
-- Normalizes UUID and trims whitespace from string columns

with source as (
    select
        user_id,
        email,
        full_name,
        is_active,
        created_at,
        updated_at
    from {{ source('bronze', 'users') }}
)

select
    cast(user_id as string) as user_id,
    cast(email as string) as email,
    cast(full_name as string) as full_name,
    is_active::boolean as is_active,
    {{ as_timestamptz('created_at') }} as created_at,
    {{ as_timestamptz('updated_at') }} as updated_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
