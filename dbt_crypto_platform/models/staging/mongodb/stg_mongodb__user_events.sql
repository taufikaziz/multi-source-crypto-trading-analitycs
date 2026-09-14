{{ config(materialized="view") }}

-- Staging model for MongoDB user_events
-- Flattens nested context and normalizes timestamps

with source as (
    select
        _id,
        event,
        context,
        ingested_at
    from {{ source('bronze', 'user_events') }}
),

flattened as (
    select
        _id,
        event as event_type,
        {{ json_string('context', 'user_id') }} as user_id,
        {{ json_string('context', 'session_id') }} as session_id,
        {{ as_timestamptz(json_string('context', 'timestamp')) }} as event_timestamp,
        {{ as_variant('context') }} as event_properties,
        ingested_at
    from source
)

select
    cast(_id as string) as event_id,
    cast(event_type as string) as event_type,
    user_id,
    session_id,
    event_timestamp,
    event_properties,
    {{ as_timestamptz('ingested_at') }} as ingested_at,
    {{ as_timestamptz('now()') }} as captured_at
from flattened