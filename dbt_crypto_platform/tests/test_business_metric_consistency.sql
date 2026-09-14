-- Singular test: business metrics consistency (no negative counts or volumes)
select
    date,
    symbol,
    active_users,
    total_orders,
    trading_volume,
    market_views
from {{ ref('gold_crypto_business_metrics') }}
where (active_users is not null and active_users < 0)
   or (total_orders is not null and total_orders < 0)
   or (trading_volume is not null and trading_volume < 0)
   or (market_views is not null and market_views < 0)
