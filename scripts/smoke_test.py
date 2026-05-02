import sys

import requests


BASE_URL = "http://127.0.0.1:8000"
ENDPOINTS = [
    "/health",
    "/decision/BTCUSDT",
    "/feed?symbols=BTCUSDT,ETHUSDT",
    "/tracking-summary",
    "/performance-analytics",
]


def main() -> int:
    failed = False

    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, timeout=30)
        except requests.RequestException as error:
            print(f"ERROR {endpoint}: {error}")
            failed = True
            continue

        if response.status_code != 200:
            print(f"ERROR {endpoint}: status {response.status_code}")
            failed = True

    if failed:
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
