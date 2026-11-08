"""fxengine — motor de análise gráfica, quantitativa e fundamentalista de Forex e metais
para identificar a melhor entrada a mercado (execução imediata) no preço spot ao vivo."""
from .config import Settings
from .engine import Engine, Opportunity, ScanResult

__all__ = ["Engine", "Settings", "Opportunity", "ScanResult"]
__version__ = "1.0.0"
