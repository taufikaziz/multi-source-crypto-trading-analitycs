"""Tests for Airflow DAGs."""

import os
import pytest


def test_dag_files_exist():
    """Test that all DAG files exist."""
    dags = [
        'crypto_ingestion.py',
        'dbt_transformation.py',
        'databricks_load.py',
    ]
    
    for dag in dags:
        path = os.path.join('dags', dag)
        assert os.path.exists(path), f"Missing DAG: {dag}"


def test_dag_syntax_valid():
    """Test that DAG files have valid Python syntax."""
    import py_compile
    
    dags = [
        'dags/crypto_ingestion.py',
        'dags/dbt_transformation.py',
        'dags/databricks_load.py',
    ]
    
    for dag in dags:
        try:
            py_compile.compile(dag, doraise=True)
            assert True, f"Syntax OK: {dag}"
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in {dag}: {e}")


def test_dag_content_valid():
    """Test that DAG files have required content."""
    required_patterns = {
        'crypto_ingestion.py': ['@dag', 'crypto_ingestion', 'extract_all_sources'],
        'dbt_transformation.py': ['@dag', 'dbt_transformation', 'run_dbt_build'],
        'databricks_load.py': ['@dag', 'databricks_load', 'load_to_databricks'],
    }
    
    for dag_file, patterns in required_patterns.items():
        path = os.path.join('dags', dag_file)
        with open(path, 'r') as f:
            content = f.read()
            for pattern in patterns:
                assert pattern in content, f"Missing pattern '{pattern}' in {dag_file}"


def test_dag_has_schedule():
    """Test that DAGs have proper schedule configuration."""
    dag_configs = {
        'crypto_ingestion.py': '@daily',
        'dbt_transformation.py': 'schedule=',
        'databricks_load.py': 'schedule=',
    }
    
    for dag_file, schedule in dag_configs.items():
        path = os.path.join('dags', dag_file)
        with open(path, 'r') as f:
            content = f.read()
            assert schedule in content, f"Missing schedule in {dag_file}"
