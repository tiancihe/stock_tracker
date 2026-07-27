import os
import sys
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

_CLOAK_DIR = os.environ.get("CLOAKBROWSER_DIR", "")
if not _CLOAK_DIR:
    if sys.platform == "win32":
        _CLOAK_DIR = os.path.expanduser(r"~\.cloakbrowser\chromium-146.0.7680.177.5")
    else:
        _CLOAK_DIR = os.path.expanduser("~/.cloakbrowser/chromium-146.0.7680.177.5")

_CHROME_BIN = os.environ.get(
    "CLOAKBROWSER_CHROME",
    os.path.join(_CLOAK_DIR, "chrome.exe" if sys.platform == "win32" else "chrome"),
)
_DRIVER_BIN = os.environ.get(
    "CLOAKBROWSER_DRIVER",
    os.path.join(_CLOAK_DIR, "chromedriver.exe" if sys.platform == "win32" else "chromedriver"),
)


def create_cloak_driver(headless=True):
    options = Options()
    if os.path.exists(_CHROME_BIN):
        options.binary_location = _CHROME_BIN
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.page_load_strategy = "eager"

    service = webdriver.ChromeService(executable_path=_DRIVER_BIN)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def fetch_json_via_browser(driver, url, timeout=15):
    result = driver.execute_script(f"""
        return new Promise((resolve, reject) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('GET', '{url}', true);
            xhr.withCredentials = true;
            xhr.onload = function() {{
                resolve({{status: xhr.status, text: xhr.responseText}});
            }};
            xhr.onerror = function() {{
                reject({{status: xhr.status, text: xhr.responseText}});
            }};
            xhr.timeout = {timeout * 1000};
            xhr.ontimeout = function() {{
                reject({{status: 0, text: 'timeout'}});
            }};
            xhr.send();
        }});
    """)
    return result


def fetch_fund_flow_via_cloak(stock_code):
    market = 1 if stock_code.startswith("6") else 0
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        f"?secid={market}.{stock_code}"
        f"&fields1=f1,f2,f3,f7"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
        f"&lmt=0&klt=101"
    )
    driver = None
    try:
        driver = create_cloak_driver()
        driver.get("https://data.eastmoney.com")
        time.sleep(2)

        result = fetch_json_via_browser(driver, url)
        if result["status"] != 200:
            print(f"  [WARN] fund flow API returned {result['status']}")
            return []

        text = result["text"]
        text = text[text.index("(")+1:text.rindex(")")] if text.startswith("jQuery") else text
        data = json.loads(text)
        klines = data.get("data", {}).get("klines", [])
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
    except Exception as e:
        print(f"  [WARN] fetch_fund_flow_via_cloak: {e}")
        return []
    finally:
        if driver:
            driver.quit()


def fetch_margin_via_cloak(stock_code):
    market = 1 if stock_code.startswith("6") else 0
    driver = None
    try:
        driver = create_cloak_driver()
        driver.get(f"https://data.eastmoney.com/rzrq/detail/{stock_code}.html")
        time.sleep(6)

        result = driver.execute_script("""
            const tables = document.querySelectorAll('table');
            const results = [];
            for (const table of tables) {
                const rows = table.querySelectorAll('tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 7) {
                        const date = cells[0].textContent.trim();
                        const balance = cells[3].textContent.trim().replace(/,/g, '');
                        const buy = cells[5].textContent.trim().replace(/,/g, '');
                        const sell = cells[6].textContent.trim().replace(/,/g, '');
                        if (date && /^\d/.test(date) && !isNaN(parseFloat(balance.replace(/[亿万元]/g, '')))) {
                            results.push({date, balance, buy, sell});
                        }
                    }
                }
            }
            return JSON.stringify(results);
        """)
        items = json.loads(result)
        rows = []
        for item in items:
            date_str = item["date"].replace("-", "")
            def parse_val(s):
                s = s.strip()
                mult = 1
                if "亿" in s:
                    mult = 1e8
                    s = s.replace("亿", "")
                elif "万" in s:
                    mult = 1e4
                    s = s.replace("万", "")
                return float(s) * mult
            rows.append((
                date_str,
                stock_code,
                parse_val(item["balance"]),
                parse_val(item["buy"]),
                parse_val(item["sell"]),
            ))
        return rows
    except Exception as e:
        print(f"  [WARN] fetch_margin_via_cloak: {e}")
        return []
    finally:
        if driver:
            driver.quit()


def fetch_fundamentals_via_cloak(stock_code):
    market = 1 if stock_code.startswith("6") else 0
    fields = (
        "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18,f20,f21,f31,f35,"
        "f37,f38,f39,f40,f43,f44,f45,f46,f47,f48,f49,f50,f52,f53,f54,"
        "f57,f58,f60,f62,f69,f84,f85,f86,f87,f100,f115,f116,f117,"
        "f161,f162,f167,f168,f169,f172,f175,f177,f198"
    )
    url = (
        f"https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={market}.{stock_code}"
        f"&fields={fields}"
    )
    driver = None
    try:
        driver = create_cloak_driver()
        driver.get("https://quote.eastmoney.com")
        time.sleep(2)
        result = fetch_json_via_browser(driver, url)
        if result["status"] != 200:
            print(f"  [WARN] fundamentals API returned {result['status']}")
            return {}
        text = result["text"]
        text = text[text.index("(")+1:text.rindex(")")] if text.startswith("jQuery") else text
        data = json.loads(text)
        return data.get("data", {})
    except Exception as e:
        print(f"  [WARN] fetch_fundamentals_via_cloak: {e}")
        return {}
    finally:
        if driver:
            driver.quit()
