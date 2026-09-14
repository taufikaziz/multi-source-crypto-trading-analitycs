{{ config(materialized="view") }}

-- Daily-normalized user events (reusable across activity marts).
-- Grain: 1 row per date.

with daily as (
    select
        cast(ingested_at as date) as date,
        count(distinct user_id) as active_users,
        count(case when event_type = 'market_view' then 1 end) as market_views,
        count(case when event_type in ('order_created', 'order_updated') then 1 end) as order_events,
        count(case when event_type = 'login' then 1 end) as login_events
    from {{ ref("stg_mongodb__user_events") }}
    where cast(ingested_at as date) is not null
    group by cast(ingested_at as date)
)

select date, active_users, market_views, order_events, login_events
from daily
