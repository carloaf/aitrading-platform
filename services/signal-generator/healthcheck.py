#!/usr/bin/env python3
import sys
import httpx
import json

def health_check():
    try:
        with httpx.Client() as client:
            response = client.get("http://localhost:8000/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            if health_data.get("status") == "healthy":
                print("✅ Signal Generator is healthy")
                return True
        
        print(f"❌ Health check failed: {response.status_code}")
        return False
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    if health_check():
        sys.exit(0)
    else:
        sys.exit(1)
