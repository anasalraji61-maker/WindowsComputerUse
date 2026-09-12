"""وكلاء متخصصة — الحزمة الكاملة."""
from __future__ import annotations

from cos.agents.business import BusinessAgent
from cos.agents.coding import CodingAgent
from cos.agents.marketing import MarketingAgent
from cos.agents.memory_agent import MemoryAgent
from cos.agents.quant import QuantAgent
from cos.agents.research import ResearchAgent
from cos.agents.supervisor_agent import SupervisorAgent
from cos.agents.trading import TradingAgent

__all__ = [
    "CodingAgent",
    "QuantAgent",
    "TradingAgent",
    "ResearchAgent",
    "BusinessAgent",
    "MarketingAgent",
    "MemoryAgent",
    "SupervisorAgent",
]
