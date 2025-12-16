#!/usr/bin/env python3
"""
PASSO 27.4: WFO Prometheus Metrics Exporter
=============================================

Expõe métricas de Walk-Forward Optimization para Prometheus/Grafana.

Métricas expostas:
- wfo_return_percent: Retorno percentual do último WFO
- wfo_sharpe_ratio: Sharpe ratio do último WFO
- wfo_max_drawdown_percent: Max drawdown do último WFO
- wfo_win_rate_percent: Win rate do último WFO
- wfo_total_trades: Total de trades do último WFO
- wfo_robustness_score: Score de robustez (0-100)
- wfo_runs_total: Total de execuções WFO
- wfo_last_run_timestamp: Timestamp da última execução

Uso:
    python3 monitoring/wfo_exporter.py --port 9090
    
    # Ou via Docker
    docker run -p 9090:9090 -v $(pwd)/logs/wfo:/app/logs/wfo wfo-exporter
"""

import time
import csv
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional


class WFOMetrics:
    """Extrai métricas do CSV do WFO"""
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.last_metrics = {}
        self.total_runs = 0
        self.update_metrics()
    
    def update_metrics(self):
        """Atualiza métricas lendo o CSV"""
        if not self.csv_path.exists():
            return
        
        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                if not rows:
                    return
                
                self.total_runs = len(rows)
                
                # Última execução
                last = rows[-1]
                
                self.last_metrics = {
                    'return_pct': float(last.get('return', 0)),
                    'sharpe': float(last.get('sharpe', 0)),
                    'max_dd': float(last.get('max_dd', 0)),
                    'win_rate': float(last.get('win_rate', 0)),
                    'trades': int(last.get('trades', 0)),
                    'date': last.get('date', ''),
                }
                
                # Calcular robustness score (heurística simples)
                score = 50  # baseline
                
                if self.last_metrics['return_pct'] > 2:
                    score += 20
                elif self.last_metrics['return_pct'] > 0:
                    score += 10
                elif self.last_metrics['return_pct'] < -5:
                    score -= 30
                elif self.last_metrics['return_pct'] < 0:
                    score -= 10
                
                if self.last_metrics['sharpe'] > 1.5:
                    score += 20
                elif self.last_metrics['sharpe'] > 0.5:
                    score += 10
                elif self.last_metrics['sharpe'] < -0.5:
                    score -= 20
                
                if self.last_metrics['win_rate'] > 60:
                    score += 10
                elif self.last_metrics['win_rate'] < 40:
                    score -= 10
                
                self.last_metrics['robustness_score'] = max(0, min(100, score))
                
        except Exception as e:
            print(f"⚠️  Erro ao ler CSV: {e}")
    
    def to_prometheus(self) -> str:
        """Converte métricas para formato Prometheus"""
        if not self.last_metrics:
            return "# No metrics available\n"
        
        lines = [
            "# HELP wfo_return_percent Last WFO return percentage",
            "# TYPE wfo_return_percent gauge",
            f"wfo_return_percent {self.last_metrics['return_pct']:.2f}",
            "",
            "# HELP wfo_sharpe_ratio Last WFO Sharpe ratio",
            "# TYPE wfo_sharpe_ratio gauge",
            f"wfo_sharpe_ratio {self.last_metrics['sharpe']:.2f}",
            "",
            "# HELP wfo_max_drawdown_percent Last WFO max drawdown percentage",
            "# TYPE wfo_max_drawdown_percent gauge",
            f"wfo_max_drawdown_percent {self.last_metrics['max_dd']:.2f}",
            "",
            "# HELP wfo_win_rate_percent Last WFO win rate percentage",
            "# TYPE wfo_win_rate_percent gauge",
            f"wfo_win_rate_percent {self.last_metrics['win_rate']:.2f}",
            "",
            "# HELP wfo_total_trades Last WFO total trades",
            "# TYPE wfo_total_trades gauge",
            f"wfo_total_trades {self.last_metrics['trades']}",
            "",
            "# HELP wfo_robustness_score WFO robustness score (0-100)",
            "# TYPE wfo_robustness_score gauge",
            f"wfo_robustness_score {self.last_metrics['robustness_score']}",
            "",
            "# HELP wfo_runs_total Total number of WFO runs",
            "# TYPE wfo_runs_total counter",
            f"wfo_runs_total {self.total_runs}",
            "",
            "# HELP wfo_last_run_timestamp Timestamp of last WFO run",
            "# TYPE wfo_last_run_timestamp gauge",
            f"wfo_last_run_timestamp {int(time.time())}",
            "",
        ]
        
        return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler para expor métricas"""
    
    metrics: Optional[WFOMetrics] = None
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/metrics':
            # Atualizar métricas antes de servir
            if self.metrics:
                self.metrics.update_metrics()
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; version=0.0.4')
                self.end_headers()
                
                output = self.metrics.to_prometheus()
                self.wfile.write(output.encode())
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Metrics not initialized\n")
        
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK\n")
        
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <html>
            <head><title>WFO Metrics Exporter</title></head>
            <body>
                <h1>WFO Prometheus Metrics Exporter</h1>
                <p>PASSO 27.4 - Walk-Forward Optimization Monitoring</p>
                <ul>
                    <li><a href="/metrics">Metrics</a> (Prometheus format)</li>
                    <li><a href="/health">Health Check</a></li>
                </ul>
                <hr>
                <p>Grafana Dashboard: <a href="http://localhost:3000">http://localhost:3000</a></p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found\n")
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def run_server(csv_path: Path, port: int = 9090):
    """Inicia servidor HTTP de métricas"""
    
    print("="*80)
    print("📊 WFO PROMETHEUS METRICS EXPORTER - PASSO 27.4")
    print("="*80)
    print(f"\n📁 CSV Path: {csv_path}")
    print(f"🌐 Server: http://localhost:{port}")
    print(f"📈 Metrics: http://localhost:{port}/metrics")
    print(f"💚 Health: http://localhost:{port}/health")
    print("\n⚙️  Configurar Prometheus para scrape:")
    print(f"   - job_name: 'wfo_metrics'")
    print(f"     static_configs:")
    print(f"       - targets: ['localhost:{port}']")
    print("\n✅ Server running. Press Ctrl+C to stop.")
    print("="*80 + "\n")
    
    # Inicializar métricas
    metrics = WFOMetrics(csv_path)
    MetricsHandler.metrics = metrics
    
    # Criar servidor
    server = HTTPServer(('', port), MetricsHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⚠️  Server stopping...")
        server.shutdown()
        print("✅ Server stopped")


def main():
    parser = argparse.ArgumentParser(description="WFO Prometheus Metrics Exporter")
    parser.add_argument('--csv', default='logs/wfo/history.csv', help='Path to WFO CSV history')
    parser.add_argument('--port', type=int, default=9090, help='HTTP server port (default: 9090)')
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv)
    
    if not csv_path.exists():
        print(f"⚠️  CSV não encontrado: {csv_path}")
        print(f"💡 Execute primeiro: bash scripts/wfo_simple.sh")
        return 1
    
    run_server(csv_path, args.port)
    return 0


if __name__ == "__main__":
    exit(main())
