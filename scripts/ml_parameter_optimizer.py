#!/usr/bin/env python3
"""
PASSO 27.3: Adaptive Parameters ML - Machine Learning Parameter Optimizer
==========================================================================

Usa Random Forest para sugerir ajustes de parâmetros do MetaBacktester
baseado em condições de mercado e histórico de performance.

Features:
- Volatility (ATR, Bollinger width)
- Market Regime (BULL/BEAR/SIDEWAYS frequency)
- Momentum (RSI, MACD trends)
- Recent performance (last 3 WFO results)

Target:
- Parameter suggestions with confidence scores
- Predicted return/Sharpe for suggested params

Metodologia:
- Walk-forward cross-validation
- Train em dados históricos CSV do WFO
- Test em período mais recente

Usage:
    python3 scripts/ml_parameter_optimizer.py
    python3 scripts/ml_parameter_optimizer.py --symbol ETHUSDT
    python3 scripts/ml_parameter_optimizer.py --train-samples 20
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import argparse
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("⚠️  scikit-learn não instalado. Usando fallback heurístico.")

# Parameter ranges (current MetaBacktester configuration)
PARAM_RANGES = {
    'risk_per_trade': (0.005, 0.03),           # 0.5% - 3.0%
    'tp_multiplier_sideways': (1.5, 3.0),      # Take Profit em SIDEWAYS
    'tp_multiplier_bull': (2.5, 4.0),          # Take Profit em BULL
    'tp_multiplier_bear': (2.0, 3.5),          # Take Profit em BEAR
    'regime_confirmation': (4, 10),            # Hysteresis candles
    'min_quality_sideways': (60, 80),          # Setup quality threshold
    'breakeven_atr_mult': (0.3, 1.0),          # Break-even trigger
    'trailing_atr_mult': (1.0, 2.0),           # Trailing stop
}

# Default parameters (baseline)
DEFAULT_PARAMS = {
    'risk_per_trade': 0.02,
    'tp_multiplier_sideways': 2.5,
    'tp_multiplier_bull': 3.0,
    'tp_multiplier_bear': 2.5,
    'regime_confirmation': 8,
    'min_quality_sideways': 70,
    'breakeven_atr_mult': 0.5,
    'trailing_atr_mult': 1.5,
}


class MarketFeatureExtractor:
    """Extrai features de mercado para ML"""
    
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
    
    def extract_features_from_wfo_history(self, csv_path: Path) -> pd.DataFrame:
        """
        Extrai features do histórico CSV do WFO
        
        Cada linha do CSV tem:
        - date, period, return, sharpe, max_dd, win_rate, trades
        
        Features derivadas:
        - recent_return_trend (últimas 3 execuções)
        - recent_sharpe_trend
        - volatility_estimate (std das últimas 5 returns)
        - win_rate_stability (std das últimas 5 WRs)
        """
        df = pd.read_csv(csv_path)
        
        # Sort por data
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Calcular features baseadas em janelas móveis
        df['return_ma3'] = df['return'].rolling(3).mean()
        df['return_std5'] = df['return'].rolling(5).std()
        df['sharpe_ma3'] = df['sharpe'].rolling(3).mean()
        df['sharpe_std5'] = df['sharpe'].rolling(5).std()
        df['win_rate_std5'] = df['win_rate'].rolling(5).std()
        df['max_dd_ma3'] = df['max_dd'].rolling(3).mean()
        
        # Tendências (diff últimos 3 períodos)
        df['return_trend'] = df['return'].diff(3)
        df['sharpe_trend'] = df['sharpe'].diff(3)
        
        # Remover NaNs das rolling windows
        df = df.dropna()
        
        return df
    
    def prepare_ml_dataset(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepara dataset para ML
        
        X (features): return_ma3, return_std5, sharpe_ma3, sharpe_std5, 
                     win_rate_std5, max_dd_ma3, return_trend, sharpe_trend
        
        y (target): next_return (return do próximo período)
        """
        # Features
        feature_cols = [
            'return_ma3', 'return_std5', 'sharpe_ma3', 'sharpe_std5',
            'win_rate_std5', 'max_dd_ma3', 'return_trend', 'sharpe_trend'
        ]
        
        X = df[feature_cols].copy()
        
        # Target: retorno do PRÓXIMO período
        y = df['return'].shift(-1)
        
        # Remover última linha (sem target)
        X = X.iloc[:-1]
        y = y.iloc[:-1]
        
        return X, y


