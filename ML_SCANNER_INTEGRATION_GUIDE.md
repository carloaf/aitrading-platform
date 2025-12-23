# 🤖 ML Scanner Integration Guide - Machine Learning para Auto-Trade

**Data**: 22 de Dezembro de 2025  
**Status**: 📋 PLANEJAMENTO  
**Objetivo**: Integrar ML Signal Filter ao Scanner RSI Divergence e Auto-Trade

---

## 🎯 Visão Geral

O sistema já possui um **LightGBM classifier** implementado (PASSO 34) que pode:
1. **Filtrar sinais de baixa qualidade** antes da execução
2. **Ajustar position sizing** baseado em confiança do ML
3. **Melhorar win rate** rejeitando false positives

---

## 📊 Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────────┐
│  MultiSymbolScanner (RSI Divergence Detection)              │
│                                                               │
│  1. Detecta Divergência                                      │
│     └─> signal_strength: 0.65 (65%)                         │
│                                                               │
│  2. ML Filter Evaluation                                     │
│     ├─> Features: RSI=68, ADX=22, Volume=1.2x, ...         │
│     ├─> ML Score: 0.82 (82% confiança)                      │
│     └─> Decision: ✅ APROVAR (score >= 0.6)                 │
│                                                               │
│  3. Position Sizing Ajustado                                 │
│     ├─> Base Risk: 2%                                        │
│     ├─> ML Multiplier: 1.5x (high confidence)              │
│     └─> Final Risk: 3% (max allowed)                        │
│                                                               │
│  4. Auto-Execute Paper Trade                                 │
│     └─> Create trade with adjusted position                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementação Step-by-Step

### ETAPA 1: Adicionar ML Filter ao Scanner

**Arquivo**: `services/execution-engine/src/multi_symbol_scanner.py`

**Modificações**:

