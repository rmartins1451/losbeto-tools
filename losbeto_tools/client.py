"""Cliente Losbeto — descobre os endpoints do nó em tempo de execução.

Decisão de design: NADA de lista de endpoints fixa no pacote. O catálogo é lido
do próprio nó (/.well-known/mcp.json). Assim, um endpoint novo no servidor vira
ferramenta automaticamente, sem precisar publicar versão nova no PyPI.

Dois modos:
  - free  (padrão): usa ?preview=1 — dados reais com atraso, custo zero, sem
           carteira, sem cadastro. Serve para o agente avaliar antes de pagar.
  - paid : passa um `payer` compatível com x402 e o cliente paga por chamada.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

import requests

DEFAULT_BASE = "https://api.losbeto.xyz"
_CATALOG_TTL = 900  # 15 min


class LosbetoError(RuntimeError):
    pass


class LosbetoClient:
    """Acesso aos endpoints do nó Losbeto.

    Args:
        base_url: URL do nó.
        payer:    Opcional. Callable que recebe (url, challenge: dict) e devolve
                  o valor do header ``PAYMENT-SIGNATURE``. Sem isso, o cliente
                  opera em modo gratuito (dados com atraso).
        timeout:  Timeout por requisição, em segundos.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        payer: Optional[Callable[[str, dict], str]] = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.payer = payer
        self.timeout = timeout
        self._catalog: List[Dict[str, Any]] = []
        self._catalog_at: float = 0.0
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "losbeto-tools/1.0 (+pypi.org/project/losbeto-tools)"

    # ------------------------------------------------------------------ #
    def catalog(self, force: bool = False) -> List[Dict[str, Any]]:
        """Lista as ferramentas disponíveis, direto do manifesto do nó."""
        if not force and self._catalog and (time.time() - self._catalog_at) < _CATALOG_TTL:
            return self._catalog
        try:
            r = self._session.get(f"{self.base_url}/.well-known/mcp.json", timeout=self.timeout)
            r.raise_for_status()
            tools = r.json().get("tools") or []
        except Exception as exc:  # pragma: no cover - rede
            raise LosbetoError(f"não consegui ler o catálogo de {self.base_url}: {exc}") from exc

        out = []
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "path": "/" + name.replace("_", "-"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("inputSchema")
                    or {"type": "object", "properties": {}, "required": []},
                }
            )
        self._catalog, self._catalog_at = out, time.time()
        return out

    # ------------------------------------------------------------------ #
    def call(self, tool: str, realtime: bool = False, **params: Any) -> Dict[str, Any]:
        """Chama um endpoint.

        realtime=False (padrão) usa ?preview=1: dado real com atraso, $0.
        realtime=True exige um `payer` configurado; sem ele, levanta LosbetoError.
        """
        path = tool if tool.startswith("/") else "/" + tool.replace("_", "-")
        url = f"{self.base_url}{path}"
        query = {k: v for k, v in params.items() if v is not None}

        if not realtime:
            query["preview"] = "1"
            resp = self._session.get(url, params=query, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # o nó devolve {preview:true, delayed_data:{...}}
            return data.get("delayed_data", data)

        if self.payer is None:
            raise LosbetoError(
                "realtime=True exige um payer x402. Use realtime=False para o "
                "modo gratuito com atraso, ou passe payer=... ao construtor."
            )

        resp = self._session.get(url, params=query, timeout=self.timeout)
        if resp.status_code != 402:
            resp.raise_for_status()
            return resp.json()

        challenge = resp.json()
        signature = self.payer(url, challenge)
        paid = self._session.get(
            url, params=query, headers={"PAYMENT-SIGNATURE": signature}, timeout=self.timeout
        )
        paid.raise_for_status()
        return paid.json()

    # ------------------------------------------------------------------ #
    def tasting_menu(self) -> Dict[str, Any]:
        """Uma chamada grátis com amostras vivas de vários endpoints."""
        r = self._session.get(f"{self.base_url}/try", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def health(self) -> Dict[str, Any]:
        """Estado das fontes de dados e da camada de IA do nó."""
        r = self._session.get(f"{self.base_url}/health/providers", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def price_of(self, tool: str) -> Optional[str]:
        """Preço em USDC do endpoint, lido do desafio 402."""
        path = tool if tool.startswith("/") else "/" + tool.replace("_", "-")
        try:
            r = self._session.get(f"{self.base_url}{path}", timeout=self.timeout)
            if r.status_code == 402:
                accepts = r.json().get("accepts") or []
                if accepts:
                    amount = int(accepts[0].get("amount", 0))
                    return f"{amount / 1_000_000:.4f}"
        except Exception:
            pass
        return None

    def __repr__(self) -> str:  # pragma: no cover
        mode = "paid" if self.payer else "free"
        return f"<LosbetoClient {self.base_url} mode={mode}>"
