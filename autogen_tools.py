"""
losbeto_tools.autogen_tools
=============================

Integração AutoGen / AG2 para o catálogo Losbeto. AutoGen não tem uma classe
"Tool" própria como CrewAI — o padrão é função Python simples + schema JSON
registrado via `register_function` (ou passado direto em `llm_config` para
frameworks que aceitam function-calling cru). Este módulo entrega os dois.

Uso (ConversableAgent / AG2):
    pip install losbeto-tools[autogen]

    from losbeto_tools import get_autogen_functions
    from autogen import ConversableAgent, register_function

    funcs = get_autogen_functions()  # dict {name: (callable, schema)}

    assistant = ConversableAgent("analista", llm_config={...})
    user_proxy = ConversableAgent("executor", human_input_mode="NEVER")

    for name, (fn, schema) in funcs.items():
        register_function(
            fn, caller=assistant, executor=user_proxy,
            name=name, description=schema["description"],
        )

Ou, se seu setup já monta o llm_config com "tools" no formato OpenAI:
    from losbeto_tools import get_autogen_schemas
    llm_config = {"tools": get_autogen_schemas(), ...}
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, Tuple

import requests

LOSBETO_BASE = "https://api.losbeto.xyz"
_TIMEOUT_S = 15

# Mesmo catálogo curado do wrapper CrewAI — mantidos em arquivos separados
# de propósito (frameworks diferentes, dependências diferentes; um usuário
# só de AutoGen não deveria precisar instalar pydantic/crewai).
_ENDPOINTS = [
    ("/br-brief", "losbeto_brazil_brief",
     "Brazil in global context: BCB macro, real interest rate, Ibovespa "
     "and B3 blue chips, with strategist synthesis.", []),
    ("/br-macro", "losbeto_brazil_macro",
     "Selic, CDI, IPCA, IGP-M and official PTAX, assembled from separate "
     "Brazilian Central Bank series.", []),
    ("/br-curve", "losbeto_brazil_rate_curve",
     "Selic, CDI annualised (252-business-day convention), TJLP and IPCA, "
     "plus the real rate via the Fisher relation.", []),
    ("/br-equity", "losbeto_brazil_equity",
     "B3 quote (PETR4, VALE3, ITUB4 or Ibovespa) in BRL and USD at the "
     "official PTAX rate.", ["symbol"]),
    ("/oracle-consensus", "losbeto_oracle_consensus",
     "Price consensus across Pyth, Coinbase, Kraken, Binance and CoinGecko "
     "in parallel, with spread in bps and outlier detection.", ["symbol"]),
    ("/sentiment-consensus", "losbeto_sentiment_consensus",
     "Four independent crypto market sentiment measures with divergence "
     "detection.", []),
    ("/correlation-matrix", "losbeto_correlation_matrix",
     "90-day cross-asset correlations: crypto vs S&P, Nasdaq, gold, oil, "
     "the dollar and 20Y treasuries.", []),
    ("/global-morning-brief", "losbeto_global_morning_brief",
     "Daily cross-asset read: forex, commodities, equities, crypto and "
     "the macro calendar, closed with strategist synthesis.", []),
    ("/equity-dossier", "losbeto_equity_dossier",
     "Quote, earnings, macro context and analyst verdict for any ticker "
     "in one call.", ["symbol"]),
    ("/launch-risk", "losbeto_launch_risk",
     "Pre-execution risk check for a new token: on-chain checks, DEX "
     "liquidity and an avoid/watch/size verdict.", ["symbol"]),
    ("/token-intel", "losbeto_token_intel",
     "Pre-execution screening for any contract or ticker: liquidity, pair "
     "age, buy/sell flow, honeypot and wash-trading signals.", ["symbol"]),
    ("/wallet-scan", "losbeto_wallet_scan",
     "Counterparty enrichment before trusting an address: holdings, "
     "concentration, activity and spam exposure on Solana/Base.", ["address"]),
]


def _fetch_preview(path: str, **params: Any) -> str:
    q = {k: v for k, v in params.items() if v is not None}
    q["preview"] = 1  # real data, delayed ~15min, always free — no wallet
    try:
        r = requests.get(f"{LOSBETO_BASE}{path}", params=q, timeout=_TIMEOUT_S)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        return json.dumps({
            "error": "losbeto_request_failed",
            "detail": str(e),
            "note": ("Sample call failed. For real-time data, pay per call "
                      f"via x402 at {LOSBETO_BASE}{path} (drop preview=1)."),
        })


def _make_callable(path: str) -> Callable[..., str]:
    def _fn(**kwargs: Any) -> str:
        return _fetch_preview(path, **kwargs)
    _fn.__name__ = f"call_{path.strip('/').replace('-', '_')}"
    return _fn


def _schema_for(name: str, description: str, params: list) -> Dict[str, Any]:
    properties = {p: {"type": "string", "description": f"Query param: {p}"}
                  for p in params}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                f"{description} Returns a real, delayed (~15min) free sample, "
                f"no wallet needed. For real-time data, pay per call via x402 "
                f"at the same path."
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [],
            },
        },
    }


def get_autogen_functions() -> Dict[str, Tuple[Callable[..., str], Dict[str, Any]]]:
    """Retorna {nome: (callable, schema_openai_format)} pra registrar com
    `register_function` do AutoGen/AG2."""
    out = {}
    for path, name, desc, params in _ENDPOINTS:
        out[name] = (_make_callable(path), _schema_for(name, desc, params))
    return out


def get_autogen_schemas() -> list:
    """Retorna só os schemas, formato OpenAI tools[], pra colar direto em
    llm_config={"tools": [...]}."""
    return [_schema_for(name, desc, params)
            for _, name, desc, params in _ENDPOINTS]
