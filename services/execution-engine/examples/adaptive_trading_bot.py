#!/usr/bin/env python3
"""
🤖 ADAPTIVE TRADING BOT - Exemplo de uso do Market Regime Detector

Este bot demonstra 3 formas de usar o detector de regime:

1. MODO MANUAL: Consulta antes de iniciar trading
2. MODO ADAPTATIVO: Monitora e troca estratégia automaticamente
3. MODO INTELIGENTE: Decide se deve ou não tradear baseado no regime

Autor: CryptoDev Assistant
Data: 2025-12-11
"""

import requests
import time
from datetime import datetime
from typing import Dict, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdaptiveTradingBot:
    """
    Bot de trading adaptativo que ajusta estratégia baseado no regime de mercado
    """
    
    def __init__(self, 
                 api_url: str = "http://localhost:3008",
                 symbol: str = "BTCUSDT",
                 interval: str = "1h"):
        """
        Inicializa o bot adaptativo
        
        Args:
            api_url: URL da API do Execution Engine
            symbol: Par de trading
            interval: Timeframe
        """
        self.api_url = api_url
        self.symbol = symbol
        self.interval = interval
        self.current_strategy = None
        self.current_regime = None
        self.session_id = None
        
    # ==========================================
    # 1. MODO MANUAL - Consulta única
    # ==========================================
    
    def get_recommended_strategy(self) -> str:
        """
        Consulta a melhor estratégia para o mercado atual (uso simples)
        
        Returns:
            Nome da estratégia recomendada
        """
        logger.info(f"🔍 Consultando melhor estratégia para {self.symbol}...")
        
        try:
            response = requests.get(
                f"{self.api_url}/api/strategy/best",
                params={
                    "symbol": self.symbol,
                    "interval": self.interval,
                    "lookback_days": 90
                }
            )
            response.raise_for_status()
            
            data = response.json()
            strategy = data['strategy']
            
            logger.info(f"✅ Estratégia recomendada: {strategy}")
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Erro ao consultar estratégia: {e}")
            raise
    
    def get_full_analysis(self) -> Dict:
        """
        Obtém análise completa do mercado com conselhos de trading
        
        Returns:
            Dict com análise completa (regime, estratégias, conselhos)
        """
        logger.info(f"📊 Obtendo análise completa do mercado...")
        
        try:
            response = requests.post(
                f"{self.api_url}/api/strategy/auto-select",
                json={
                    "symbol": self.symbol,
                    "interval": self.interval,
                    "lookback_days": 90
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Log da análise
            regime = data['market_analysis']['regime']
            confidence = data['market_analysis']['confidence']
            primary_strategy = data['strategy_recommendation']['primary']
            should_trade = data['trading_advice']['should_trade']
            risk_level = data['trading_advice']['risk_level']
            
            logger.info(f"📊 Regime: {regime.upper()} ({confidence:.1f}% confiança)")
            logger.info(f"🎯 Estratégia: {primary_strategy}")
            logger.info(f"🎲 Risco: {risk_level.upper()}")
            logger.info(f"🚦 Deve tradear? {'SIM' if should_trade else 'NÃO'}")
            
            # Warnings
            for warning in data['trading_advice']['warnings']:
                logger.warning(f"⚠️  {warning}")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter análise: {e}")
            raise
    
    # ==========================================
    # 2. MODO ADAPTATIVO - Monitoramento contínuo
    # ==========================================
    
    def should_change_strategy(self) -> Dict:
        """
        Verifica se a estratégia atual ainda é apropriada
        
        Returns:
            Dict indicando se deve mudar e qual nova estratégia usar
        """
        if not self.current_strategy:
            logger.warning("⚠️  Nenhuma estratégia ativa. Use start_adaptive_trading() primeiro.")
            return None
        
        logger.info(f"🔄 Verificando se estratégia '{self.current_strategy}' ainda é apropriada...")
        
        try:
            response = requests.post(
                f"{self.api_url}/api/strategy/should-change",
                json={
                    "current_strategy": self.current_strategy,
                    "symbol": self.symbol,
                    "interval": self.interval
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data['should_change']:
                logger.warning(
                    f"⚠️  RECOMENDAÇÃO DE MUDANÇA:\n"
                    f"   De: {data['current_strategy']}\n"
                    f"   Para: {data['recommended_strategy']}\n"
                    f"   Motivo: {data['reason']}"
                )
            else:
                logger.info(f"✅ Estratégia {self.current_strategy} ainda é apropriada")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar mudança: {e}")
            raise
    
    def monitor_regime_changes(self, check_interval: int = 3600):
        """
        Monitora regime de mercado continuamente e alerta sobre mudanças
        
        Args:
            check_interval: Intervalo entre verificações (segundos)
        """
        logger.info(f"👁️  Iniciando monitoramento de regime (verificando a cada {check_interval/60:.0f} min)...")
        
        try:
            while True:
                # Obter análise atual
                analysis = self.get_full_analysis()
                
                new_regime = analysis['market_analysis']['regime']
                confidence = analysis['market_analysis']['confidence']
                recommended = analysis['strategy_recommendation']['primary']
                
                # Detectar mudança de regime
                if self.current_regime and new_regime != self.current_regime:
                    logger.critical(
                        f"🚨 MUDANÇA DE REGIME DETECTADA!\n"
                        f"   De: {self.current_regime.upper()}\n"
                        f"   Para: {new_regime.upper()}\n"
                        f"   Confiança: {confidence:.1f}%\n"
                        f"   Nova estratégia recomendada: {recommended}"
                    )
                    
                    # Aqui você pode adicionar lógica para:
                    # - Enviar notificação (email, Telegram, etc)
                    # - Trocar estratégia automaticamente
                    # - Fechar posições abertas
                    # - Ajustar parâmetros de risco
                
                # Atualizar estado
                self.current_regime = new_regime
                
                # Aguardar próxima verificação
                logger.info(f"⏳ Próxima verificação em {check_interval/60:.0f} minutos...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Monitoramento interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro no monitoramento: {e}")
            raise
    
    # ==========================================
    # 3. MODO INTELIGENTE - Trading adaptativo
    # ==========================================
    
    def start_adaptive_trading(self):
        """
        Inicia paper trading com estratégia adaptativa
        
        1. Analisa o mercado
        2. Escolhe a melhor estratégia
        3. Inicia paper trading
        4. Monitora e adapta conforme necessário
        """
        logger.info("🚀 Iniciando trading adaptativo...")
        
        # 1. Obter análise completa
        analysis = self.get_full_analysis()
        
        # 2. Verificar se deve tradear
        should_trade = analysis['trading_advice']['should_trade']
        if not should_trade:
            logger.error(
                "🚫 TRADING NÃO RECOMENDADO!\n"
                f"   Motivo: {analysis['trading_advice']['warnings']}"
            )
            return False
        
        # 3. Obter estratégia recomendada
        strategy = analysis['strategy_recommendation']['primary']
        position_multiplier = analysis['trading_advice']['position_size_multiplier']
        
        # 4. Ajustar parâmetros baseado no risco
        initial_balance = 10000.0
        if position_multiplier < 1.0:
            logger.warning(f"⚠️  Reduzindo capital inicial devido ao risco: {position_multiplier}x")
            initial_balance *= position_multiplier
        
        # 5. Iniciar paper trading
        logger.info(
            f"🎯 Iniciando paper trading:\n"
            f"   Estratégia: {strategy}\n"
            f"   Capital: ${initial_balance:.2f}\n"
            f"   Regime: {analysis['market_analysis']['regime'].upper()}\n"
            f"   Confiança: {analysis['market_analysis']['confidence']:.1f}%"
        )
        
        try:
            response = requests.post(
                f"{self.api_url}/paper-trading/start",
                json={
                    "session_id": f"adaptive_{int(time.time())}",
                    "strategy_name": strategy,
                    "symbol": self.symbol,
                    "initial_balance": initial_balance,
                    "leverage": 1  # Sem alavancagem para segurança
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self.session_id = data['session_id']
            self.current_strategy = strategy
            self.current_regime = analysis['market_analysis']['regime']
            
            logger.info(f"✅ Paper trading iniciado! Session ID: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar paper trading: {e}")
            raise


# ==========================================
# EXEMPLOS DE USO
# ==========================================

def example_1_manual_query():
    """
    Exemplo 1: Consulta manual antes de iniciar trading
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 1: Consulta Manual")
    print("=" * 80 + "\n")
    
    bot = AdaptiveTradingBot()
    
    # Forma simples: apenas o nome da estratégia
    strategy = bot.get_recommended_strategy()
    print(f"\n🎯 Melhor estratégia: {strategy}\n")
    
    # Forma completa: análise detalhada
    analysis = bot.get_full_analysis()
    print(f"\n✅ Análise completa obtida!\n")


def example_2_adaptive_monitoring():
    """
    Exemplo 2: Monitoramento contínuo com adaptação
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 2: Monitoramento Adaptativo")
    print("=" * 80 + "\n")
    
    bot = AdaptiveTradingBot()
    
    # Iniciar com uma estratégia
    bot.current_strategy = "momentum"
    bot.current_regime = "bull"
    
    # Verificar se ainda é apropriada
    result = bot.should_change_strategy()
    
    if result and result['should_change']:
        print(f"\n⚠️  Recomendado trocar para: {result['recommended_strategy']}\n")
    else:
        print("\n✅ Estratégia atual ainda é apropriada\n")


def example_3_intelligent_trading():
    """
    Exemplo 3: Trading inteligente que se adapta ao mercado
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 3: Trading Inteligente e Adaptativo")
    print("=" * 80 + "\n")
    
    bot = AdaptiveTradingBot()
    
    # Iniciar trading adaptativo
    # (vai analisar mercado, escolher estratégia, e iniciar)
    success = bot.start_adaptive_trading()
    
    if success:
        print("\n✅ Trading adaptativo iniciado com sucesso!\n")
        print("💡 O bot agora está:")
        print("   1. Usando a estratégia mais apropriada para o regime atual")
        print("   2. Ajustado o tamanho de posição baseado no risco")
        print("   3. Pronto para se adaptar a mudanças de mercado")
    else:
        print("\n❌ Trading não iniciado (condições de mercado desfavoráveis)\n")


def example_4_continuous_monitoring():
    """
    Exemplo 4: Monitoramento contínuo (rode em background)
    """
    print("\n" + "=" * 80)
    print("EXEMPLO 4: Monitoramento Contínuo")
    print("=" * 80 + "\n")
    print("⚠️  Este exemplo roda indefinidamente!")
    print("💡 Pressione Ctrl+C para parar\n")
    
    bot = AdaptiveTradingBot()
    
    # Monitorar a cada 1 hora
    bot.monitor_regime_changes(check_interval=3600)


if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                     🤖 ADAPTIVE TRADING BOT - Exemplos                       ║
║                                                                              ║
║  Este script demonstra como usar o Market Regime Detector na prática        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) < 2:
        print("Uso: python adaptive_trading_bot.py [exemplo]")
        print("\nExemplos disponíveis:")
        print("  1 - Consulta manual (recomendado para começar)")
        print("  2 - Monitoramento adaptativo")
        print("  3 - Trading inteligente")
        print("  4 - Monitoramento contínuo (background)")
        print("\nExemplo: python adaptive_trading_bot.py 1")
        sys.exit(1)
    
    example = sys.argv[1]
    
    if example == "1":
        example_1_manual_query()
    elif example == "2":
        example_2_adaptive_monitoring()
    elif example == "3":
        example_3_intelligent_trading()
    elif example == "4":
        example_4_continuous_monitoring()
    else:
        print(f"❌ Exemplo '{example}' não encontrado!")
        sys.exit(1)
