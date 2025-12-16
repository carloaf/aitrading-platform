#!/usr/bin/env python3
"""
Health Check para News Collector Service
"""

import sys
import requests
import json

def main():
    try:
        # Tentar conectar ao endpoint de health
        response = requests.get('http://localhost:8000/health', timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            
            # Verificar se o serviço está healthy
            if health_data.get('status') == 'healthy':
                print("✅ News Collector Service is healthy")
                sys.exit(0)
            else:
                print(f"❌ Service unhealthy: {health_data}")
                sys.exit(1)
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
