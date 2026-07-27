from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import json


def create_cloak_driver(headless=True):
    options = Options()
    options.binary_location = r"C:\Users\tianc\.cloakbrowser\chromium-146.0.7680.177.5\chrome.exe"
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.page_load_strategy = "eager"

    service = webdriver.ChromeService(
        executable_path=r"C:\Users\tianc\.cloakbrowser\chromium-146.0.7680.177.5\chromedriver.exe"
    )
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