```python
# Linha 10: Import ML Filter
from ml_signal_filter import MLSignalFilter

class MultiSymbolScanner:
    def __init__(self, config: ScannerConfig = None, db_pool=None, auto_trade_enabled: bool = False):
        # ... código existente ...
        
        # NOVO: ML Filter
        self.ml_filter_enabled = False  # Opt-in
        self.ml_filter = None
        self.min_ml_score = 0.60  # 60% confiança mínima
        
        logger.info(f"MultiSymbolScanner initialized | ML Filter: {self.ml_filter_enabled}")
    
    async def initialize_ml_filter(self):
        """
        🤖 Inicializa e treina ML Filter com histórico de trades
        """
        try:
            self.ml_filter = MLSignalFilter()
            
            # Buscar histórico de trades do banco
            async with self.db_pool.acquire() as conn:
                trades = await conn.fetch("""
                    SELECT 
                        t.entry_price, t.exit_price, t.quantity,
                        t.side, t.status, t.pnl, t.signal_strength,
                        t.entry_time, t.exit_time,
                        s.rsi_current, s.price_current, s.signal_type,
                        s.timeframe, s.strength
                    FROM paper_trading_trades t
                    LEFT JOIN autotrade_signals s ON t.signal_id = s.signal_id
                    WHERE t.session_id LIKE 'auto_scanner_%'
                        AND t.status = 'CLOSED'
                        AND t.entry_time >= NOW() - INTERVAL '30 days'
                    ORDER BY t.entry_time DESC
                    LIMIT 500
                """)
            
            if len(trades) < 50:
                logger.warning(f"🤖 Not enough trades for ML training: {len(trades)} (need 50+)")
                return False
            
            # Preparar dados para treino
            training_data = []
            for trade in trades:
                # Determinar label (0=bad, 1=good)
                label = 1 if trade['pnl'] > 0 else 0
                
                training_data.append({
                    'entry_state': {
                        'close': trade['entry_price'],
                        'rsi': trade['rsi_current'],
                        'adx': 25.0,  # Placeholder (buscar do histórico)
                        'volume': 1000.0,  # Placeholder
                        'atr': abs(trade['entry_price'] * 0.02),  # Estimate
                    },
                    'strategy': 'rsi_divergence',
                    'signal_strength': trade['signal_strength'] or 0.5,
                    'setup_quality': 70.0,  # Placeholder
                    'regime': 'SIDEWAYS',  # Majority regime
                    'exit_reason': 'TAKE_PROFIT' if label == 1 else 'STOP_LOSS'
                })
            
            # Treinar modelo
            metrics = self.ml_filter.train(training_data, test_size=0.2, num_rounds=100)
            
            logger.info(f"🤖 ML Filter trained successfully!")
            logger.info(f"   Accuracy: {metrics['accuracy']:.2%}")
            logger.info(f"   Precision: {metrics['precision']:.2%}")
            logger.info(f"   Recall: {metrics['recall']:.2%}")
            logger.info(f"   AUC: {metrics['auc']:.2f}")
            
            self.ml_filter_enabled = True
            return True
            
        except Exception as e:
            logger.error(f"🤖 Error initializing ML Filter: {e}")
            return False
    
    async def _save_signal_to_db(self, signal: DivergenceSignal) -> str:
        """
        💾 Salva sinal no banco de dados e auto-executa se habilitado
        """
        # ... código existente até salvar no banco ...
        
        signal_id = await conn.fetchval(...)
        logger.info(f"💾 Signal saved to DB: {signal_id}")
        
        # 🤖 ML FILTER: Avaliar sinal antes de executar
        ml_score = 0.5  # Default (no filter)
        ml_approved = True
        
        if self.ml_filter_enabled and self.ml_filter:
            try:
                # Extrair features do sinal
                candle_data = {
                    'close': signal.price_current,
                    'rsi': signal.rsi_current,
                    'adx': 20.0,  # Buscar do histórico
                    'volume': 1000.0,  # Buscar do histórico
                    'atr': abs(signal.entry_price - signal.stop_loss),
                }
                
                # Predizer
                ml_score = self.ml_filter.predict(
                    candle_data=candle_data,
                    strategy='rsi_divergence',
                    signal_strength=signal.strength,
                    setup_quality=70.0,  # Placeholder
                    regime='SIDEWAYS'
                )
                
                ml_approved = ml_score >= self.min_ml_score
                
                logger.info(f"🤖 ML Score: {ml_score:.2%} | Approved: {ml_approved}")
                
                # Salvar score no banco
                await conn.execute("""
                    UPDATE autotrade_signals
                    SET ml_score = $1
                    WHERE signal_id = $2
                """, ml_score, signal_id)
                
            except Exception as e:
                logger.warning(f"🤖 ML Filter error (using default): {e}")
        
        # 🚀 AUTO-EXECUTE: Só se ML aprovar
        if self.auto_trade_enabled and signal.strength >= self.min_signal_strength_for_trade:
            if ml_approved:
                trade_id = await self._create_paper_trade_from_signal(
                    signal, signal_id, ml_score
                )
                if trade_id:
                    logger.info(f"🤖 Auto-executed trade: {trade_id} (ML: {ml_score:.2%})")
            else:
                logger.info(f"🚫 ML Filter rejected signal: {ml_score:.2%} < {self.min_ml_score:.2%}")
        
        return signal_id
    
    async def _create_paper_trade_from_signal(
        self, signal: DivergenceSignal, signal_id: str, ml_score: float = 0.5
    ) -> Optional[int]:
        """
        🤖 Cria paper trade com position sizing ajustado por ML
        """
        # ... código existente até calcular base risk ...
        
        # Base risk: 2%
        base_risk_amount = current_capital * 0.02
        
        # 🤖 ML POSITION SIZING ADJUSTMENT
        if ml_score >= 0.8:
            risk_multiplier = 1.5  # High confidence: 3% risk
            logger.info(f"🤖 High ML confidence ({ml_score:.2%}) -> 3% risk")
        elif ml_score >= 0.6:
            risk_multiplier = 1.0  # Medium confidence: 2% risk (padrão)
            logger.info(f"🤖 Medium ML confidence ({ml_score:.2%}) -> 2% risk")
        else:
            risk_multiplier = 0.5  # Low confidence: 1% risk (conservador)
            logger.info(f"🤖 Low ML confidence ({ml_score:.2%}) -> 1% risk")
        
        risk_amount = base_risk_amount * risk_multiplier
        
        # Calculate position size
        stop_distance = abs(entry_price - stop_loss)
        position_size = risk_amount / stop_distance if stop_distance > 0 else 0.001
        
        # ... resto do código existente ...
```

---

### ETAPA 2: API Endpoints para ML Control

**Arquivo**: `services/execution-engine/src/main.py`

