"""Integration tests for dbt models."""

import os
import pytest


def test_dbt_project_exists():
    """Test that dbt project exists."""
    assert os.path.exists('dbt_crypto_platform/dbt_project.yml')
    assert os.path.exists('dbt_crypto_platform/profiles.yml')
    assert os.path.exists('dbt_crypto_platform/packages.yml')


def test_dbt_models_exist():
    """Test that all dbt models exist."""
    models_dir = 'dbt_crypto_platform/models'
    
    staging_files = [
        'staging/indodax/stg_indodax__pairs.sql',
        'staging/indodax/stg_indodax__summaries.sql',
        'staging/postgresql/stg_postgres__users.sql',
        'staging/postgresql/stg_postgres__orders.sql',
        'staging/postgresql/stg_postgres__trades.sql',
        'staging/postgresql/stg_postgres__accounts.sql',
        'staging/postgresql/stg_postgres__assets.sql',
        'staging/postgresql/stg_postgres__transactions.sql',
        'staging/mongodb/stg_mongodb__user_events.sql',
    ]
    
    for file in staging_files:
        path = os.path.join(models_dir, file)
        assert os.path.exists(path), f"Missing: {file}"


def test_dbt_marts_exist():
    """Test that all Gold marts exist."""
    marts_dir = 'dbt_crypto_platform/models/marts'
    
    marts_files = [
        'market/gold_market_daily.sql',
        'trading/gold_trading_daily.sql',
        'activity/gold_user_activity_daily.sql',
        'business/gold_crypto_business_metrics.sql',
    ]
    
    for file in marts_files:
        path = os.path.join(marts_dir, file)
        assert os.path.exists(path), f"Missing: {file}"


def test_dbt_intermediate_exist():
    """Test that all intermediate models exist."""
    intermediate_dir = 'dbt_crypto_platform/models/intermediate'
    
    intermediate_files = [
        'int_daily_market.sql',
        'int_daily_trading.sql',
        'int_orders_trades.sql',
        'int_user_events_daily.sql',
        'int_user_trading_activity.sql',
    ]
    
    for file in intermediate_files:
        path = os.path.join(intermediate_dir, file)
        assert os.path.exists(path), f"Missing: {file}"


def test_dbt_schemas_exist():
    """Test that schema.yml files exist."""
    schemas = [
        'staging/indodax/schema.yml',
        'staging/postgresql/schema.yml',
        'staging/mongodb/schema.yml',
        'intermediate/schema.yml',
    ]
    
    for schema in schemas:
        path = os.path.join('dbt_crypto_platform/models', schema)
        assert os.path.exists(path), f"Missing: {schema}"
