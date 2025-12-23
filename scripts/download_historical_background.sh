#!/bin/bash
# Script para baixar dados históricos de múltiplos símbolos em background

SYMBOLS="ADAUSDT,LINKUSDT,DOTUSDT,UNIUSDT,AAVEUSDT,ALGOUSDT,APTUSDT,ARBUSDT,ATOMUSDT,AVAXUSDT"
START_DATE="2021-01-01"
END_DATE="2024-12-31"
TIMEFRAMES="1h,4h,1d"

LOG_FILE="logs/download_historical_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "=================================================="
echo "INICIANDO DOWNLOAD HISTÓRICO EM BACKGROUND"
echo "=================================================="
echo "Símbolos: $SYMBOLS"
echo "Período: $START_DATE até $END_DATE"
echo "Timeframes: $TIMEFRAMES"
echo "Log: $LOG_FILE"
echo "=================================================="

# Executar em background
nohup docker exec aitrading-execution-engine python /app/src/download_historical_multi.py \
  --symbols "$SYMBOLS" \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --timeframes "$TIMEFRAMES" \
  > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ Processo iniciado (PID: $PID)"
echo "📊 Monitorar progresso: tail -f $LOG_FILE"
echo ""
echo "Para verificar status:"
echo "  ps aux | grep download_historical_multi"
echo ""
echo "Para parar:"
echo "  kill $PID"
