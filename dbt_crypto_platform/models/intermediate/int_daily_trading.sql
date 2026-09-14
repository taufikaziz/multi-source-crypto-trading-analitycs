{{ config(materialized="view") }}

-- Daily trading aggregation built on the reusable order-trade join.
-- Grain: 1 row per date + symbol.

with daily_trading as (
    select
        cast(order_updated_at as date) as date,
        symbol,
        count(distinct order_id) as total_orders,
        count(distinct case when status = 'filled' then order_id end) as completed_orders,
        sum(case when order_type = 'buy' then order_quantity else 0 end) as buy_volume,
        sum(case when order_type = 'sell' then order_quantity else 0 end) as sell_volume,
        sum(trade_quantity) as trading_volume,
        avg(trade_quantity) as avg_trade_size
    from {{ ref("int_orders_trades") }}
    where cast(order_updated_at as date) is not null
    group by cast(order_updated_at as date), symbol
)

select
    date,
    symbol,
    total_orders,
    completed_orders,
    buy_volume,
    sell_volume,
    trading_volume,
    avg_trade_size
from daily_trading
