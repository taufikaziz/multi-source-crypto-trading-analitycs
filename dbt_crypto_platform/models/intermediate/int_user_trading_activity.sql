{{ config(materialized="view") }}

-- User-day integration of trading and product activity (reusable).
-- Grain: 1 row per date + user_id.

with orders_daily as (
    select
        cast(o.updated_at as date) as date,
        o.user_id,
        count(o.order_id) as total_orders,
        count(case when o.status = 'filled' then 1 end) as completed_orders
    from {{ ref("stg_postgres__orders") }} o
    where cast(o.updated_at as date) is not null
    group by cast(o.updated_at as date), o.user_id
),

trades_daily as (
    select
        cast(t.executed_at as date) as date,
        o.user_id,
        count(t.trade_id) as total_trades,
        sum(t.quantity) as trading_volume
    from {{ ref("stg_postgres__trades") }} t
    join {{ ref("stg_postgres__orders") }} o on t.order_id = o.order_id
    where cast(t.executed_at as date) is not null
    group by cast(t.executed_at as date), o.user_id
),

events_daily as (
    select
        cast(ingested_at as date) as date,
        user_id,
        count(*) as total_events
    from {{ ref("stg_mongodb__user_events") }}
    where cast(ingested_at as date) is not null
      and user_id is not null
    group by cast(ingested_at as date), user_id
)

select
    coalesce(o.date, t.date, e.date) as date,
    coalesce(o.user_id, t.user_id, e.user_id) as user_id,
    coalesce(o.total_orders, 0) as total_orders,
    coalesce(o.completed_orders, 0) as completed_orders,
    coalesce(t.total_trades, 0) as total_trades,
    coalesce(t.trading_volume, 0) as trading_volume,
    coalesce(e.total_events, 0) as total_events
from orders_daily o
full outer join trades_daily t
    on o.date = t.date and o.user_id = t.user_id
full outer join events_daily e
    on coalesce(o.date, t.date) = e.date
    and coalesce(o.user_id, t.user_id) = e.user_id
