{{ config(materialized="view") }}

-- Intermediate model for daily market aggregation
-- Combines pairs and summaries for market metrics
-- Grain: 1 row per date + symbol (portable window aggregation)

with ranked as (
    select
        cast(captured_at as date) as date,
        pair_id as symbol,
        last_price,
        high_price,
        low_price,
        volume_idr,
        volume_asset,
        row_number() over (
            partition by cast(captured_at as date), pair_id
            order by captured_at asc
        ) as rn_asc,
        row_number() over (
            partition by cast(captured_at as date), pair_id
            order by captured_at desc
        ) as rn_desc
    from {{ ref("stg_indodax__summaries") }}
),

daily_prices as (
    select
        date,
        symbol,
        max(case when rn_asc = 1 then last_price end) as open_price,
        max(high_price) as high_price,
        min(low_price) as low_price,
        max(case when rn_desc = 1 then last_price end) as close_price,
        sum(volume_idr) as volume_idr,
        sum(volume_asset) as volume_asset
    from ranked
    group by date, symbol
)

select
    date,
    symbol,
    open_price,
    high_price,
    low_price,
    close_price,
    volume_idr,
    volume_asset
from daily_prices