```python
@app.post("/api/scanner/enable-ml-filter")
async def enable_scanner_ml_filter(min_score: float = 0.6):
    """
    🤖 Habilita ML Filter no scanner
    
    Args:
        min_score: Score mínimo para aprovar sinal (0.0-1.0)
    """
    global rsi_scanner
    
    if rsi_scanner is None:
        raise HTTPException(status_code=400, detail="Scanner not initialized")
    
    # Inicializar e treinar ML filter
    success = await rsi_scanner.initialize_ml_filter()
    
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="ML Filter initialization failed (need 50+ historical trades)"
        )
    
    rsi_scanner.min_ml_score = min_score
    
    return {
        'success': True,
        'message': 'ML Filter enabled',
        'min_ml_score': min_score,
        'note': 'Signals will be filtered by ML confidence before auto-execution'
    }


@app.post("/api/scanner/disable-ml-filter")
async def disable_scanner_ml_filter():
    """
    Desabilita ML Filter
    """
    global rsi_scanner
    
    if rsi_scanner is None:
        return {'success': True, 'message': 'Scanner not initialized'}
    
    rsi_scanner.ml_filter_enabled = False
    
    return {
        'success': True,
        'message': 'ML Filter disabled'
    }


@app.get("/api/scanner/ml-filter-stats")
async def get_ml_filter_stats():
    """
    📊 Retorna estatísticas do ML Filter
    """
    global rsi_scanner
    
    if rsi_scanner is None or not rsi_scanner.ml_filter_enabled:
        return {
            'success': False,
            'enabled': False,
            'message': 'ML Filter not enabled'
        }
    
    # Buscar estatísticas de sinais filtrados
    async with rsi_scanner.db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_signals,
                COUNT(*) FILTER (WHERE ml_score >= $1) as approved_signals,
                COUNT(*) FILTER (WHERE ml_score < $1) as rejected_signals,
                AVG(ml_score) as avg_ml_score,
                AVG(CASE WHEN executed THEN ml_score END) as avg_executed_score
            FROM autotrade_signals
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
                AND ml_score IS NOT NULL
        """, rsi_scanner.min_ml_score)
    
    return {
        'success': True,
        'enabled': True,
        'min_score_threshold': rsi_scanner.min_ml_score,
        'total_signals': stats['total_signals'],
        'approved': stats['approved_signals'],
        'rejected': stats['rejected_signals'],
        'approval_rate': round(stats['approved_signals'] / stats['total_signals'] * 100, 1) if stats['total_signals'] > 0 else 0,
        'avg_ml_score': round(stats['avg_ml_score'], 3) if stats['avg_ml_score'] else None,
        'avg_executed_score': round(stats['avg_executed_score'], 3) if stats['avg_executed_score'] else None
    }
```

---

### ETAPA 3: Frontend Dashboard Updates

**Arquivo**: `frontend/views/scanner-dashboard.ejs`

**Adicionar seção "ML Filter Status"**:

```html
<!-- ML Filter Controls (adicionar após botões de scan) -->
<div class="card shadow-sm mb-4">
    <div class="card-header bg-info bg-opacity-10 d-flex justify-content-between align-items-center">
        <h5 class="mb-0">
            <i class="bi bi-robot text-info"></i> Machine Learning Filter
        </h5>
        <div>
            <span id="mlFilterStatus" class="badge bg-secondary">Desabilitado</span>
            <button class="btn btn-info btn-sm ms-2" onclick="toggleMLFilter()" id="btnMLFilter">
                <i class="bi bi-cpu"></i> Habilitar ML
            </button>
        </div>
    </div>
    <div class="card-body">
        <div class="row text-center">
            <div class="col-md-3">
                <small class="text-muted">Sinais Totais</small>
                <div class="fw-bold" id="mlStatTotalSignals">-</div>
            </div>
            <div class="col-md-3">
                <small class="text-muted">Aprovados</small>
                <div class="fw-bold text-success" id="mlStatApproved">-</div>
            </div>
            <div class="col-md-3">
                <small class="text-muted">Rejeitados</small>
                <div class="fw-bold text-danger" id="mlStatRejected">-</div>
            </div>
            <div class="col-md-3">
                <small class="text-muted">Taxa Aprovação</small>
                <div class="fw-bold text-info" id="mlStatApprovalRate">-</div>
            </div>
        </div>
    </div>
</div>

<script>
async function toggleMLFilter() {
    const isEnabled = document.getElementById('mlFilterStatus').textContent === 'Habilitado';
    
    try {
        const endpoint = isEnabled ? '/api/scanner/disable-ml-filter' : '/api/scanner/enable-ml-filter?min_score=0.6';
        const response = await fetch(API_BASE + endpoint, { method: 'POST' });
        const result = await response.json();
        
        if (!result.success) {
            showToast('Erro', result.detail || 'Falha ao mudar ML Filter', 'danger');
            return;
        }
        
        // Update UI
        const statusBadge = document.getElementById('mlFilterStatus');
        const btnML = document.getElementById('btnMLFilter');
        
        if (isEnabled) {
            statusBadge.textContent = 'Desabilitado';
            statusBadge.className = 'badge bg-secondary';
            btnML.innerHTML = '<i class="bi bi-cpu"></i> Habilitar ML';
        } else {
            statusBadge.textContent = 'Habilitado';
            statusBadge.className = 'badge bg-success';
            btnML.innerHTML = '<i class="bi bi-cpu-fill"></i> Desabilitar ML';
            loadMLFilterStats();  // Load stats immediately
        }
        
        showToast('ML Filter', result.message, 'success');
        
    } catch (error) {
        console.error('Error toggling ML Filter:', error);
        showToast('Erro', 'Falha ao comunicar com servidor', 'danger');
    }
}

async function loadMLFilterStats() {
    try {
        const response = await fetch(API_BASE + '/api/scanner/ml-filter-stats');
        const result = await response.json();
        
        if (!result.success) {
            return;
        }
        
        // Update stats
        document.getElementById('mlStatTotalSignals').textContent = result.total_signals || '0';
        document.getElementById('mlStatApproved').textContent = result.approved || '0';
        document.getElementById('mlStatRejected').textContent = result.rejected || '0';
        document.getElementById('mlStatApprovalRate').textContent = result.approval_rate 
            ? result.approval_rate.toFixed(1) + '%' 
            : '-';
        
    } catch (error) {
        console.error('Error loading ML stats:', error);
    }
}

// Auto-refresh ML stats every 30 seconds
setInterval(() => {
    if (document.getElementById('mlFilterStatus').textContent === 'Habilitado') {
        loadMLFilterStats();
    }
}, 30000);
</script>
```

