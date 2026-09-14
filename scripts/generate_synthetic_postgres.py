"""Generate synthetic PostgreSQL data for the indodax pipeline.

Tables match the bronze sources consumed by dbt staging models
(dbt_crypto_platform/models/staging/postgresql/stg_postgres__*.sql):
users, accounts, assets, orders, trades, transactions, plus the
etl_watermark table used by src/ingestion/watermark.py.

Default mode writes a SQL file (postgres has no published host port,
so load it via docker exec). With --execute it inserts directly,
useful from inside the compose network.

Usage (from repo root):
    .venv/Scripts/python.exe scripts/generate_synthetic_postgres.py
    docker exec indodax-airflow-postgres psql -U airflow -d airflow -c "CREATE DATABASE indodax"
    Get-Content scripts/seed_postgres.sql -Raw | docker exec -i indodax-airflow-postgres psql -U airflow -d indodax
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

SEED = 42
OUT_SQL = Path("scripts/seed_postgres.sql")
OUT_IDS = Path("scripts/synthetic_ids.json")

N_USERS = 50
N_ACCOUNTS = 120
N_ORDERS = 500
N_TRADES = 1000
N_TRANSACTIONS = 600

PAIR_BASE_PRICE = {
    "btcidr": 1700000000.0,
    "ethidr": 58000000.0,
    "usdtidr": 16500.0,
    "bnbidr": 10500000.0,
    "solidr": 2400000.0,
    "xrpidr": 34000.0,
    "dogeidr": 2800.0,
    "adaidr": 11500.0,
    "avaxidr": 380000.0,
    "dotidr": 58000.0,
    "trxidir": 4200.0,
    "linkidr": 280000.0,
}

ASSETS = [
    ("IDR", "Indonesian Rupiah", 2),
    ("BTC", "Bitcoin", 8),
    ("ETH", "Ethereum", 8),
    ("USDT", "Tether", 6),
    ("BNB", "BNB", 8),
    ("SOL", "Solana", 8),
    ("XRP", "XRP", 6),
    ("DOGE", "Dogecoin", 4),
    ("ADA", "Cardano", 6),
    ("AVAX", "Avalanche", 8),
    ("DOT", "Polkadot", 8),
    ("TRX", "TRON", 6),
]


def ts(days_min: float, days_max: float, now: datetime) -> datetime:
    return now - timedelta(days=random.uniform(days_min, days_max))


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def fts(value: datetime) -> str:
    return "'" + value.strftime("%Y-%m-%d %H:%M:%S+00") + "'"


def uid() -> str:
    return uuid.uuid4().hex


def jitter(price: float, pct: float = 0.05) -> float:
    return round(price * random.uniform(1 - pct, 1 + pct), 8)


def generate(now: datetime):
    fake = Faker("id_ID")
    random.seed(SEED)
    Faker.seed(SEED)

    assets, users, accounts, orders, trades, transactions = [], [], [], [], [], []

    for symbol, name, precision in ASSETS:
        assets.append({
            "asset_id": uid(), "symbol": symbol, "name": name,
            "precision": precision, "created_at": ts(300, 900, now),
        })

    for _ in range(N_USERS):
        created = ts(10, 400, now)
        users.append({
            "user_id": uid(), "email": fake.unique.email(),
            "full_name": fake.name(),
            "is_active": random.random() > 0.08,
            "created_at": created,
            "updated_at": created + timedelta(days=random.uniform(0, 30)),
        })

    user_ids = [u["user_id"] for u in users]
    currencies = [a["symbol"] for a in assets]
    for _ in range(N_ACCOUNTS):
        created = ts(5, 300, now)
        accounts.append({
            "account_id": uid(), "user_id": random.choice(user_ids),
            "currency": random.choice(currencies),
            "balance": round(random.uniform(0, 500_000_000), 8),
            "locked_balance": round(random.uniform(0, 5_000_000), 8),
            "created_at": created,
            "updated_at": created + timedelta(days=random.uniform(0, 20)),
        })

    pairs = list(PAIR_BASE_PRICE)
    for _ in range(N_ORDERS):
        pair = random.choice(pairs)
        price = jitter(PAIR_BASE_PRICE[pair])
        qty = round(random.uniform(0.0001, 5), 8)
        status = random.choices(
            ["filled", "partially_filled", "open", "cancelled"],
            weights=[0.55, 0.15, 0.2, 0.1],
        )[0]
        filled = qty if status == "filled" else (
            round(qty * random.uniform(0.1, 0.9), 8)
            if status == "partially_filled" else 0.0
        )
        created = ts(0, 30, now)
        orders.append({
            "order_id": uid(), "user_id": random.choice(user_ids),
            "pair": pair,
            "order_type": random.choice(["limit", "limit", "limit", "market"]),
            "price": price, "quantity": qty, "filled_quantity": filled,
            "status": status, "created_at": created,
            "updated_at": created + timedelta(hours=random.uniform(0, 48)),
        })

    fillable = [o for o in orders if o["status"] in ("filled", "partially_filled")]
    for _ in range(N_TRADES):
        order = random.choice(fillable)
        qty = round(order["filled_quantity"] * random.uniform(0.1, 1.0), 8)
        executed = order["created_at"] + timedelta(hours=random.uniform(0, 24))
        trades.append({
            "trade_id": uid(), "order_id": order["order_id"],
            "price": jitter(order["price"], 0.002), "quantity": qty,
            "taker_side": random.choice(["buy", "sell"]),
            "executed_at": executed,
        })

    account_ids = [a["account_id"] for a in accounts]
    for _ in range(N_TRANSACTIONS):
        transactions.append({
            "transaction_id": uid(),
            "account_id": random.choice(account_ids),
            "amount": round(random.uniform(-50_000_000, 200_000_000), 8),
            "type": random.choice(["deposit", "withdrawal", "buy", "sell", "fee"]),
            "status": random.choices(
                ["completed", "pending", "failed"],
                weights=[0.9, 0.07, 0.03],
            )[0],
            "created_at": ts(0, 60, now),
        })

    watermarks = [
        ("postgresql.users", "postgres", min(u["updated_at"] for u in users)),
        ("postgresql.accounts", "postgres", min(a["updated_at"] for a in accounts)),
        ("postgresql.assets", "postgres", min(a["created_at"] for a in assets)),
        ("postgresql.orders", "postgres", min(o["updated_at"] for o in orders)),
        ("postgresql.trades", "postgres", min(t["executed_at"] for t in trades)),
        ("postgresql.transactions", "postgres", min(t["created_at"] for t in transactions)),
        ("mongodb.tickers", "mongodb", now - timedelta(days=8)),
        ("mongodb.orderbooks", "mongodb", now - timedelta(days=8)),
        ("mongodb.user_events", "mongodb", now - timedelta(days=8)),
    ]

    return {
        "assets": assets, "users": users, "accounts": accounts,
        "orders": orders, "trades": trades,
        "transactions": transactions, "watermarks": watermarks,
    }


def insert_sql(table: str, columns: list, rows: list) -> str:
    chunks, out = 500, []
    for i in range(0, len(rows), chunks):
        values = ",\n".join(
            "(" + ", ".join(row[c] for c in columns) + ")"
            for row in rows[i:i + chunks]
        )
        out.append(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n"
            f"{values}\nON CONFLICT DO NOTHING;"
        )
    return "\n".join(out)


def to_sql(data: dict) -> str:
    fmt = lambda rows, mapping: [
        {c: mapping[c](r) for c in mapping} for r in rows
    ]
    parts = ["""CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, name TEXT NOT NULL,
    precision INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL, is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
    currency TEXT NOT NULL, balance DECIMAL(18,8) NOT NULL,
    locked_balance DECIMAL(18,8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
    pair TEXT NOT NULL, order_type TEXT NOT NULL, price DECIMAL(18,8) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL, filled_quantity DECIMAL(18,8) NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
    price DECIMAL(18,8) NOT NULL, quantity DECIMAL(18,8) NOT NULL,
    taker_side TEXT NOT NULL, executed_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    amount DECIMAL(18,8) NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS etl_watermark (
    namespace TEXT NOT NULL PRIMARY KEY, source TEXT NOT NULL,
    last_watermark TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_users_updated_at ON users(updated_at);
CREATE INDEX IF NOT EXISTS idx_accounts_updated_at ON accounts(updated_at);
CREATE INDEX IF NOT EXISTS idx_orders_updated_at ON orders(updated_at);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);"""]

    parts.append(insert_sql("assets",
        ["asset_id", "symbol", "name", "precision", "created_at"],
        fmt(data["assets"], {"asset_id": lambda r: q(r["asset_id"]),
            "symbol": lambda r: q(r["symbol"]), "name": lambda r: q(r["name"]),
            "precision": lambda r: str(r["precision"]),
            "created_at": lambda r: fts(r["created_at"])})))
    parts.append(insert_sql("users",
        ["user_id", "email", "full_name", "is_active", "created_at", "updated_at"],
        fmt(data["users"], {"user_id": lambda r: q(r["user_id"]),
            "email": lambda r: q(r["email"]),
            "full_name": lambda r: q(r["full_name"]),
            "is_active": lambda r: "TRUE" if r["is_active"] else "FALSE",
            "created_at": lambda r: fts(r["created_at"]),
            "updated_at": lambda r: fts(r["updated_at"])})))
    parts.append(insert_sql("accounts",
        ["account_id", "user_id", "currency", "balance", "locked_balance",
         "created_at", "updated_at"],
        fmt(data["accounts"], {"account_id": lambda r: q(r["account_id"]),
            "user_id": lambda r: q(r["user_id"]),
            "currency": lambda r: q(r["currency"]),
            "balance": lambda r: f"{r['balance']:.8f}",
            "locked_balance": lambda r: f"{r['locked_balance']:.8f}",
            "created_at": lambda r: fts(r["created_at"]),
            "updated_at": lambda r: fts(r["updated_at"])})))
    parts.append(insert_sql("orders",
        ["order_id", "user_id", "pair", "order_type", "price", "quantity",
         "filled_quantity", "status", "created_at", "updated_at"],
        fmt(data["orders"], {"order_id": lambda r: q(r["order_id"]),
            "user_id": lambda r: q(r["user_id"]), "pair": lambda r: q(r["pair"]),
            "order_type": lambda r: q(r["order_type"]),
            "price": lambda r: f"{r['price']:.8f}",
            "quantity": lambda r: f"{r['quantity']:.8f}",
            "filled_quantity": lambda r: f"{r['filled_quantity']:.8f}",
            "status": lambda r: q(r["status"]),
            "created_at": lambda r: fts(r["created_at"]),
            "updated_at": lambda r: fts(r["updated_at"])})))
    parts.append(insert_sql("trades",
        ["trade_id", "order_id", "price", "quantity", "taker_side", "executed_at"],
        fmt(data["trades"], {"trade_id": lambda r: q(r["trade_id"]),
            "order_id": lambda r: q(r["order_id"]),
            "price": lambda r: f"{r['price']:.8f}",
            "quantity": lambda r: f"{r['quantity']:.8f}",
            "taker_side": lambda r: q(r["taker_side"]),
            "executed_at": lambda r: fts(r["executed_at"])})))
    parts.append(insert_sql("transactions",
        ["transaction_id", "account_id", "amount", "type", "status", "created_at"],
        fmt(data["transactions"], {
            "transaction_id": lambda r: q(r["transaction_id"]),
            "account_id": lambda r: q(r["account_id"]),
            "amount": lambda r: f"{r['amount']:.8f}",
            "type": lambda r: q(r["type"]), "status": lambda r: q(r["status"]),
            "created_at": lambda r: fts(r["created_at"])})))
    wm_rows = [
        {"namespace": q(ns), "source": q(src),
         "last_watermark": fts(wm), "updated_at": fts(datetime.now(timezone.utc))}
        for ns, src, wm in data["watermarks"]
    ]
    chunks = []
    for i in range(0, len(wm_rows), 500):
        values = ",\n".join(
            f"({r['namespace']}, {r['source']}, {r['last_watermark']}, {r['updated_at']})"
            for r in wm_rows[i:i + 500]
        )
        chunks.append(
            "INSERT INTO etl_watermark (namespace, source, last_watermark, updated_at)"
            f" VALUES\n{values}\nON CONFLICT (namespace) DO UPDATE SET "
            "last_watermark = EXCLUDED.last_watermark, "
            "updated_at = EXCLUDED.updated_at;"
        )
    parts.append("\n".join(chunks))
    return "\n\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic PostgreSQL data.")
    parser.add_argument("--execute", action="store_true",
                        help="Insert directly instead of writing SQL.")
    parser.add_argument("--dsn", default="",
                        help="Postgres DSN for --execute.")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    data = generate(now)

    if args.execute:
        if not args.dsn:
            raise SystemExit("--execute needs --dsn")
        import psycopg2
        conn = psycopg2.connect(args.dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(to_sql(data))
        conn.close()
    else:
        OUT_SQL.write_text(to_sql(data), encoding="utf-8")

    OUT_IDS.write_text(json.dumps({
        "generated_at": now.isoformat(),
        "user_ids": [u["user_id"] for u in data["users"]],
        "account_ids": [a["account_id"] for a in data["accounts"]],
        "order_ids": [o["order_id"] for o in data["orders"]],
        "pairs": sorted(PAIR_BASE_PRICE),
    }, indent=2), encoding="utf-8")

    print(f"users={len(data['users'])} accounts={len(data['accounts'])} "
          f"assets={len(data['assets'])} orders={len(data['orders'])} "
          f"trades={len(data['trades'])} transactions={len(data['transactions'])}")
    if not args.execute:
        print(f"wrote {OUT_SQL} + {OUT_IDS}")


if __name__ == "__main__":
    main()
