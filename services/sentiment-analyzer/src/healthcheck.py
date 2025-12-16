#!/usr/bin/env python3
"""
Health Check para Sentiment Analyzer Service
"""

import sys
import requests
import os

def main():
    try:
        port = os.getenv("HTTP_PORT", "8000")
        url = f"http://localhost:{port}/health"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print("✅ Sentiment Analyzer is healthy")
                sys.exit(0)
            else:
                print(f"❌ Sentiment Analyzer unhealthy: {data}")
                sys.exit(1)
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check request failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Health check error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