class MLParameterOptimizer:
    """Otimizador de parâmetros usando Machine Learning"""
    
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.model = None
        self.scaler = StandardScaler() if HAS_SKLEARN else None
        self.feature_extractor = MarketFeatureExtractor(symbol)
        self.trained = False
    
    def train(self, csv_path: Path, n_estimators: int = 100) -> Dict:
        """
        Treina modelo Random Forest com dados históricos
        
        Returns:
            Dict com métricas de treinamento
        """
        if not HAS_SKLEARN:
            print("❌ scikit-learn não disponível. Treino impossível.")
            return {'success': False, 'error': 'sklearn_missing'}
        
        print(f"\n🤖 Treinando modelo ML para {self.symbol}...")
        print(f"📁 CSV: {csv_path}")
        
        # 1. Extrair features
        df = self.feature_extractor.extract_features_from_wfo_history(csv_path)
        
        if len(df) < 10:
            print(f"⚠️  Dados insuficientes: {len(df)} amostras (mínimo 10)")
            return {'success': False, 'error': 'insufficient_data', 'samples': len(df)}
        
        print(f"✅ {len(df)} amostras disponíveis")
        
        # 2. Preparar dataset
        X, y = self.feature_extractor.prepare_ml_dataset(df)
        
        print(f"📊 Features: {X.shape[1]}")
        print(f"📊 Samples: {len(X)}")
        
        # 3. Normalizar features
        X_scaled = self.scaler.fit_transform(X)
        
        # 4. Walk-forward cross-validation (Time Series Split)
        tscv = TimeSeriesSplit(n_splits=min(3, len(X) // 3))
        
        print("\n🔄 Walk-Forward Cross-Validation:")
        
        cv_scores = []
        fold = 1
        
        for train_idx, test_idx in tscv.split(X_scaled):
            X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Treinar fold
            rf = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)
            rf.fit(X_train, y_train)
            
            # Predizer
            y_pred = rf.predict(X_test)
            
            # Métricas
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            print(f"   Fold {fold}: MSE={mse:.4f}, R²={r2:.4f}")
            cv_scores.append(r2)
            fold += 1
        
        # 5. Treinar modelo final com todos os dados
        self.model = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)
        self.model.fit(X_scaled, y)
        
        self.trained = True
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n📊 FEATURE IMPORTANCE:")
        for _, row in feature_importance.iterrows():
            print(f"   {row['feature']:<20}: {row['importance']:.4f}")
        
        metrics = {
            'success': True,
            'samples': len(X),
            'cv_r2_mean': np.mean(cv_scores),
            'cv_r2_std': np.std(cv_scores),
            'feature_importance': feature_importance.to_dict('records')
        }
        
        print(f"\n✅ Modelo treinado!")
        print(f"   CV R² médio: {metrics['cv_r2_mean']:.4f} ± {metrics['cv_r2_std']:.4f}")
        
        return metrics
    
    def predict_performance(self, current_features: Dict) -> float:
        """
        Prediz retorno esperado com features atuais
        
        Args:
            current_features: Dict com features do período atual
        
        Returns:
            Retorno previsto (%)
        """
        if not self.trained:
            print("⚠️  Modelo não treinado. Use .train() primeiro.")
            return 0.0
        
        # Converter dict para array
        feature_array = np.array([[
            current_features.get('return_ma3', 0),
            current_features.get('return_std5', 0),
            current_features.get('sharpe_ma3', 0),
            current_features.get('sharpe_std5', 0),
            current_features.get('win_rate_std5', 0),
            current_features.get('max_dd_ma3', 0),
            current_features.get('return_trend', 0),
            current_features.get('sharpe_trend', 0)
        ]])
        
        # Normalizar
        feature_scaled = self.scaler.transform(feature_array)
        
        # Predizer
        prediction = self.model.predict(feature_scaled)[0]
        
        return prediction
    
    def suggest_parameters(self, csv_path: Path) -> Dict:
        """
        Sugere ajustes de parâmetros baseado em análise heurística
        
        Estratégia:
        1. Analisar últimas 3 execuções WFO
        2. Identificar problemas (baixo Sharpe, alto DD, etc)
        3. Sugerir ajustes de parâmetros
        4. Se modelo ML treinado, usar predição para confidence
        
        Returns:
            Dict com parâmetros sugeridos e rationale
        """
        print(f"\n🔍 Analisando histórico WFO para sugerir parâmetros...")
        
        df = pd.read_csv(csv_path)
        
        if len(df) == 0:
            return {'success': False, 'error': 'empty_csv'}
        
        # Sort por data
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Últimas 3 execuções
        recent = df.tail(3)
        
        avg_return = recent['return'].mean()
        avg_sharpe = recent['sharpe'].mean()
        avg_dd = recent['max_dd'].mean()
        avg_wr = recent['win_rate'].mean()
        
        print(f"\n📊 ANÁLISE RECENTE (últimas 3 execuções):")
        print(f"   Retorno médio: {avg_return:+.2f}%")
        print(f"   Sharpe médio: {avg_sharpe:.2f}")
        print(f"   DD médio: {avg_dd:.2f}%")
        print(f"   WR médio: {avg_wr:.1f}%")
        
        # Iniciar com parâmetros padrão
        suggested = DEFAULT_PARAMS.copy()
        rationale = []
        
        # REGRA 1: Sharpe baixo (<0.5) → Reduzir risco
        if avg_sharpe < 0.5:
            suggested['risk_per_trade'] = max(0.005, DEFAULT_PARAMS['risk_per_trade'] * 0.7)
            rationale.append(f"Sharpe baixo ({avg_sharpe:.2f}) → Reduzir risco para {suggested['risk_per_trade']*100:.1f}%")
        
        # REGRA 2: Sharpe alto (>1.5) → Aumentar risco (aproveitar edge)
        elif avg_sharpe > 1.5:
            suggested['risk_per_trade'] = min(0.03, DEFAULT_PARAMS['risk_per_trade'] * 1.3)
            rationale.append(f"Sharpe alto ({avg_sharpe:.2f}) → Aumentar risco para {suggested['risk_per_trade']*100:.1f}%")
        
        # REGRA 3: DD alto (>10%) → Aumentar hysteresis (evitar whipsaw)
        if avg_dd > 10:
            suggested['regime_confirmation'] = min(10, DEFAULT_PARAMS['regime_confirmation'] + 2)
            rationale.append(f"DD alto ({avg_dd:.1f}%) → Aumentar hysteresis para {suggested['regime_confirmation']} candles")
        
        # REGRA 4: WR baixo (<50%) → Aumentar TP targets (deixar lucros correrem)
        if avg_wr < 50:
            suggested['tp_multiplier_sideways'] = min(3.0, DEFAULT_PARAMS['tp_multiplier_sideways'] + 0.5)
            suggested['tp_multiplier_bull'] = min(4.0, DEFAULT_PARAMS['tp_multiplier_bull'] + 0.5)
            rationale.append(f"WR baixo ({avg_wr:.1f}%) → Aumentar TP targets (deixar lucros correrem)")
        
        # REGRA 5: WR alto (>65%) → Diminuir TP targets (realizar lucros mais cedo)
        elif avg_wr > 65:
            suggested['tp_multiplier_sideways'] = max(1.5, DEFAULT_PARAMS['tp_multiplier_sideways'] - 0.3)
            suggested['tp_multiplier_bull'] = max(2.5, DEFAULT_PARAMS['tp_multiplier_bull'] - 0.3)
            rationale.append(f"WR alto ({avg_wr:.1f}%) → Diminuir TP targets (realizar lucros)")
        
        # REGRA 6: Retorno negativo consistente → Aumentar filtros
        if avg_return < 0:
            suggested['min_quality_sideways'] = min(80, DEFAULT_PARAMS['min_quality_sideways'] + 5)
            rationale.append(f"Retorno negativo ({avg_return:.2f}%) → Aumentar min_quality para {suggested['min_quality_sideways']}")
        
        # REGRA 7: Volatilidade alta (std return > 5%) → Ajustar stops
        if len(recent) >= 3:
            vol = recent['return'].std()
            if vol > 5:
                suggested['breakeven_atr_mult'] = max(0.3, DEFAULT_PARAMS['breakeven_atr_mult'] - 0.1)
                suggested['trailing_atr_mult'] = min(2.0, DEFAULT_PARAMS['trailing_atr_mult'] + 0.2)
                rationale.append(f"Volatilidade alta (std={vol:.2f}%) → Ajustar stops")
        
        # Se não há mudanças, manter defaults
        if not rationale:
            rationale.append("Performance estável → Manter parâmetros atuais")
        
        # Calcular confidence (se modelo ML disponível)
        confidence = 0.5  # baseline
        
        if self.trained and HAS_SKLEARN:
            # Extrair features atuais
            df_features = self.feature_extractor.extract_features_from_wfo_history(csv_path)
            if len(df_features) > 0:
                current_features = df_features.iloc[-1].to_dict()
                predicted_return = self.predict_performance(current_features)
                
                # Confidence baseado em previsão
                if predicted_return > 2:
                    confidence = 0.8
                elif predicted_return > 0:
                    confidence = 0.6
                elif predicted_return > -2:
                    confidence = 0.4
                else:
                    confidence = 0.2
                
                rationale.append(f"ML prevê retorno de {predicted_return:+.2f}% (confidence: {confidence:.1%})")
        
        return {
            'success': True,
            'suggested_params': suggested,
            'default_params': DEFAULT_PARAMS,
            'changes': {k: v for k, v in suggested.items() if v != DEFAULT_PARAMS[k]},
            'rationale': rationale,
            'confidence': confidence,
            'metrics': {
                'avg_return': avg_return,
                'avg_sharpe': avg_sharpe,
                'avg_dd': avg_dd,
                'avg_wr': avg_wr
            }
        }