---

## 📊 Exemplo de Fluxo Completo

### Cenário: Scanner detecta divergência bullish em BTCUSDT

```
1. Scanner RSI Divergence
   ├─> Detecta: Bullish divergence
   ├─> Signal Strength: 0.68 (68%)
   └─> Salva no banco: autotrade_signals

2. ML Filter Evaluation
   ├─> Extrai features:
   │   ├─> RSI: 32 (oversold)
   │   ├─> ADX: 22 (moderate trend)
   │   ├─> Volume: 1.5x average
   │   ├─> Price vs EMA50: -2.3%
   │   └─> ATR: $1,200
   ├─> LightGBM Predict: 0.78 (78% confidence)
   └─> Decision: ✅ APPROVED (>= 0.6 threshold)

3. Position Sizing Adjustment
   ├─> Base capital: $10,000
   ├─> Base risk: 2% = $200
   ├─> ML multiplier: 1.5x (high confidence)
   ├─> Adjusted risk: 3% = $300
   ├─> Entry: $42,500
   ├─> Stop: $42,100
   ├─> Distance: $400
   └─> Position size: $300 / $400 = 0.75 BTC

4. Auto-Execute Paper Trade
   ├─> Create trade in paper_trading_trades
   ├─> Link to signal via signal_id
   └─> Log: "🤖 Auto-executed trade #123 (ML: 78%)"

5. Update Signal Record
   └─> UPDATE autotrade_signals SET ml_score=0.78, executed=true
```

---

## 🎯 Benefícios Esperados

### 1. **Melhoria no Win Rate**
- **Antes ML**: 52.4% win rate (baseline)
- **Esperado com ML**: 58-62% win rate (+6-10pp)
- **Razão**: Filtrar falsos positivos com confiança <60%

### 2. **Redução de Drawdown**
- **Antes ML**: 15.94% max drawdown
- **Esperado com ML**: 12-14% max drawdown (-20%)
- **Razão**: Rejeitar sinais fracos em condições desfavoráveis

### 3. **Position Sizing Dinâmico**
- **High Confidence (80%+)**: 3% risk → Maximizar lucros
- **Medium Confidence (60-80%)**: 2% risk → Padrão conservador
- **Low Confidence (<60%)**: Rejeitado → Evitar perdas

### 4. **Métricas ML**
- **Accuracy**: 70-75% (esperado)
- **Precision**: 75-80% (evitar false positives)
- **Recall**: 65-70% (capturar good signals)
- **AUC**: 0.75-0.85 (discriminação)

---

## 📋 Schema Database Update

**Adicionar coluna `ml_score` na tabela `autotrade_signals`**:

