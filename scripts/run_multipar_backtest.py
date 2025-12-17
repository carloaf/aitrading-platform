#!/usr/bin/env python3
"""
Backtest RSI Divergence - Multi-Par + Multi-Timeframe
Executa diretamente dentro do container para maior performance
"""
import sys
import json
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

API_URL = "http://localhost:3008"

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"
]

TIMEFRAMES = ["1h", "4h", "1d"]

# Parâmetros otimizados por timeframe
PARAMS_BY_TF = {
    "1h": {
        "lookback_periods": 10,
        "min_adx_trend": 12,
        "min_signal_strength": 0.20,
        "stop_loss_atr_mult": 2.0,
        "take_profit_atr_mult": 4.0
    },
    "4h": {
        "lookback_periods": 15,
        "min_adx_trend": 15,
        "min_signal_strength": 0.25,
        "stop_loss_atr_mult": 2.5,
        "take_profit_atr_mult": 5.0
    },
    "1d": {
        "lookback_periods": 20,
        "min_adx_trend": 18,
        "min_signal_strength": 0.30,
        "stop_loss_atr_mult": 3.0,
        "take_profit_atr_mult": 6.0
    }
}

def run_backtest(symbol: str, timeframe: str, start_date: str, end_date: str) -> dict:
    """Executa backtest para um símbolo e timeframe"""
    params = PARAMS_BY_TF.get(timeframe, PARAMS_BY_TF["1h"])
    
    payload = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "timeframe": timeframe,
        "initial_capital": 10000,
        "risk_per_trade": 0.02,
        **params
    }
    
    try:
        response = requests.post(
            f"{API_URL}/api/backtest/rsi-divergence",
            json=payload,
            timeout=300
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", {})
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "return_pct": results.get("total_return_pct", 0),
                "sharpe": data.get("sharpe_ratio", 0),
                "max_dd": results.get("max_drawdown_pct", 0),
                "win_rate": results.get("win_rate", 0) * 100,
                "trades": results.get("total_trades", 0),
                "tp": results.get("exit_reasons", {}).get("TAKE_PROFIT", 0),
                "sl": results.get("exit_reasons", {}).get("STOP_LOSS", 0),
                "patterns": data.get("pattern_statistics", {}).get("total_patterns", 0),
                "success": True
            }
        else:
            return {"symbol": symbol, "timeframe": timeframe, "success": False, "error": response.text[:100]}
    except Exception as e:
        return {"symbol": symbol, "timeframe": timeframe, "success": False, "error": str(e)[:100]}

def print_table_header():
    print("\n" + "=" * 95)
    print(f"{'SYMBOL':<12} | {'RETURN':>8} | {'SHARPE':>7} | {'MAX DD':>7} | {'WIN RATE':>8} | {'TRADES':>6} | {'TP':>4} | {'SL':>4} | {'PATTERNS':>8}")
    print("-" * 95)

def print_result(r: dict):
    if r.get("success"):
        color = "\033[92m" if r["return_pct"] > 0 else "\033[91m"
        reset = "\033[0m"
        print(f"{r['symbol']:<12} | {color}{r['return_pct']:>7.2f}%{reset} | {r['sharpe']:>7.2f} | {r['max_dd']:>6.2f}% | {r['win_rate']:>7.1f}% | {r['trades']:>6} | {r['tp']:>4} | {r['sl']:>4} | {r['patterns']:>8}")
    else:
        print(f"{r['symbol']:<12} | {'ERROR':>8} | {'-':>7} | {'-':>7} | {'-':>8} | {'-':>6} | {'-':>4} | {'-':>4} | {r.get('error', 'Unknown')[:20]}")

def main():
    print("\n" + "╔" + "═" * 93 + "╗")
    print("║" + " BACKTEST RSI DIVERGENCE - MULTI-PAR + MULTI-TIMEFRAME ".center(93) + "║")
    print("║" + " Período: 2023-01-01 a 2024-12-15 (2 anos) ".center(93) + "║")
    print("╚" + "═" * 93 + "╝")
    
    start_date = "2023-01-01"
    end_date = "2024-12-15"
    
    all_results = []
    
    for tf in TIMEFRAMES:
        print(f"\n{'=' * 95}")
        print(f"  TIMEFRAME: {tf}")
        print_table_header()
        
        tf_results = []
        
        for symbol in SYMBOLS:
            print(f"  Testing {symbol} {tf}...", end="\r")
            result = run_backtest(symbol, tf, start_date, end_date)
            tf_results.append(result)
            print_result(result)
            time.sleep(0.3)  # Rate limiting
        
        # Calcular médias
        successful = [r for r in tf_results if r.get("success")]
        if successful:
            avg_return = sum(r["return_pct"] for r in successful) / len(successful)
            total_trades = sum(r["trades"] for r in successful)
            avg_winrate = sum(r["win_rate"] for r in successful) / len(successful)
            total_patterns = sum(r["patterns"] for r in successful)
            
            print("-" * 95)
            print(f"{'MÉDIA ' + tf:<12} | {avg_return:>7.2f}% | {'-':>7} | {'-':>7} | {avg_winrate:>7.1f}% | {total_trades:>6} | {'-':>4} | {'-':>4} | {total_patterns:>8}")
        
        all_results.extend(tf_results)
    
    # Resumo final
    print("\n" + "=" * 95)
    print("  RESUMO GERAL")
    print("=" * 95)
    
    successful = [r for r in all_results if r.get("success")]
    if successful:
        # Por timeframe
        for tf in TIMEFRAMES:
            tf_res = [r for r in successful if r["timeframe"] == tf]
            if tf_res:
                avg_ret = sum(r["return_pct"] for r in tf_res) / len(tf_res)
                avg_wr = sum(r["win_rate"] for r in tf_res) / len(tf_res)
                total_tr = sum(r["trades"] for r in tf_res)
                positivos = len([r for r in tf_res if r["return_pct"] > 0])
                print(f"  {tf}: Média {avg_ret:+.2f}% | WR {avg_wr:.1f}% | {total_tr} trades | {positivos}/{len(tf_res)} positivos")
        
        # Melhores por timeframe
        print("\n  🏆 TOP 3 POR TIMEFRAME:")
        for tf in TIMEFRAMES:
            tf_res = sorted([r for r in successful if r["timeframe"] == tf], key=lambda x: x["return_pct"], reverse=True)[:3]
            print(f"  {tf}: ", end="")
            for i, r in enumerate(tf_res):
                print(f"{i+1}.{r['symbol'].replace('USDT','')} ({r['return_pct']:+.1f}%) ", end="")
            print()
    
    # Salvar resultados em JSON
    output_file = f"/tmp/backtest_multipar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  📊 Resultados salvos em: {output_file}")
    print("=" * 95)

if __name__ == "__main__":
    main()