def format_suggestions(result: Dict):
    """Formata sugestões para output legível"""
    print("\n" + "="*80)
    print("💡 SUGESTÕES DE PARÂMETROS")
    print("="*80)
    
    if not result['success']:
        print(f"❌ Erro: {result.get('error', 'unknown')}")
        return
    
    print(f"\n📊 Métricas Recentes:")
    m = result['metrics']
    print(f"   Retorno: {m['avg_return']:+.2f}%")
    print(f"   Sharpe: {m['avg_sharpe']:.2f}")
    print(f"   Max DD: {m['avg_dd']:.2f}%")
    print(f"   Win Rate: {m['avg_wr']:.1f}%")
    
    print(f"\n🔧 MUDANÇAS SUGERIDAS:")
    
    changes = result['changes']
    if not changes:
        print("   ✅ Nenhuma mudança necessária (sistema estável)")
    else:
        for param, new_value in changes.items():
            old_value = result['default_params'][param]
            
            # Format values
            if 'risk' in param or 'mult' in param:
                old_str = f"{old_value:.3f}"
                new_str = f"{new_value:.3f}"
            else:
                old_str = f"{old_value}"
                new_str = f"{new_value}"
            
            change_pct = ((new_value - old_value) / old_value * 100) if old_value != 0 else 0
            emoji = "🔼" if new_value > old_value else "🔽"
            
            print(f"   {emoji} {param}: {old_str} → {new_str} ({change_pct:+.1f}%)")
    
    print(f"\n💭 RATIONALE:")
    for i, reason in enumerate(result['rationale'], 1):
        print(f"   {i}. {reason}")
    
    print(f"\n🎯 CONFIDENCE: {result['confidence']:.1%}")
    
    if result['confidence'] > 0.7:
        print("   ✅ Alta confiança - Aplicar mudanças")
    elif result['confidence'] > 0.5:
        print("   🟡 Confiança moderada - Testar em backtest antes")
    else:
        print("   ⚠️  Baixa confiança - Monitorar mais períodos")
    
    print("\n" + "="*80)


