{{ config(
    materialized="incremental",
    incremental_strategy="merge",
    unique_key=["date", "symbol"]
) }}

-- Gold trading daily - Trading activity metrics
-- Grain: 1 row per date + symbol

select
    date,
    symbol,
    total_orders,
    completed_orders,
    buy_volume,
    sell_volume,
    trading_volume,
    avg_trade_size,
    {{ as_timestamptz('now()') }} as created_at
from {{ ref("int_daily_trading") }}
