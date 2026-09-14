{{ config(
    materialized="incremental",
    incremental_strategy="merge",
    unique_key="date"
) }}

-- Gold user activity daily - User engagement metrics
-- Grain: 1 row per date

select
    date,
    active_users,
    market_views,
    order_events,
    login_events,
    {{ as_timestamptz('now()') }} as created_at
from {{ ref("int_user_events_daily") }}