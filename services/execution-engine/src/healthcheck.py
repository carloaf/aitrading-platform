#!/usr/bin/env python3
"""
Healthcheck para Execution Engine
Versão simplificada usando requests síncrono
"""
import sys
import requests

def check_health():
    try:
        resp = requests.get('http://localhost:8001/health', timeout=5)
        if resp.status_code == 200:
            print("OK")
            return 0
        else:
            print(f"FAIL: {resp.status_code}")
            return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(check_health())
