{{ config(materialized="view") }}

-- Staging model for PostgreSQL assets

with source as (
    select
        asset_id,
        symbol,
        name,
        precision,
        created_at
    from {{ source('bronze', 'assets') }}
)

select
    cast(asset_id as string) as asset_id,
    cast(symbol as string) as symbol,
    cast(name as string) as name,
    cast(precision as int) as precision,
    {{ as_timestamptz('created_at') }} as created_at,
    {{ as_timestamptz('now()') }} as captured_at
from source
