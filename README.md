# losbeto-tools

Cross-asset market data for AI agents — **forex, equities, commodities, macro and crypto** — over the [x402](https://x402.org) payment protocol.

**Free by default.** Every tool returns real, delayed data at zero cost, with no wallet, no API key and no signup. Pay per call in USDC only when your agent needs real-time.

```bash
pip install losbeto-tools[langchain]
```

## LangChain

```python
from losbeto_tools import get_langchain_tools

tools = get_langchain_tools()          # free, delayed data
agent = create_react_agent(llm, tools) # your usual agent setup
```

## CrewAI

```python
from losbeto_tools import get_crewai_tools

analyst = Agent(role="Macro Analyst", tools=get_crewai_tools(), llm=llm)
```


## What's new in 1.1.0

- **Native CrewAI tools** — `get_crewai_tools()` now returns 12 purpose-built
  `crewai.tools.BaseTool` instances (curated flagship endpoints). Install with
  `pip install losbeto-tools[crewai]`. The old LangChain-adapter path still
  works via `losbeto_tools.adapters`.
- **AutoGen / AG2 support** — `get_autogen_functions()` returns
  `{name: (callable, schema)}` ready for `register_function`;
  `get_autogen_schemas()` returns OpenAI-format `tools[]` for `llm_config`.
  Install with `pip install losbeto-tools[autogen]`.
- **Function schemas offline** — `get_function_schemas()` returns the same
  OpenAI + Anthropic schemas the node serves at
  `https://api.losbeto.xyz/.well-known/function-schemas.json`.

```python
from losbeto_tools import get_autogen_functions
funcs = get_autogen_functions()   # 12 tools, free ?preview=1 data by default
```


## OpenAI function calling / AutoGen

```python
from losbeto_tools import get_openai_tools, openai_dispatcher

tools    = get_openai_tools()
dispatch = openai_dispatcher()

resp = client.chat.completions.create(model="...", messages=msgs, tools=tools)
for call in resp.choices[0].message.tool_calls:
    result = dispatch(call.function.name, call.function.arguments)
```

## Direct client

```python
from losbeto_tools import LosbetoClient

c = LosbetoClient()
c.call("forex_rate", pair="EUR/USD")   # free, delayed
c.tasting_menu()                       # live samples from 6 endpoints, one call
c.health()                             # per-source liveness of the node
c.price_of("equity_dossier")           # price in USDC
```

## Real-time (paid)

Real-time data settles per call in USDC on Base or Solana. Provide a `payer`
callable that signs the x402 challenge:

```python
def payer(url, challenge):
    # sign `challenge` with your x402 client and return the PAYMENT-SIGNATURE value
    ...

c = LosbetoClient(payer=payer)
c.call("forex_rate", pair="EUR/USD", realtime=True)
```

## What's available

Tools are discovered **at runtime** from the node's own manifest, so the list
tracks the server and never goes stale. A compact default set is exposed to keep
agent prompts small; pass `all_tools=True` for the full catalog (86 per-call endpoints, $0.003–$1.00 each, plus 9 plans).

| Area | Examples |
|---|---|
| Forex | EUR/USD, GBP/USD, USD/JPY, triangular arbitrage |
| Equities | quotes, single-stock AI dossiers, sector rotation |
| Commodities | gold, silver, WTI, Brent, copper, natural gas |
| Macro | FOMC / NFP / CPI / ECB calendar, event playbooks, regime |
| Crypto | Pyth oracle prices, fear & greed, DEX screening, rug checks |
| Research | daily cross-asset morning brief, 90-day correlation matrix |

## Notes

- Free mode returns data delayed roughly 15 minutes — enough to evaluate shape
  and quality before paying.
- If an upstream data source or the AI layer is down, premium endpoints return
  HTTP 503 and **do not charge**.
- Node status is public: `GET https://api.losbeto.xyz/health/providers`
- Operator test purchases are labeled versus organic on-chain at `/receipts`.

MIT licensed.
