"""Generate synthetic MongoDB data for the indodax pipeline.

Collections mirror infra/mongodb/init/01_validation_and_indexes.js
(orderbooks, tickers, user_events) with the envelope shape consumed by
dbt_crypto_platform/models/staging/mongodb/stg_mongodb__user_events.sql
and the watermark extractor in src/ingestion/mongodb.py
(watermark column: ingested_at, ISO8601 string).

user_id values are reused from scripts/synthetic_ids.json (written by
generate_synthetic_postgres.py) so both databases tell one story.
Run the postgres generator first; without it, random ids are used.

Usage (from repo root, after `docker compose -f airflow-docker/docker-compose.yml up -d mongodb`):
    .venv/Scripts/python.exe scripts/generate_synthetic_mongodb.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker
from pymongo import MongoClient

SEED = 42
IDS_FILE = Path("scripts/synthetic_ids.json")

MONGO_URI = (
    "mongodb://mongodb:Mongodbxyz@127.0.0.1:27017/indodax?authSource=admin"
)
DATABASE = "indodax"

N_TICKERS = 400
N_ORDERBOOKS = 150
N_USER_EVENTS = 600

PAIR_META = {
    "btcidr": ("btc_idr", 1700000000.0),
    "ethidr": ("eth_idr", 58000000.0),
    "usdtidr": ("usdt_idr", 16500.0),
    "bnbidr": ("bnb_idr", 10500000.0),
    "solidr": ("sol_idr", 2400000.0),
    "xrpidr": ("xrp_idr", 34000.0),
    "dogeidr": ("doge_idr", 2800.0),
    "adaidr": ("ada_idr", 11500.0),
    "avaxidr": ("avax_idr", 380000.0),
    "dotidr": ("dot_idr", 58000.0),
    "trxidir": ("trx_idr", 4200.0),
    "linkidr": ("link_idr", 280000.0),
}

EVENT_TYPES = ["market_view", "order_created", "order_updated",
               "login", "logout", "page_view"]


def iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def jitter(price: float, pct: float = 0.03) -> float:
    return round(price * random.uniform(1 - pct, 1 + pct), 2)


def depth_levels(mid: float, side: str) -> list:
    levels = []
    for i in range(10):
        offset = mid * 0.0005 * (i + 1)
        price = round(mid - offset if side == "bid" else mid + offset, 2)
        levels.append([price, round(random.uniform(0.001, 3), 8)])
    return levels


def main() -> None:
    random.seed(SEED)
    Faker.seed(SEED)
    fake = Faker("id_ID")
    now = datetime.now(timezone.utc)

    if IDS_FILE.exists():
        ids = json.loads(IDS_FILE.read_text(encoding="utf-8"))
        user_ids = ids["user_ids"]
        print(f"linked {len(user_ids)} postgres users from {IDS_FILE}")
    else:
        user_ids = [uuid.uuid4().hex for _ in range(50)]
        print("WARNING: synthetic_ids.json missing, using random user ids")

    pairs = list(PAIR_META)
    tickers, orderbooks, user_events = [], [], []

    for _ in range(N_TICKERS):
        pair = random.choice(pairs)
        ticker_id, base = PAIR_META[pair]
        last = jitter(base)
        stamped = now - timedelta(days=random.uniform(0, 7))
        tickers.append({
            "event": "ticker_update",
            "context": {
                "pair": pair, "ticker_id": ticker_id,
                "last_price": last,
                "buy_price": round(last * 0.9995, 2),
                "sell_price": round(last * 1.0005, 2),
                "high_24h": round(last * 1.02, 2),
                "low_24h": round(last * 0.98, 2),
                "volume_idr": round(random.uniform(1e7, 5e11), 2),
                "timestamp": iso(stamped),
            },
            "ingested_at": iso(stamped),
        })

    for _ in range(N_ORDERBOOKS):
        pair = random.choice(pairs)
        mid = jitter(PAIR_META[pair][1])
        stamped = now - timedelta(days=random.uniform(0, 7))
        orderbooks.append({
            "event": "orderbook_snapshot",
            "context": {
                "pair": pair,
                "bids": depth_levels(mid, "bid"),
                "asks": depth_levels(mid, "ask"),
                "timestamp": iso(stamped),
            },
            "ingested_at": iso(stamped),
        })

    for _ in range(N_USER_EVENTS):
        event = random.choices(
            EVENT_TYPES, weights=[0.35, 0.2, 0.15, 0.1, 0.05, 0.15])[0]
        stamped = now - timedelta(days=random.uniform(0, 7))
        context = {
            "user_id": random.choice(user_ids),
            "session_id": uuid.uuid4().hex,
            "timestamp": iso(stamped),
        }
        if event in ("order_created", "order_updated"):
            pair = random.choice(pairs)
            context.update({
                "pair": pair,
                "price": jitter(PAIR_META[pair][1]),
                "quantity": round(random.uniform(0.0001, 5), 8),
            })
        elif event == "market_view":
            context["pair"] = random.choice(pairs)
        elif event == "page_view":
            context["page"] = fake.uri_path()
        user_events.append({
            "event": event,
            "event_type": event,
            "context": context,
            "ingested_at": iso(stamped),
        })

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client[DATABASE]
    for name in ("tickers", "orderbooks", "user_events"):
        if name not in db.list_collection_names():
            db.create_collection(name)
    db.tickers.create_index([("event", 1)])
    db.tickers.create_index([("context.pair", 1)])
    db.tickers.create_index([("ingested_at", -1)])
    db.orderbooks.create_index([("event", 1)])
    db.orderbooks.create_index([("context.pair", 1)])
    db.orderbooks.create_index([("ingested_at", -1)])
    db.user_events.create_index([("event_type", 1)])
    db.user_events.create_index([("ingested_at", -1)])

    db.tickers.insert_many(tickers)
    db.orderbooks.insert_many(orderbooks)
    db.user_events.insert_many(user_events)

    print(f"tickers={db.tickers.count_documents({})} "
          f"orderbooks={db.orderbooks.count_documents({})} "
          f"user_events={db.user_events.count_documents({})}")
    client.close()


if __name__ == "__main__":
    main()