def apply_suggestions(result: Dict, output_file: Path):
    """
    Gera arquivo JSON com parâmetros sugeridos para aplicação
    """
    if not result['success']:
        print("❌ Não há sugestões para aplicar")
        return
    
    config = {
        'timestamp': datetime.now().isoformat(),
        'parameters': result['suggested_params'],
        'confidence': result['confidence'],
        'rationale': result['rationale'],
        'metrics': result['metrics']
    }
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Parâmetros salvos em: {output_file}")
    print("\n📝 Para aplicar:")
    print("   1. Revisar arquivo JSON")
    print("   2. Editar services/execution-engine/src/meta_simulation.py")
    print("   3. Rebuild container: docker compose build execution-engine")
    print("   4. Restart: docker compose restart execution-engine")
    print("   5. Validar: bash scripts/wfo_simple.sh")


def main():
    parser = argparse.ArgumentParser(description="ML Parameter Optimizer - PASSO 27.3")
    parser.add_argument('--symbol', default='BTCUSDT', help='Trading pair (default: BTCUSDT)')
    parser.add_argument('--csv', help='Path to WFO CSV history (default: auto-detect)')
    parser.add_argument('--train', action='store_true', help='Train ML model (requires sklearn)')
    parser.add_argument('--train-samples', type=int, default=100, help='Number of trees for Random Forest')
    parser.add_argument('--apply', action='store_true', help='Generate JSON file with suggestions')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🤖 ML PARAMETER OPTIMIZER - PASSO 27.3")
    print("="*80)
    print(f"\nSymbol: {args.symbol}")
    
    # Detectar CSV path
    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = Path(f"logs/wfo/history.csv")
        if not csv_path.exists():
            csv_path = Path(f"logs/wfo/{args.symbol.lower()}_history.csv")
    
    if not csv_path.exists():
        print(f"\n❌ CSV não encontrado: {csv_path}")
        print("\n💡 Execute primeiro:")
        print(f"   bash scripts/wfo_simple.sh")
        return 1
    
    print(f"📁 CSV: {csv_path}")
    
    # Criar optimizer
    optimizer = MLParameterOptimizer(args.symbol)
    
    # Train ML model se solicitado
    if args.train:
        if not HAS_SKLEARN:
            print("\n❌ scikit-learn não instalado")
            print("   Instalar: pip install scikit-learn")
            return 1
        
        train_metrics = optimizer.train(csv_path, n_estimators=args.train_samples)
        
        if not train_metrics['success']:
            print(f"\n❌ Treino falhou: {train_metrics.get('error')}")
            return 1
    
    # Sugerir parâmetros
    result = optimizer.suggest_parameters(csv_path)
    
    # Formatar output
    format_suggestions(result)
    
    # Aplicar se solicitado
    if args.apply:
        output_file = Path(f"logs/wfo/suggested_params_{args.symbol.lower()}.json")
        apply_suggestions(result, output_file)
    
    return 0


if __name__ == "__main__":
    exit(main())
