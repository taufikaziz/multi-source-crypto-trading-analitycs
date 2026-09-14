{{ config(
    materialized="incremental",
    incremental_strategy="merge",
    unique_key=["date", "symbol"]
) }}

-- Gold market daily - Price performance metrics
-- Grain: 1 row per date + symbol

with daily_market as (
    select
        date,
        symbol,
        open_price,
        high_price,
        low_price,
        close_price,
        volume_idr,
        volume_asset,
        lag(close_price) over (partition by symbol order by date) as prev_close_price
    from {{ ref("int_daily_market") }}
)

select
    date,
    symbol,
    open_price,
    high_price,
    low_price,
    close_price,
    case
        when prev_close_price > 0 then
            ((close_price - prev_close_price) / prev_close_price) * 100
        else null
    end as price_change_pct,
    volume_idr,
    volume_asset,
    {{ as_timestamptz('now()') }} as created_at
from daily_market
