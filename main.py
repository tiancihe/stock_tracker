import sys
import os
import signal
import argparse
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)


def run_dashboard(port=8501, headless=False):
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "0"
    os.environ["BROWSER"] = "none"

    sys.argv = [
        "streamlit",
        "run",
        os.path.join(BASE_DIR, "dashboard.py"),
        f"--server.port={port}",
        "--server.address=0.0.0.0",
    ]
    if headless:
        sys.argv.append("--server.headless=true")

    from streamlit.web import cli as stcli
    try:
        stcli.main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"Error: {e}")

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            break


def run_collector():
    from collector import collect_all
    print("Collecting data...")
    collect_all()
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Stock Tracker")
    parser.add_argument("action", nargs="?", default="dashboard",
                        choices=["dashboard", "collect", "both"],
                        help="Action to perform")
    parser.add_argument("--port", type=int, default=8501, help="Dashboard port")
    parser.add_argument("--headless", action="store_true", help="Run without browser")
    args = parser.parse_args()

    if args.action in ("collect", "both"):
        run_collector()

    if args.action in ("dashboard", "both"):
        run_dashboard(port=args.port, headless=args.headless)


if __name__ == "__main__":
    main()
