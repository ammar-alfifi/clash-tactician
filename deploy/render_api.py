#!/usr/bin/env python3
"""Minimal Render API client used to maintain the cloud deployment.

Usage:
    python3 deploy/render_api.py GET /services
    python3 deploy/render_api.py PUT /services/<serviceId>/env-vars body.json
    python3 deploy/render_api.py POST /services/<serviceId>/deploys body.json

The API key is read from the RENDER_API_KEY environment variable or from
~/.config/coc-bot/render_api_key (never stored inside this repository).
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.render.com/v1"


def load_api_key() -> str:
    key = os.getenv("RENDER_API_KEY", "").strip()
    if key:
        return key
    path = pathlib.Path.home() / ".config" / "coc-bot" / "render_api_key"
    if path.exists():
        key = path.read_text().strip()
    if not key:
        raise SystemExit(
            "Set RENDER_API_KEY or create ~/.config/coc-bot/render_api_key first."
        )
    return key


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    method, path = sys.argv[1].upper(), sys.argv[2]
    body = None
    if len(sys.argv) > 3:
        with open(sys.argv[3], encoding="utf-8") as handle:
            body = json.dumps(json.load(handle)).encode()

    request = urllib.request.Request(f"{BASE_URL}{path}", data=body, method=method)
    request.add_header("Authorization", f"Bearer {load_api_key()}")
    request.add_header("Accept", "application/json")
    if body:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            print(response.status)
            print(response.read().decode())
    except urllib.error.HTTPError as error:
        print(error.code)
        print(error.read().decode())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
