import sqlite3
import os
from config import DB_PATH


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_data (
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                turnover_rate REAL,
                PRIMARY KEY (date, stock_code)
            );

            CREATE TABLE IF NOT EXISTS fund_flow (
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                close REAL,
                change_pct REAL,
                main_net_flow REAL,
                main_net_flow_pct REAL,
                super_large_net_flow REAL,
                super_large_net_flow_pct REAL,
                large_net_flow REAL,
                large_net_flow_pct REAL,
                medium_net_flow REAL,
                medium_net_flow_pct REAL,
                small_net_flow REAL,
                small_net_flow_pct REAL,
                PRIMARY KEY (date, stock_code)
            );

            CREATE TABLE IF NOT EXISTS margin_data (
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                margin_balance REAL,
                margin_buy REAL,
                margin_sell REAL,
                PRIMARY KEY (date, stock_code)
            );

            CREATE TABLE IF NOT EXISTS intraday_data (
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                morning_volume REAL,
                morning_amount REAL,
                afternoon_volume REAL,
                afternoon_amount REAL,
                PRIMARY KEY (date, stock_code)
            );
        """)


def upsert_daily(rows):
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO daily_data
            (date, stock_code, stock_name, open, close, high, low, volume, amount, change_pct, turnover_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)


def upsert_fund_flow(rows):
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO fund_flow
            (date, stock_code, close, change_pct,
             main_net_flow, main_net_flow_pct,
             super_large_net_flow, super_large_net_flow_pct,
             large_net_flow, large_net_flow_pct,
             medium_net_flow, medium_net_flow_pct,
             small_net_flow, small_net_flow_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)


def upsert_margin(rows):
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO margin_data
            (date, stock_code, margin_balance, margin_buy, margin_sell)
            VALUES (?, ?, ?, ?, ?)
        """, rows)


def upsert_intraday(rows):
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO intraday_data
            (date, stock_code, morning_volume, morning_amount, afternoon_volume, afternoon_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rows)


def get_existing_dates(table, stock_code):
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT date FROM {table} WHERE stock_code = ? ORDER BY date",
            (stock_code,)
        ).fetchall()
        return {r["date"] for r in rows}


def query_daily(stock_code, start_date=None, end_date=None):
    with get_conn() as conn:
        sql = "SELECT * FROM daily_data WHERE stock_code = ?"
        params = [stock_code]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date"
        return conn.execute(sql, params).fetchall()


def query_fund_flow(stock_code, start_date=None, end_date=None):
    with get_conn() as conn:
        sql = "SELECT * FROM fund_flow WHERE stock_code = ?"
        params = [stock_code]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date"
        return conn.execute(sql, params).fetchall()


def query_margin(stock_code, start_date=None, end_date=None):
    with get_conn() as conn:
        sql = "SELECT * FROM margin_data WHERE stock_code = ?"
        params = [stock_code]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date"
        return conn.execute(sql, params).fetchall()


def query_intraday(stock_code, start_date=None, end_date=None):
    with get_conn() as conn:
        sql = "SELECT * FROM intraday_data WHERE stock_code = ?"
        params = [stock_code]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date"
        return conn.execute(sql, params).fetchall()
