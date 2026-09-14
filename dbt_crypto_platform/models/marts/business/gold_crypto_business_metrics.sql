{{ config(
    materialized="incremental",
    incremental_strategy="merge",
    unique_key=["date", "symbol"]
) }}

-- Gold crypto business metrics - Unified business metrics
-- Grain: 1 row per date + symbol

select
    m.date,
    m.symbol,
    m.close_price,
    m.volume_idr as market_volume,
    m.price_change_pct,
    t.trading_volume,
    t.total_orders,
    u.active_users,
    u.market_views,
    {{ as_timestamptz('now()') }} as created_at
from {{ ref("gold_market_daily") }} m
left join {{ ref("gold_trading_daily") }} t on m.date = t.date and m.symbol = t.symbol
left join {{ ref("gold_user_activity_daily") }} u on m.date = u.date
