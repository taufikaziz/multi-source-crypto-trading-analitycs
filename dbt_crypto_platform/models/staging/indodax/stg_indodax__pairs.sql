{{ config(materialized="view") }}

-- Staging model for Indodax pairs
-- This model normalizes and cleans data from the Bronze layer

with source as (
    select
        pair,
        ticker_id,
        name as asset_name,
        base_currency,
        quote_currency,
        price_decimal_places,
        min_price,
        max_price,
        min_volume,
        created_at,
        run_id
    from {{ source('bronze', 'pairs') }}
)

select
    cast(pair as string) as pair_id,
    cast(ticker_id as string) as ticker_id,
    cast(asset_name as string) as asset_name,
    cast(base_currency as string) as base_currency,
    cast(quote_currency as string) as quote_currency,
    cast(price_decimal_places as int) as price_decimal_places,
    cast(min_price as decimal(18,8)) as min_price,
    cast(max_price as decimal(18,8)) as max_price,
    cast(min_volume as decimal(18,8)) as min_volume,
    {{ as_timestamptz('created_at') }} as created_at,
    cast(run_id as string) as run_id,
    {{ as_timestamptz('now()') }} as captured_at
from source
