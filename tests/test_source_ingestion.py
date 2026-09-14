import asyncio
from datetime import datetime, timezone

import src.orchestration.tasks as tasks

NOW = datetime(2026, 9, 12, 15, tzinfo=timezone.utc)


class FakeExtractor:
    rows_by_name = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def connect(self):
        pass

    async def close(self):
        pass

    async def extract(self, last_watermark):
        name = self.kwargs.get("table", self.kwargs.get("collection"))
        return list(self.rows_by_name.get(name, [])), NOW


class FakeManager:
    instances = []

    def __init__(self, conn_string):
        self.conn_string = conn_string
        self.committed = []
        FakeManager.instances.append(self)

    async def connect(self):
        pass

    async def close(self):
        pass

    async def get_all_watermarks(self):
        return {}

    async def commit_watermarks(self, watermarks, source):
        self.committed.append((watermarks, source))


def test_extract_postgres_skips_empty_tables(monkeypatch):
    FakeExtractor.rows_by_name = {
        "users": [{"user_id": "u1", "updated_at": NOW}],
        "orders": [],
    }
    FakeManager.instances = []
    monkeypatch.setattr(tasks, "PostgresExtractor", FakeExtractor)
    monkeypatch.setattr(tasks, "WatermarkManager", FakeManager)

    datasets, watermarks = asyncio.run(tasks.extract_postgres_data(run_id="test_run_1"))

    assert set(datasets) == {"users"}
    assert set(watermarks) == {"postgresql.users"}
    assert watermarks["postgresql.users"] == NOW


def test_extract_mongodb_returns_all_collections(monkeypatch):
    FakeExtractor.rows_by_name = {
        "tickers": [{"event": "ticker_update"}],
        "orderbooks": [{"event": "orderbook_snapshot"}],
        "user_events": [{"event": "login"}],
    }
    FakeManager.instances = []
    monkeypatch.setattr(tasks, "MongoDBExtractor", FakeExtractor)
    monkeypatch.setattr(tasks, "WatermarkManager", FakeManager)

    datasets, watermarks = asyncio.run(tasks.extract_mongodb_data(run_id="test_run_1"))

    assert set(datasets) == {"tickers", "orderbooks", "user_events"}
    assert set(watermarks) == {
        "mongodb.tickers", "mongodb.orderbooks", "mongodb.user_events",
    }


def test_write_source_bronze_skips_empty():
    assert asyncio.run(
        tasks.write_source_bronze_data("postgresql", {}, NOW)
    ) == {}


def test_write_source_bronze_uses_source_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("BRONZE_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("BRONZE_STORAGE_BACKEND", "local")
    paths = asyncio.run(
        tasks.write_source_bronze_data(
            "postgresql", {"orders": [{"order_id": "o1"}]}, NOW,
        )
    )
    assert "source=postgresql" in paths["orders"]
    assert "dataset=orders" in paths["orders"]


def test_commit_skips_empty_watermarks(monkeypatch):
    FakeManager.instances = []
    monkeypatch.setattr(tasks, "WatermarkManager", FakeManager)
    asyncio.run(tasks.commit_source_watermarks("postgres", {}))
    assert FakeManager.instances == []


def test_commit_passes_source_through(monkeypatch):
    FakeManager.instances = []
    monkeypatch.setattr(tasks, "WatermarkManager", FakeManager)
    asyncio.run(
        tasks.commit_source_watermarks("mongodb", {"mongodb.tickers": NOW})
    )
    assert FakeManager.instances[-1].committed == [
        ({"mongodb.tickers": NOW}, "mongodb")
    ]
