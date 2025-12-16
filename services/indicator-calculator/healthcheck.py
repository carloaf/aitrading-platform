#!/usr/bin/env python3
"""
Health check para Indicator Calculator Service
"""

import requests
import sys
import os

def main():
    try:
        # Tentar conectar na API REST
        port = os.getenv('HTTP_PORT', 8000)
        response = requests.get(f'http://127.0.0.1:{port}/health', timeout=2)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                print("Health check passed")
                sys.exit(0)
            else:
                print(f"Health check failed: {data.get('status')}")
                sys.exit(1)
        else:
            print(f"Health check failed with status: {response.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Health check error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
