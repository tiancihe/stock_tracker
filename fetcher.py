import baostock as bs
import pandas as pd
import requests
from datetime import datetime, timedelta

EM_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _bs_login():
    lg = bs.login()
    if lg.error_code != "0":
        raise Exception(f"baostock login failed: {lg.error_msg}")


def fetch_daily_hist(stock_code, start_date, end_date, stock_name=""):
    try:
        _bs_login()
        bs_code = f"sh.{stock_code}" if stock_code.startswith("6") else f"sz.{stock_code}"
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,close,high,low,volume,amount,pctChg,turn",
            start_date=start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
            end_date=end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:],
            frequency="d",
            adjustflag="2",
        )
        rows = []
        while rs.next():
            r = rs.get_row_data()
            if not r or not r[0]:
                continue
            rows.append((
                r[0].replace("-", ""),
                stock_code,
                stock_name,
                float(r[1]),
                float(r[2]),
                float(r[3]),
                float(r[4]),
                float(r[5]),
                float(r[6]),
                float(r[7]),
                float(r[8]),
            ))
        bs.logout()
        return rows
    except Exception as e:
        print(f"  [WARN] fetch_daily_hist: {e}")
        try:
            bs.logout()
        except:
            pass
        return []


def fetch_fund_flow(stock_code):
    try:
        market = 1 if stock_code.startswith("6") else 0
        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
            f"?secid={market}.{stock_code}"
            f"&fields1=f1,f2,f3,f7"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
            f"&lmt=0&klt=101"
        )
        r = requests.get(url, headers=EM_HEADERS, timeout=15)
        data = r.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            raise Exception("empty response")
        rows = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 13:
                continue
            rows.append((
                parts[0].replace("-", ""),
                stock_code,
                float(parts[11]),
                float(parts[12]),
                float(parts[1]),
                float(parts[6]),
                float(parts[5]),
                float(parts[10]),
                float(parts[4]),
                float(parts[9]),
                float(parts[3]),
                float(parts[8]),
                float(parts[2]),
                float(parts[7]),
            ))
        return rows
    except Exception:
        print(f"  direct API failed, trying cloakbrowser...")
        from cloak_fetcher import fetch_fund_flow_via_cloak
        return fetch_fund_flow_via_cloak(stock_code)


def _fetch_margin_from_web(stock_code):
    try:
        url = f"https://data.eastmoney.com/rzrq/{stock_code}.html"
        r = requests.get(url, headers=EM_HEADERS, timeout=15)
        r.encoding = "utf-8"

        import re
        import json

        pattern = r'"data":\s*(\[.*?\]),?\s*"options"'
        match = re.search(pattern, r.text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            rows = []
            for item in data:
                date_str = item.get("DATE", "")
                if date_str:
                    date_str = date_str[:10].replace("-", "")
                rows.append((
                    date_str,
                    stock_code,
                    float(item.get("RZ_JYE", item.get("RZYE", 0))),
                    float(item.get("RZ_MRE", item.get("RZMRJE", 0))),
                    float(item.get("RZ_CHE", item.get("RZCHJE", 0))),
                ))
            return rows
        return []
    except Exception as e:
        print(f"  [WARN] fetch_margin: {e}")
        return []


def fetch_margin_data(stock_code, dates):
    rows = _fetch_margin_from_web(stock_code)
    if not rows:
        print(f"  direct margin API failed, trying cloakbrowser...")
        try:
            from cloak_fetcher import fetch_margin_via_cloak
            rows = fetch_margin_via_cloak(stock_code)
        except Exception as e:
            print(f"  [WARN] fetch_margin_via_cloak: {e}")
    return rows


def fetch_intraday_minutes(stock_code, trade_date):
    try:
        _bs_login()
        bs_code = f"sh.{stock_code}" if stock_code.startswith("6") else f"sz.{stock_code}"
        date_fmt = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,time,volume,amount",
            start_date=date_fmt,
            end_date=date_fmt,
            frequency="5",
            adjustflag="2",
        )
        morning_vol = 0.0
        morning_amt = 0.0
        afternoon_vol = 0.0
        afternoon_amt = 0.0

        found = False
        while rs.next():
            r = rs.get_row_data()
            if not r or not r[0]:
                continue
            found = True
            time_str = r[1] if len(r) > 1 else ""
            hour = int(time_str[8:10]) if len(time_str) >= 12 else 12
            vol = float(r[2]) if r[2] else 0
            amt = float(r[3]) if r[3] else 0
            if hour < 12:
                morning_vol += vol
                morning_amt += amt
            else:
                afternoon_vol += vol
                afternoon_amt += amt

        bs.logout()
        if not found:
            return None
        return (trade_date, stock_code, morning_vol, morning_amt, afternoon_vol, afternoon_amt)
    except Exception as e:
        print(f"  [WARN] fetch_intraday_minutes for {trade_date}: {e}")
        try:
            bs.logout()
        except:
            pass
        return None


def fetch_hourly_breakdown(stock_code, trade_date):
    try:
        _bs_login()
        bs_code = f"sh.{stock_code}" if stock_code.startswith("6") else f"sz.{stock_code}"
        date_fmt = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,time,volume,amount",
            start_date=date_fmt,
            end_date=date_fmt,
            frequency="5",
            adjustflag="2",
        )
        hourly = {}
        found = False
        while rs.next():
            r = rs.get_row_data()
            if not r or not r[0]:
                continue
            found = True
            time_str = r[1] if len(r) > 1 else ""
            hour = int(time_str[8:10]) if len(time_str) >= 12 else 12
            vol = float(r[2]) if r[2] else 0
            amt = float(r[3]) if r[3] else 0
            if hour not in hourly:
                hourly[hour] = [0.0, 0.0]
            hourly[hour][0] += vol
            hourly[hour][1] += amt
        bs.logout()
        if not found or not hourly:
            return None
        sorted_hours = sorted(hourly.keys())
        return [(trade_date, stock_code, h, hourly[h][0], hourly[h][1]) for h in sorted_hours]
    except Exception as e:
        print(f"  [WARN] fetch_hourly_breakdown for {trade_date}: {e}")
        try:
            bs.logout()
        except:
            pass
        return None
