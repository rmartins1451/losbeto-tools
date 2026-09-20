"""Adaptadores para frameworks de agentes.

As ferramentas são geradas a partir do catálogo vivo do nó, então a lista
acompanha o servidor sem precisar de release novo do pacote.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from .client import DEFAULT_BASE, LosbetoClient

# Conjunto enxuto e útil por padrão — evita despejar 67 ferramentas no prompt
# do agente (o que consome contexto e piora a escolha do modelo).
DEFAULT_TOOLS = [
    "forex_rate",
    "stock_quote",
    "commodity_price",
    "macro_calendar",
    "fear_greed",
    "pyth_price",
    "regime",
    "global_morning_brief",
]


def _describe(entry: Dict[str, Any], price: Optional[str]) -> str:
    desc = entry["description"]
    if price:
        desc += f" [Free delayed data; real-time costs {price} USDC per call.]"
    return desc[:1000]


def _make_fn(client: LosbetoClient, name: str, realtime: bool) -> Callable[..., str]:
    def _run(**kwargs: Any) -> str:
        try:
            data = client.call(name, realtime=realtime, **kwargs)
            return json.dumps(data, ensure_ascii=False, default=str)[:6000]
        except Exception as exc:
            return json.dumps({"error": str(exc)[:300]})

    _run.__name__ = name
    return _run


def _select(client: LosbetoClient, include: Optional[List[str]], all_tools: bool):
    catalog = client.catalog()
    if all_tools:
        return catalog
    wanted = set(include or DEFAULT_TOOLS)
    chosen = [e for e in catalog if e["name"] in wanted]
    return chosen or catalog[:8]


# --------------------------------------------------------------------------- #
def get_langchain_tools(
    base_url: str = DEFAULT_BASE,
    payer: Optional[Callable[[str, dict], str]] = None,
    include: Optional[List[str]] = None,
    all_tools: bool = False,
    realtime: bool = False,
):
    """Ferramentas LangChain (`StructuredTool`).

        from losbeto_tools import get_langchain_tools
        tools = get_langchain_tools()          # grátis, dados com atraso
        agent = create_react_agent(llm, tools)
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "LangChain não encontrado. Instale com: pip install 'losbeto-tools[langchain]'"
        ) from exc

    client = LosbetoClient(base_url=base_url, payer=payer)
    tools = []
    for entry in _select(client, include, all_tools):
        name = entry["name"]
        tools.append(
            StructuredTool.from_function(
                func=_make_fn(client, name, realtime),
                name=f"losbeto_{name}",
                description=_describe(entry, client.price_of(name) if realtime else None),
                args_schema=None,
                infer_schema=False,
            )
        )
    return tools


# --------------------------------------------------------------------------- #
def get_crewai_tools(
    base_url: str = DEFAULT_BASE,
    payer: Optional[Callable[[str, dict], str]] = None,
    include: Optional[List[str]] = None,
    all_tools: bool = False,
    realtime: bool = False,
):
    """Ferramentas CrewAI. CrewAI aceita ferramentas LangChain, então
    reaproveitamos o mesmo adaptador."""
    return get_langchain_tools(
        base_url=base_url, payer=payer, include=include,
        all_tools=all_tools, realtime=realtime,
    )


# --------------------------------------------------------------------------- #
def get_openai_tools(
    base_url: str = DEFAULT_BASE,
    include: Optional[List[str]] = None,
    all_tools: bool = False,
) -> List[Dict[str, Any]]:
    """Schemas no formato de function-calling da OpenAI (também serve para
    AutoGen). Devolve (schemas, dispatcher) via `openai_dispatcher`."""
    client = LosbetoClient(base_url=base_url)
    out = []
    for entry in _select(client, include, all_tools):
        out.append(
            {
                "type": "function",
                "function": {
                    "name": f"losbeto_{entry['name']}",
                    "description": _describe(entry, None),
                    "parameters": entry["input_schema"],
                },
            }
        )
    return out


def openai_dispatcher(base_url: str = DEFAULT_BASE, realtime: bool = False,
                      payer: Optional[Callable[[str, dict], str]] = None):
    """Executor para os schemas de `get_openai_tools`."""
    client = LosbetoClient(base_url=base_url, payer=payer)

    def _dispatch(tool_name: str, arguments: Dict[str, Any] | str) -> str:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
        name = tool_name[len("losbeto_"):] if tool_name.startswith("losbeto_") else tool_name
        try:
            data = client.call(name, realtime=realtime, **arguments)
            return json.dumps(data, ensure_ascii=False, default=str)[:6000]
        except Exception as exc:
            return json.dumps({"error": str(exc)[:300]})

    return _dispatch
