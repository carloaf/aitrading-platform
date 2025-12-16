#!/usr/bin/env node

/**
 * Script para testar otimizações do Meta-Backtest
 * Compara resultados ANTES vs DEPOIS das otimizações
 */

const tests = [
  {
    name: "Full Year 2025",
    start_date: "2025-01-10",
    end_date: "2025-12-11",
    baseline: { return_pct: 14.21, sharpe: 1.23, trades: 3 },
    target: { return_pct: 25, trades: 8 }
  },
  {
    name: "Feb-Mar 2025 Volatility",
    start_date: "2025-02-01",
    end_date: "2025-03-31",
    baseline: { return_pct: 0, sharpe: 0, trades: 0 },
    target: { return_pct: 5, trades: 2 }
  },
  {
    name: "ATH Period Jul-Oct 2025",
    start_date: "2025-07-01",
    end_date: "2025-10-31",
    baseline: { return_pct: 5.0, sharpe: 1.52, trades: 1 },
    target: { return_pct: 8, trades: 3 }
  },
  {
    name: "4-Year Cycle 2021-2024",
    start_date: "2021-01-01",
    end_date: "2024-12-31",
    baseline: { return_pct: 134.73, sharpe: 1.54, trades: 18 },
    target: { return_pct: 135, trades: 20 }
  }
];

async function runBacktest(test) {
  const response = await fetch('http://localhost:3008/api/meta-backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_date: test.start_date,
      end_date: test.end_date,
      symbol: 'BTC/USDT',
      initial_capital: 100000
    })
  });
  
  const result = await response.json();
  return result;
}

async function main() {
  console.log("═".repeat(80));
  console.log("OPTIMIZATION VALIDATION TESTS");
  console.log("Testing: SIDEWAYS detection, Trailing stops, High-vol filters, Re-entry logic");
  console.log("═".repeat(80));
  console.log("");
  
  for (const test of tests) {
    console.log(`\n${"─".repeat(80)}`);
    console.log(`📊 ${test.name}`);
    console.log(`${"─".repeat(80)}`);
    console.log(`Period: ${test.start_date} → ${test.end_date}`);
    console.log("");
    
    try {
      const result = await runBacktest(test);
      
      if (!result.success) {
        console.log("❌ FAILED:", result.error || "Unknown error");
        continue;
      }
      
      const actual = {
        return_pct: result.performance.total_return_pct || 0,
        sharpe: result.risk_metrics.sharpe_ratio || 0,
        trades: result.trade_stats.total_trades || 0,
        win_rate: result.trade_stats.win_rate || 0
      };
      
      console.log("BASELINE (Before Optimizations):");
      console.log(`  Return: ${test.baseline.return_pct.toFixed(2)}%`);
      console.log(`  Sharpe: ${test.baseline.sharpe.toFixed(2)}`);
      console.log(`  Trades: ${test.baseline.trades}`);
      console.log("");
      
      console.log("CURRENT (After Optimizations):");
      console.log(`  Return: ${actual.return_pct.toFixed(2)}%`);
      console.log(`  Sharpe: ${actual.sharpe.toFixed(2)}`);
      console.log(`  Trades: ${actual.trades}`);
      console.log(`  Win Rate: ${actual.win_rate.toFixed(1)}%`);
      console.log(`  Max DD: ${(result.performance.max_drawdown_pct || 0).toFixed(2)}%`);
      console.log("");
      
      console.log("TARGET:");
      console.log(`  Return: ${test.target.return_pct.toFixed(2)}%`);
      console.log(`  Trades: ${test.target.trades}`);
      console.log("");
      
      // Validação
      const return_improved = actual.return_pct >= test.baseline.return_pct;
      const trades_improved = actual.trades >= test.baseline.trades;
      const target_return_met = actual.return_pct >= test.target.return_pct;
      const target_trades_met = actual.trades >= test.target.trades;
      
      console.log("VALIDATION:");
      console.log(`  ${return_improved ? "✅" : "❌"} Return improved vs baseline`);
      console.log(`  ${trades_improved ? "✅" : "❌"} Trades improved vs baseline`);
      console.log(`  ${target_return_met ? "✅" : "⚠️ "} Target return ${target_return_met ? "met" : "not met"}`);
      console.log(`  ${target_trades_met ? "✅" : "⚠️ "} Target trades ${target_trades_met ? "met" : "not met"}`);
      
      if (result.adaptability) {
        console.log("");
        console.log("ADAPTABILITY:");
        console.log(`  Regime changes: ${result.adaptability.regime_changes}`);
        console.log(`  Strategy switches: ${result.adaptability.strategy_switches}`);
      }
      
    } catch (error) {
      console.log("❌ ERROR:", error.message);
    }
  }
  
  console.log("\n" + "═".repeat(80));
  console.log("SUMMARY");
  console.log("═".repeat(80));
  console.log("Optimizations implemented:");
  console.log("  1. ✅ SIDEWAYS/CONSOLIDATION detection (range > $15k + BB width)");
  console.log("  2. ✅ Trailing stops (highest_price - 2×ATR)");
  console.log("  3. ✅ High volatility filters (ATR% > 5% relaxes ADX, RSI, volume)");
  console.log("  4. ✅ Re-entry logic (BULL: 4h cooldown, max 2 stops, EMA crossover)");
  console.log("");
  console.log("Next steps:");
  console.log("  - If Feb-Mar 2025 still shows 0 trades: investigate regime detection");
  console.log("  - If performance degraded: may need to tune thresholds");
  console.log("  - Document final results in OPTIMIZATION_RESULTS.md");
  console.log("═".repeat(80));
}

main().catch(console.error);
