from datetime import datetime, timedelta
from config import STOCKS, FETCH_DAYS
from database import init_db, get_existing_dates, upsert_daily, upsert_fund_flow, upsert_margin, upsert_intraday
from fetcher import fetch_daily_hist, fetch_fund_flow, fetch_margin_data, fetch_intraday_minutes


def collect_all():
    init_db()
    today = datetime.now()
    start_date = (today - timedelta(days=FETCH_DAYS)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    for code, name in STOCKS.items():
        print(f"[{code} {name}] 开始采集...")

        existing_daily = get_existing_dates("daily_data", code)
        existing_fund = get_existing_dates("fund_flow", code)
        existing_margin = get_existing_dates("margin_data", code)
        existing_intra = get_existing_dates("intraday_data", code)

        print(f"  采集日K线数据...")
        daily_rows = fetch_daily_hist(code, start_date, end_date, name)
        new_daily = [r for r in daily_rows if r[0] not in existing_daily]
        if new_daily:
            upsert_daily(new_daily)
            print(f"  新增/更新 {len(new_daily)} 条日K线数据")
        else:
            print(f"  日K线数据已是最新")

        print(f"  采集资金流向数据...")
        fund_rows = fetch_fund_flow(code)
        new_fund = [r for r in fund_rows if r[0] not in existing_fund]
        if new_fund:
            upsert_fund_flow(new_fund)
            print(f"  新增/更新 {len(new_fund)} 条资金流向数据")
        else:
            print(f"  资金流向数据已是最新")

        print(f"  采集融资融券数据...")
        all_dates_in_range = set()
        d = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        while d <= end:
            if d.weekday() < 5:
                all_dates_in_range.add(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
        missing_dates = sorted(all_dates_in_range - existing_margin)
        if missing_dates:
            margin_rows = fetch_margin_data(code, missing_dates)
            if margin_rows:
                upsert_margin(margin_rows)
                print(f"  新增 {len(margin_rows)} 条融资融券数据")
        else:
            print(f"  融资融券数据已是最新")

        print(f"  采集日内分钟数据(用于上下午拆分)...")
        missing_intra = sorted(all_dates_in_range - existing_intra)
        if missing_intra:
            intra_count = 0
            for td in missing_intra[-10:]:
                result = fetch_intraday_minutes(code, td)
                if result:
                    upsert_intraday([result])
                    intra_count += 1
            if intra_count:
                print(f"  新增 {intra_count} 条日内数据")
            else:
                print(f"  无新增日内数据")
        else:
            print(f"  日内数据已是最新")

        print(f"[{code} {name}] 采集完成")


if __name__ == "__main__":
    collect_all()
