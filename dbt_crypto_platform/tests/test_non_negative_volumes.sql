-- Singular test: volume must be non-negative in market and trading metrics
select
    date,
    symbol,
    volume_idr,
    volume_asset
from {{ ref('int_daily_market') }}
where volume_idr < 0 or volume_asset < 0

union all

select
    date,
    symbol,
    trading_volume as volume_idr,
    0 as volume_asset
from {{ ref('int_daily_trading') }}
where trading_volume < 0 or buy_volume < 0 or sell_volume < 0
