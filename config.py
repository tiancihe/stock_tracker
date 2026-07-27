STOCKS = {
    "603986": "兆易创新",
}

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "stocks.db")

FETCH_DAYS = 60
