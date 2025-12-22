"""
PASSO 34: Machine Learning Signal Filter
==========================================
LightGBM classifier para filtrar sinais falsos e melhorar win rate.

Features:
- RSI (14), ADX (14), Volume Ratio, ATR Ratio
- Market Regime (BULL/BEAR/SIDEWAYS)
- Signal Strength, Setup Quality
- Price Distance from EMAs (50, 200)

Training:
- Usa histórico de trades do backtest como labeled data
- Label: 1 = TP (bom sinal), 0 = SL (falso sinal)
- Auto-retrain quando performance degrada

Usage:
    ml_filter = MLSignalFilter()
    ml_filter.train(historical_trades_df)
    score = ml_filter.predict(current_features)
    if score >= min_score:
        # Executar trade
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import json
import os
from datetime import datetime
import logging

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logging.warning("LightGBM not installed. ML filter disabled. Install: pip install lightgbm")

logger = logging.getLogger(__name__)


class MLSignalFilter:
    """
    Filtro de Machine Learning para classificar qualidade de sinais de trading.
    
    Features utilizadas:
    - Indicadores técnicos: RSI, ADX, Volume, ATR
    - Market regime: BULL, BEAR, SIDEWAYS
    - Signal metadata: strategy, signal strength, setup quality
    - Price context: distance from EMAs, price momentum
    
    Label:
    - 1 = Good signal (resultou em TAKE_PROFIT)
    - 0 = False signal (resultou em STOP_LOSS)
    """
    
    def __init__(self, model_path: str = '/tmp/ml_signal_filter_model.txt'):
        self.model_path = model_path
        self.model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = []
        self.regime_mapping = {'BULL': 0, 'BEAR': 1, 'SIDEWAYS': 2}
        self.is_trained = False
        
        # LightGBM hyperparameters
        self.params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'max_depth': 5,
            'min_data_in_leaf': 20,
            'lambda_l1': 0.1,
            'lambda_l2': 0.1
        }
        
        # Tentar carregar modelo existente
        if os.path.exists(self.model_path):
            try:
                self.load_model()
                logger.info(f"✅ ML model loaded from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load ML model: {e}")
    
    def extract_features(self, candle_data: Dict, strategy: str, signal_strength: float, 
                        setup_quality: float, regime: str) -> Dict[str, float]:
        """
        Extrai features do estado atual do mercado para predição.
        
        Args:
            candle_data: Dict com OHLCV e indicadores
            strategy: Nome da estratégia (ex: 'momentum', 'rsi_divergence_bullish')
            signal_strength: Força do sinal (0-1)
            setup_quality: Qualidade do setup (0-100)
            regime: Market regime ('BULL', 'BEAR', 'SIDEWAYS')
        
        Returns:
            Dict com features prontas para predição
        """
        features = {}
        
        # Indicadores técnicos
        features['rsi'] = candle_data.get('rsi', 50.0)
        features['adx'] = candle_data.get('adx', 20.0)
        features['atr'] = candle_data.get('atr', 0.0)
        features['volume'] = candle_data.get('volume', 0.0)
        
        # Volume ratio (vs média)
        volume_ma = candle_data.get('volume_ma_20', features['volume'])
        features['volume_ratio'] = features['volume'] / volume_ma if volume_ma > 0 else 1.0
        
        # ATR ratio (volatility)
        price = candle_data.get('close', 0.0)
        features['atr_ratio'] = features['atr'] / price if price > 0 else 0.0
        
        # Price distance from EMAs
        ema_50 = candle_data.get('ema_50', price)
        ema_200 = candle_data.get('ema_200', price)
        features['price_vs_ema50'] = (price - ema_50) / ema_50 if ema_50 > 0 else 0.0
        features['price_vs_ema200'] = (price - ema_200) / ema_200 if ema_200 > 0 else 0.0
        
        # EMA separation (trend strength)
        features['ema_separation'] = (ema_50 - ema_200) / ema_200 if ema_200 > 0 else 0.0
        
        # Signal metadata
        features['signal_strength'] = signal_strength
        features['setup_quality'] = setup_quality
        
        # Market regime (encoded)
        features['regime'] = self.regime_mapping.get(regime, 2)
        
        # Strategy type (one-hot encoding simplificado)
        features['is_trend_strategy'] = 1.0 if 'trend' in strategy.lower() or 'momentum' in strategy.lower() else 0.0
        features['is_reversion_strategy'] = 1.0 if 'reversion' in strategy.lower() or 'divergence' in strategy.lower() else 0.0
        
        # Price momentum (recent change)
        open_price = candle_data.get('open', price)
        features['price_momentum'] = (price - open_price) / open_price if open_price > 0 else 0.0
        
        # RSI extremes
        features['rsi_oversold'] = 1.0 if features['rsi'] < 30 else 0.0
        features['rsi_overbought'] = 1.0 if features['rsi'] > 70 else 0.0
        
        return features
    
    def prepare_training_data(self, trades: List[Dict]) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepara dados de treino a partir do histórico de trades.
        
        Args:
            trades: Lista de trades do backtest, cada um com:
                - entry_state: Dict com candle data no momento da entrada
                - strategy: Nome da estratégia
                - signal_strength: Força do sinal
                - setup_quality: Qualidade do setup
                - regime: Market regime
                - exit_reason: 'TAKE_PROFIT' ou 'STOP_LOSS'
        
        Returns:
            (X, y) onde X é DataFrame com features e y é Series com labels (1=TP, 0=SL)
        """
        if not trades:
            raise ValueError("No trades provided for training")
        
        feature_rows = []
        labels = []
        
        for trade in trades:
            # Extrair features do estado no momento da entrada
            entry_state = trade.get('entry_state', {})
            strategy = trade.get('strategy', 'unknown')
            signal_strength = trade.get('signal_strength', 0.5)
            setup_quality = trade.get('setup_quality', 50.0)
            regime = trade.get('regime', 'SIDEWAYS')
            
            features = self.extract_features(
                candle_data=entry_state,
                strategy=strategy,
                signal_strength=signal_strength,
                setup_quality=setup_quality,
                regime=regime
            )
            
            feature_rows.append(features)
            
            # Label: 1 = bom sinal (TP), 0 = falso sinal (SL)
            exit_reason = trade.get('exit_reason', 'STOP_LOSS')
            label = 1 if exit_reason == 'TAKE_PROFIT' else 0
            labels.append(label)
        
        X = pd.DataFrame(feature_rows)
        y = pd.Series(labels, name='label')
        
        # Armazenar feature names para uso futuro
        self.feature_names = list(X.columns)
        
        logger.info(f"📊 Training data prepared: {len(X)} samples, {len(self.feature_names)} features")
        logger.info(f"   Positive samples (TP): {y.sum()} ({y.mean()*100:.1f}%)")
        logger.info(f"   Negative samples (SL): {len(y) - y.sum()} ({(1-y.mean())*100:.1f}%)")
        
        return X, y
    
    def train(self, trades: List[Dict], test_size: float = 0.2, num_rounds: int = 100) -> Dict:
        """
        Treina o modelo LightGBM com histórico de trades.
        
        Args:
            trades: Lista de trades com features e exit_reason
            test_size: Proporção para validação (default 0.2)
            num_rounds: Número de rounds de boosting (default 100)
        
        Returns:
            Dict com métricas de treinamento (accuracy, precision, recall, f1)
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("LightGBM not installed. Install: pip install lightgbm")
        
        # Preparar dados
        X, y = self.prepare_training_data(trades)
        
        # Split train/test
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Criar datasets LightGBM
        train_data = lgb.Dataset(X_train, label=y_train, feature_name=self.feature_names)
        test_data = lgb.Dataset(X_test, label=y_test, reference=train_data, feature_name=self.feature_names)
        
        # Treinar modelo
        logger.info(f"🔧 Training LightGBM model ({num_rounds} rounds)...")
        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_rounds,
            valid_sets=[test_data],
            valid_names=['validation'],
            callbacks=[lgb.early_stopping(stopping_rounds=20), lgb.log_evaluation(period=0)]
        )
        
        self.is_trained = True
        
        # Avaliar performance
        y_pred_proba = self.model.predict(X_test)
        y_pred = (y_pred_proba >= 0.5).astype(int)
        
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_pred_proba) if len(set(y_test)) > 1 else 0.0,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'best_iteration': self.model.best_iteration
        }
        
        logger.info(f"✅ Model trained successfully!")
        logger.info(f"   Accuracy: {metrics['accuracy']:.3f}")
        logger.info(f"   Precision: {metrics['precision']:.3f}")
        logger.info(f"   Recall: {metrics['recall']:.3f}")
        logger.info(f"   F1: {metrics['f1']:.3f}")
        logger.info(f"   AUC: {metrics['auc']:.3f}")
        
        # Feature importance
        importance = self.model.feature_importance(importance_type='gain')
        feature_importance = sorted(zip(self.feature_names, importance), key=lambda x: x[1], reverse=True)
        logger.info("📊 Top 5 features:")
        for feat, imp in feature_importance[:5]:
            logger.info(f"   {feat}: {imp:.1f}")
        
        # Salvar modelo
        self.save_model()
        
        return metrics
    
    def predict(self, candle_data: Dict, strategy: str, signal_strength: float,
                setup_quality: float, regime: str) -> float:
        """
        Prediz score de qualidade do sinal (0-1).
        
        Args:
            candle_data: Dict com OHLCV e indicadores
            strategy: Nome da estratégia
            signal_strength: Força do sinal
            setup_quality: Qualidade do setup
            regime: Market regime
        
        Returns:
            Score 0-1 (probabilidade de ser bom sinal)
        """
        if not self.is_trained:
            logger.warning("⚠️ ML model not trained. Returning default score 0.5")
            return 0.5
        
        # Extrair features
        features = self.extract_features(candle_data, strategy, signal_strength, setup_quality, regime)
        
        # Garantir ordem correta das features
        X = pd.DataFrame([features])[self.feature_names]
        
        # Predição
        score = self.model.predict(X)[0]
        
        return float(score)
    
    def save_model(self):
        """Salva modelo treinado em disco."""
        if self.model is None:
            logger.warning("No model to save")
            return
        
        try:
            self.model.save_model(self.model_path)
            
            # Salvar metadata
            metadata = {
                'feature_names': self.feature_names,
                'regime_mapping': self.regime_mapping,
                'trained_at': datetime.now().isoformat(),
                'is_trained': self.is_trained
            }
            metadata_path = self.model_path.replace('.txt', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"💾 Model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def load_model(self):
        """Carrega modelo treinado do disco."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        try:
            self.model = lgb.Booster(model_file=self.model_path)
            
            # Carregar metadata
            metadata_path = self.model_path.replace('.txt', '_metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                self.feature_names = metadata.get('feature_names', [])
                self.regime_mapping = metadata.get('regime_mapping', self.regime_mapping)
                self.is_trained = metadata.get('is_trained', True)
            else:
                # Fallback: usar feature names do modelo
                self.feature_names = self.model.feature_name()
                self.is_trained = True
            
            logger.info(f"📂 Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def get_feature_importance(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        Retorna as N features mais importantes do modelo.
        
        Args:
            top_n: Número de features a retornar
        
        Returns:
            Lista de tuplas (feature_name, importance_score)
        """
        if not self.is_trained:
            return []
        
        importance = self.model.feature_importance(importance_type='gain')
        feature_importance = sorted(zip(self.feature_names, importance), key=lambda x: x[1], reverse=True)
        
        return feature_importance[:top_n]


# Exemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Criar mock de trades para demonstração
    mock_trades = [
        {
            'entry_state': {
                'close': 45000.0,
                'open': 44800.0,
                'volume': 1500.0,
                'volume_ma_20': 1200.0,
                'rsi': 65.0,
                'adx': 28.0,
                'atr': 450.0,
                'ema_50': 44500.0,
                'ema_200': 43000.0
            },
            'strategy': 'momentum',
            'signal_strength': 0.75,
            'setup_quality': 85.0,
            'regime': 'BULL',
            'exit_reason': 'TAKE_PROFIT'
        },
        {
            'entry_state': {
                'close': 44000.0,
                'open': 44200.0,
                'volume': 800.0,
                'volume_ma_20': 1200.0,
                'rsi': 35.0,
                'adx': 18.0,
                'atr': 400.0,
                'ema_50': 44500.0,
                'ema_200': 43000.0
            },
            'strategy': 'rsi_divergence_bullish',
            'signal_strength': 0.45,
            'setup_quality': 55.0,
            'regime': 'SIDEWAYS',
            'exit_reason': 'STOP_LOSS'
        }
    ]
    
    # Testar ML filter
    print("\n🧪 Testing ML Signal Filter...")
    ml_filter = MLSignalFilter()
    
    # Precisaria de mais trades para treinar realmente
    print("⚠️ Mock example with only 2 trades (need 50+ for real training)")
    print("   In production, use historical backtest trades for training")
