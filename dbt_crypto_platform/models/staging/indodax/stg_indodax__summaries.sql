{{ config(materialized="view") }}

-- Staging model for Indodax summaries
-- This model normalizes and cleans data from the Bronze layer

with source as (
    select
        pair,
        last,
        buy,
        sell,
        high,
        low,
        vol_coin as vol_asset,
        vol_idr,
        created_at,
        run_id
    from {{ source('bronze', 'summaries') }}
),

unnested_tickers as (
    select
        pair,
        cast(last as decimal(28,8)) as last_price,
        cast(buy as decimal(28,8)) as buy_price,
        cast(sell as decimal(28,8)) as sell_price,
        cast(high as decimal(28,8)) as high_price,
        cast(low as decimal(28,8)) as low_price,
        cast(vol_asset as decimal(28,8)) as volume_asset,
        cast(vol_idr as decimal(28,8)) as volume_idr,
        {{ as_timestamptz('created_at') }} as captured_at,
        cast(run_id as string) as run_id,
        {{ as_timestamptz('now()') }} as ingested_at
    from source
)

select
    cast(pair as string) as pair_id,
    pair_id || '_IDR' as ticker_id,
    last_price,
    buy_price,
    sell_price,
    high_price,
    low_price,
    volume_asset,
    volume_idr,
    captured_at,
    run_id,
    ingested_at
from unnested_tickers
