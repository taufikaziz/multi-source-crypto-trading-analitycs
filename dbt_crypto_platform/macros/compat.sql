-- Cross-warehouse compatibility helpers.
-- Default implementation targets Databricks SQL; DuckDB overrides follow.
-- Usage: {{ json_string('context', 'user_id') }}

{% macro json_string(column, key) -%}
  {{ adapter.dispatch('json_string', 'crypto_platform')(column, key) }}
{%- endmacro %}

{% macro default__json_string(column, key) -%}
  get_json_object({{ column }}, '$.{{ key }}')
{%- endmacro %}

{% macro duckdb__json_string(column, key) -%}
  json_extract_string({{ column }}, '{{ key }}')
{%- endmacro %}

{% macro as_variant(column) -%}
  {{ adapter.dispatch('as_variant', 'crypto_platform')(column) }}
{%- endmacro %}

{% macro default__as_variant(column) -%}
  cast({{ column }} as variant)
{%- endmacro %}

{% macro duckdb__as_variant(column) -%}
  cast({{ column }} as json)
{%- endmacro %}

{% macro as_timestamptz(column) -%}
  {{ adapter.dispatch('as_timestamptz', 'crypto_platform')(column) }}
{%- endmacro %}

{% macro default__as_timestamptz(column) -%}
  cast({{ column }} as timestamp)
{%- endmacro %}

{% macro duckdb__as_timestamptz(column) -%}
  cast({{ column }} as timestamptz)
{%- endmacro %}