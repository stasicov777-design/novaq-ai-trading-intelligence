import os
import sys

import requests


BASE_URL = "http://127.0.0.1:8000"
PUBLIC_ENDPOINTS = [
    "/",
    "/api",
    "/health",
    "/feedback",
    "/decision/BTCUSDT",
    "/feed?symbols=BTCUSDT,ETHUSDT",
]

PROTECTED_ENDPOINTS = [
    "/tracking-summary",
    "/performance-analytics",
    "/api/feedback-summary",
    "/api/feedback",
]


def main() -> int:
    failed = False

    for endpoint in PUBLIC_ENDPOINTS:
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
            continue

        if endpoint == "/api":
            try:
                data = response.json()
            except ValueError:
                print("ERROR /api: invalid JSON")
                failed = True
                continue

            print(f"Storage backend: {data.get('storage_backend', 'unknown')}")

    for endpoint in ["/login"]:
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

    for endpoint in PROTECTED_ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, timeout=30)
        except requests.RequestException as error:
            print(f"ERROR {endpoint}: {error}")
            failed = True
            continue

        if response.status_code != 401:
            print(f"ERROR {endpoint}: expected 401 without code, got {response.status_code}")
            failed = True

    access_code = os.getenv("ACCESS_CODE", "novaq-demo-access")
    headers = {"X-Access-Code": access_code}

    for endpoint in PROTECTED_ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as error:
            print(f"ERROR {endpoint} with access code: {error}")
            failed = True
            continue

        if response.status_code != 200:
            print(f"ERROR {endpoint} with access code: status {response.status_code}")
            failed = True

    if failed:
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