```sql
ALTER TABLE autotrade_signals
ADD COLUMN ml_score DECIMAL(5,4) DEFAULT NULL,
ADD COLUMN ml_rejection_reason TEXT DEFAULT NULL;

CREATE INDEX idx_autotrade_signals_ml_score 
ON autotrade_signals(ml_score) 
WHERE ml_score IS NOT NULL;
```

---

## 🚀 Próximos Passos (Implementação)

### Fase 1: Backend ML Integration (2 horas)
- [ ] Modificar `multi_symbol_scanner.py`:
  - [ ] Adicionar `initialize_ml_filter()` method
  - [ ] Integrar ML filter em `_save_signal_to_db()`
  - [ ] Ajustar position sizing com ML score
- [ ] Atualizar `_create_paper_trade_from_signal()` para aceitar ml_score
- [ ] Adicionar coluna `ml_score` no banco

### Fase 2: API Endpoints (30 min)
- [ ] POST `/api/scanner/enable-ml-filter`
- [ ] POST `/api/scanner/disable-ml-filter`
- [ ] GET `/api/scanner/ml-filter-stats`

### Fase 3: Frontend Integration (1 hora)
- [ ] Adicionar seção "ML Filter Status" no dashboard
- [ ] Criar botão toggle ML Filter
- [ ] Exibir estatísticas de aprovação/rejeição
- [ ] Adicionar coluna "ML Score" na tabela de sinais

### Fase 4: Testing & Validation (1 hora)
- [ ] Treinar ML com 30 dias de histórico
- [ ] Testar filtro com sinais reais
- [ ] Validar performance: antes vs depois ML
- [ ] Ajustar threshold (0.5, 0.6, 0.7)

### Fase 5: Documentation (30 min)
- [ ] Criar script `test_ml_scanner.sh`
- [ ] Documentar casos de uso
- [ ] Atualizar SIGNAL_PERSISTENCE_GUIDE.md

---

## 📊 Comparação: Antes vs Depois ML

| Métrica | Sem ML | Com ML (esperado) | Melhoria |
|---------|--------|-------------------|----------|
| **Win Rate** | 52.4% | 58-62% | +6-10pp |
| **Max Drawdown** | 15.94% | 12-14% | -20% |
| **Trades/Mês** | ~20 | ~15 | -25% (mais seletivo) |
| **Avg Win** | $1,509 | $1,800 | +19% |
| **Profit Factor** | 1.25 | 1.4-1.6 | +12-28% |
| **Sharpe Ratio** | 0.67 | 0.8-1.0 | +19-49% |

---

## 🔍 Monitoramento e Ajustes

### Métricas para Acompanhar

1. **ML Approval Rate**: % de sinais aprovados
   - **Ideal**: 50-70% (filtro seletivo mas não muito rigoroso)
   - **Alerta**: <30% (muito restritivo) ou >90% (pouco seletivo)

2. **Win Rate ML-Approved vs Rejected**:
   - Validar se sinais rejeitados realmente teriam perdido
   - Ideal: Rejected signals têm <40% win rate

3. **False Negatives**:
   - Sinais rejeitados pelo ML que teriam dado TP
   - Objetivo: <20% dos sinais aprovados

4. **Re-training Frequency**:
   - Re-treinar modelo a cada 7-14 dias
   - Ou quando accuracy cair abaixo de 65%

---

## 🐛 Troubleshooting

### "ML Filter initialization failed"
- **Causa**: Menos de 50 trades históricos
- **Solução**: Aguardar mais dados ou reduzir limite para 30 trades

### "ML Score sempre 0.5"
- **Causa**: Modelo não treinado ou erro na predição
- **Solução**: Verificar logs, re-treinar modelo

### "Approval Rate muito baixa (<30%)"
- **Causa**: Threshold muito alto (0.7-0.8)
- **Solução**: Reduzir para 0.5-0.6

### "Win Rate não melhorou"
- **Causa**: Features podem não ser preditivas
- **Solução**: Adicionar mais features (Bollinger Bands, MACD, regime history)

---

## 📞 Suporte

Para dúvidas sobre ML integration:
1. Consulte [PASSO_34_ML_FILTER.md](PASSO_34_ML_FILTER.md) para detalhes do modelo
2. Consulte [AUTO_TRADE_GUIDE.md](AUTO_TRADE_GUIDE.md) para auto-trade
3. Consulte [SIGNAL_PERSISTENCE_GUIDE.md](SIGNAL_PERSISTENCE_GUIDE.md) para database

---

**Última atualização**: 22 de Dezembro de 2025  
**Versão**: 1.0.0 (PLANEJAMENTO)  
**Próximo passo**: Implementar Fase 1 - Backend ML Integration
