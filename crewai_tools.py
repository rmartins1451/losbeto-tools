"""
losbeto_tools.crewai_tools
===========================

Integração CrewAI para o catálogo Losbeto — mesma filosofia do
`get_langchain_tools()` que já existe no pacote: cada ferramenta chama o
node com `?preview=1` (amostra real, atrasada, sem custo e sem wallet), pra
o agente CrewAI decidir se aquele dado é útil ANTES de qualquer pagamento
entrar em cena. Quando o dev do agente quiser dado em tempo real, troca o
wrapper HTTP por um cliente x402 (agentcash, x402-fetch) na mesma URL.

Por que isso importa mais do que estar em mais um diretório: um agente
construído com CrewAI que importa `get_crewai_tools()` já sai da fábrica
com Losbeto na caixa de ferramentas — ele nunca precisou "descobrir" o
node em lugar nenhum. É a mesma lógica por trás da Apify ter levado 20 mil
Actors pra dentro do x402 de uma vez: entrar onde o agente já vive, não
esperar ele procurar.

Uso:
    pip install losbeto-tools[crewai]

    from losbeto_tools import get_crewai_tools
    from crewai import Agent

    agent = Agent(
        role="Analista de mercado",
        goal="Cobrir Brasil e cross-asset pro desk",
        tools=get_crewai_tools(),
    )

Requisitos: crewai>=0.80 (usa `crewai.tools.BaseTool`, API estável desde
a reescrita de tools em pydantic). Se seu crewai for mais antigo, veja a
nota de compat no fim deste arquivo.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

import requests

try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "get_crewai_tools() precisa de crewai + pydantic instalados. "
        "Rode: pip install losbeto-tools[crewai]"
    ) from e

LOSBETO_BASE = "https://api.losbeto.xyz"
_TIMEOUT_S = 15

# ---------------------------------------------------------------------------
# Catálogo curado — os endpoints flagship que fazem sentido como ferramenta
# de agente de propósito geral. O catálogo completo (86 endpoints per-call) fica em
# GET /llms-full.txt; aqui é só o subconjunto que um agente de mercado/
# pesquisa chamaria sem precisar de contexto extra pra saber que existe.
# ---------------------------------------------------------------------------
_ENDPOINTS = [
    ("/br-brief", "losbeto_brazil_brief",
     "Brasil em contexto global: macro do BCB, taxa de juro real, Ibovespa "
     "e blue chips B3, com síntese de estrategista. Use para qualquer "
     "pergunta sobre economia ou mercado brasileiro."),
    ("/br-macro", "losbeto_brazil_macro",
     "Selic, CDI, IPCA, IGP-M e PTAX oficial, montados a partir de séries "
     "separadas do Banco Central."),
    ("/br-curve", "losbeto_brazil_rate_curve",
     "Selic, CDI anualizado (base 252 dias úteis), TJLP e IPCA, mais a "
     "taxa real pela relação de Fisher."),
    ("/br-equity", "losbeto_brazil_equity",
     "Cotação B3 (PETR4, VALE3, ITUB4 ou Ibovespa) em BRL e USD ao PTAX "
     "oficial. Parâmetro: symbol."),
    ("/oracle-consensus", "losbeto_oracle_consensus",
     "Consenso de preço entre Pyth, Coinbase, Kraken, Binance e CoinGecko "
     "em paralelo, com spread em bps e detecção de outlier. Parâmetro: "
     "symbol (ex.: SOL, BTC, ETH)."),
    ("/sentiment-consensus", "losbeto_sentiment_consensus",
     "Quatro medidas independentes de sentimento de mercado cripto, com "
     "detecção de divergência entre elas."),
    ("/correlation-matrix", "losbeto_correlation_matrix",
     "Correlação cross-asset de 90 dias: cripto contra S&P, Nasdaq, ouro, "
     "petróleo, dólar e treasuries de 20 anos."),
    ("/global-morning-brief", "losbeto_global_morning_brief",
     "Leitura cross-asset diária: forex, commodities, ações, cripto e "
     "calendário macro, fechada com síntese de estrategista."),
    ("/equity-dossier", "losbeto_equity_dossier",
     "Cotação, resultados, contexto macro e veredito de analista para "
     "qualquer ticker, numa chamada só. Parâmetro: symbol."),
    ("/launch-risk", "losbeto_launch_risk",
     "Checagem de risco pré-execução para um token novo: liquidez em DEX, "
     "verificação on-chain e veredito (avoid/watch/size)."),
    ("/token-intel", "losbeto_token_intel",
     "Triagem pré-execução de qualquer contrato ou ticker: liquidez, idade "
     "do par, fluxo de compra/venda, sinais de honeypot e wash-trading."),
    ("/wallet-scan", "losbeto_wallet_scan",
     "Enriquecimento de contraparte antes do agente confiar num endereço: "
     "holdings, concentração, atividade e exposição a spam em Solana/Base."),
]


class _LosbetoToolInput(BaseModel):
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Parâmetros de query opcionais para este endpoint, ex.: "
            '{"symbol": "SOL"}. Deixe vazio se o endpoint não precisar de nenhum.'
        ),
    )


def _fetch_preview(path: str, params: Optional[Dict[str, Any]]) -> str:
    q = dict(params or {})
    q["preview"] = 1  # amostra real, atrasada, sempre grátis — sem wallet
    try:
        r = requests.get(f"{LOSBETO_BASE}{path}", params=q, timeout=_TIMEOUT_S)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        return json.dumps({
            "error": "losbeto_request_failed",
            "detail": str(e),
            "note": (
                "Sample call failed. For real-time data with no delay, pay "
                "per call via x402 at the same path (no preview=1) — see "
                f"{LOSBETO_BASE}/.well-known/x402.json"
            ),
        })


def _make_tool(path: str, name: str, description: str) -> BaseTool:
    full_description = (
        f"{description} Retorna uma amostra real dos dados, atrasada ~15min, "
        f"sem custo. Para dado em tempo real, pague por chamada via x402 no "
        f"mesmo endpoint ({LOSBETO_BASE}{path}) — sem conta, sem chave de API."
    )

    class _LosbetoTool(BaseTool):
        name: str = name
        description: str = full_description
        args_schema: Type[BaseModel] = _LosbetoToolInput

        def _run(self, params: Optional[Dict[str, Any]] = None) -> str:
            return _fetch_preview(path, params)

    _LosbetoTool.__name__ = f"LosbetoTool_{name}"
    return _LosbetoTool()


def get_crewai_tools(endpoints: Optional[List[str]] = None) -> List[BaseTool]:
    """Retorna a lista de Tools CrewAI prontas pra usar.

    Args:
        endpoints: lista opcional de paths (ex.: ["/oracle-consensus"]) pra
            restringir o conjunto. Sem isso, retorna o catálogo curado
            inteiro (12 ferramentas).
    """
    chosen = _ENDPOINTS if endpoints is None else [
        e for e in _ENDPOINTS if e[0] in endpoints
    ]
    return [_make_tool(path, name, desc) for path, name, desc in chosen]


# ---------------------------------------------------------------------------
# Nota de compatibilidade: versões de crewai anteriores à reescrita em
# pydantic (pré-0.80) usavam `crewai_tools.BaseTool` num módulo separado,
# com a mesma assinatura de `_run`. Se seu projeto está numa versão antiga
# e o import acima falhar, troque só a linha de import por:
#     from crewai_tools import BaseTool
# o resto deste arquivo funciona sem mudança.
# ---------------------------------------------------------------------------
