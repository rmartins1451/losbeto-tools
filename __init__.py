"""losbeto-tools — dados de mercado cross-asset para agentes de IA, via x402.

Grátis por padrão (dados reais com atraso). Pagamento por chamada em USDC
apenas quando você quiser tempo real.

    from losbeto_tools import get_langchain_tools
    tools = get_langchain_tools()

v1.1.0: CrewAI nativo (BaseTool), AutoGen/AG2 e schemas OpenAI+Anthropic.
"""
from .client import LosbetoClient, LosbetoError, DEFAULT_BASE
from .adapters import (
    get_langchain_tools,
    get_openai_tools,
    openai_dispatcher,
    DEFAULT_TOOLS,
)
from .autogen_tools import get_autogen_functions, get_autogen_schemas

__version__ = "1.1.0"


def get_crewai_tools(*args, **kwargs):
    """Ferramentas CrewAI nativas (12 BaseTool). Import preguiçoso de
    propósito: crewai+pydantic são extras opcionais — sem eles, o resto do
    pacote continua importando só com requests.
    Instale com: pip install losbeto-tools[crewai]"""
    from .crewai_tools import get_crewai_tools as _impl
    return _impl(*args, **kwargs)


def get_function_schemas() -> dict:
    """Espelho offline do https://api.losbeto.xyz/.well-known/function-schemas.json
    (schemas OpenAI + Anthropic dos 12 endpoints curados)."""
    import json
    from importlib.resources import files
    p = files("losbeto_tools").joinpath("function_schemas.json")
    return json.loads(p.read_text(encoding="utf-8"))


__all__ = [
    # 1.0.0 — preservados (retrocompatibilidade)
    "LosbetoClient", "LosbetoError", "DEFAULT_BASE", "DEFAULT_TOOLS",
    "get_langchain_tools", "get_openai_tools", "openai_dispatcher",
    # 1.1.0 — novos
    "get_crewai_tools", "get_autogen_functions", "get_autogen_schemas",
    "get_function_schemas",
]
