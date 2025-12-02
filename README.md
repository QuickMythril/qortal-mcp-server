# Qortal MCP Server (Python)

## Overview

This repository contains a **read‑only Qortal MCP server** implemented in Python.  
It exposes a carefully curated subset of the Qortal Core HTTP API (port `12391`) as
LLM‑friendly tools so that agents (Codex, ChatGPT Agents, etc.) can query on‑chain
and QDN data without any ability to sign or broadcast transactions.

The server runs alongside a Qortal Core node and acts as a safe, structured proxy
for information such as:

- Node status and version
- Account / balance / name information
- Cross‑chain Trade Portal offers
- QDN (Qortal Data Network) search metadata

All write / state‑changing operations are permanently out of scope.

## Status

This project is in early development.

- **v1 goal**: minimal but useful tool set + stable Python server:
  - `get_node_status` – node sync / connectivity status
  - `get_node_info` – version, uptime, node id
  - `get_account_overview` – address info, QORT balance, optional names / assets
  - `get_balance` – simple QORT / asset balance lookup (optional)
  - `validate_address` – utility for checking address format
  - `get_name_info` – single name lookup
  - `get_names_by_address` – names owned by an address
  - `list_trade_offers` – open cross‑chain Trade Portal offers
  - `search_qdn` – constrained search over arbitrary / QDN data

  `get_account_overview` currently returns QORT balance plus names; the
  `assetBalances` field is intentionally left empty in v1 to avoid large payloads.

The first implementation milestone focuses only on `get_node_status` and
`get_account_overview`, then expands from there.

For full details, see **`DESIGN.md`**.

## Security model (short version)

- **Read‑only only** – no signing, no broadcasting, no POST/PUT/DELETE calls.
- Only a **whitelisted set of GET endpoints** under `/admin`, `/addresses`,
  `/names`, `/crosschain/tradeoffers`, `/arbitrary/search`, and a small subset
  of `/assets` will ever be used.
- Tool inputs are validated (addresses, names, service codes, limits, etc.).
- Outputs are trimmed and normalized for LLMs (no huge binary blobs, no logs,
  no sensitive node details).
- The Qortal Core API key (if required) is kept server‑side and never returned
  to callers.

The full security model is documented in **`DESIGN.md`** and enforced via the
rules in **`AGENTS.md`**.

## High‑level architecture

- Python 3.11+
- HTTP server: FastAPI + Uvicorn (or equivalent ASGI server)
- HTTP client to Qortal: `httpx`
- Internal layout (subject to refinement):

  ```text
  qortal_mcp/
    __init__.py
    config.py           # base URL, API key path, timeouts, limits
    qortal_api/
      __init__.py
      client.py         # thin wrappers around whitelisted Qortal HTTP endpoints
    tools/
      __init__.py
      node.py           # node status / info tools
      account.py        # account + balance + names tools
      names.py          # name system helpers
      trade.py          # Trade Portal tools
      qdn.py            # QDN / arbitrary search tools
    server.py           # FastAPI app wiring tools to HTTP routes or MCP interface
  ```

Each tool function is responsible for:

- Validating inputs
- Calling one or more `qortal_api.client` helpers
- Mapping raw Qortal responses into compact JSON results for LLMs
- Handling and normalizing errors

See **`DESIGN.md`** for specifics on each tool and its underlying Qortal
endpoint(s).

## Requirements

- Python **3.11+**
- A running **Qortal Core** node with the HTTP API enabled (default
  `http://localhost:12391`)
- If your Core requires an API key for `/admin/*` endpoints, ensure the MCP
  server can read it (for example from `apikey.txt`, or environment).

## Quick start (once implementation exists)

```bash
# 1. Clone the repo
git clone https://github.com/<your-user-or-org>/qortal-mcp-python.git
cd qortal-mcp-python

# 2. Create a virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# 3. Configure Qortal Core connection (defaults usually OK)
#    e.g. edit config file or set environment variables as described in DESIGN.md

# 4. Run the server (example – adjust module/path once implemented)
uvicorn qortal_mcp.server:app --reload

# (Optional) Quick sanity check against your local Core node
# Override QORTAL_SAMPLE_ADDRESS to another on-chain address if desired.
python scripts/sanity_check.py

# (Optional) Run unit tests
pip install -r requirements-dev.txt
pytest

# (Optional) Live integration tests (require a running Core node)
# Set LIVE_QORTAL=1 and optionally QORTAL_SAMPLE_ADDRESS / QORTAL_SAMPLE_NAME
LIVE_QORTAL=1 pytest tests/test_live_integration.py

## HTTP usage examples

With the server running (default `http://localhost:8000`):

```bash
# Health
curl http://localhost:8000/health

# Metrics snapshot
curl http://localhost:8000/metrics

# Node status
curl http://localhost:8000/tools/node_status

# Account overview
curl http://localhost:8000/tools/account_overview/QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV

# Validate address (no Core call)
curl http://localhost:8000/tools/validate_address/QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV

# Name info
curl http://localhost:8000/tools/name_info/AGAPE

# Trade offers (limit=3)
curl "http://localhost:8000/tools/trade_offers?limit=3"
```

## MCP integration (initialize + tools)

The MCP gateway lives at `POST /mcp` and supports the MCP initialize handshake
plus standard tool methods.

- **Protocol version**: `2025-03-26` (echoed back to the client)
- **Supported methods**:
  - `initialize` → returns `protocolVersion`, `serverInfo`, `capabilities.tools`
  - `tools/list` or `list_tools` → returns the tool catalog
  - `tools/call` or `call_tool` → call a tool by name

Example `initialize` call for debugging:

```bash
curl -sS -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "debug-client",
        "version": "0.0.1"
      }
    }
  }'
```

Tool calls (post-initialize):

```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "validate_address", "arguments": {"address": "Q..."}}}
```

Tool responses include a `content` array with a `text` item plus a
`structuredContent` copy of the JSON result. Tool execution errors set
`isError: true` and return the message as text content. Protocol-level failures
use the JSON-RPC `error` field.

Manifest: `mcp-manifest.json` points at `http://localhost:8000/mcp` with name
`qortal-mcp-server` and version `0.1.0`. Update the endpoint for remote usage.

## Notes on rate limits and logging

- A simple per-tool rate limiter (token bucket) defaults to ~5 requests/second
  per tool to protect the underlying Qortal node. Adjust via `QortalConfig.rate_limit_qps`.
- Logging is minimal and avoids secrets. Adjust log level via `QORTAL_MCP_LOG_LEVEL`.
- Responses include an `X-Request-ID` header for tracing.
- Log format can be switched to JSON with `QORTAL_MCP_LOG_FORMAT=json`. Per-tool
  rate limits can be set in code via `per_tool_rate_limits` if desired.
- `/metrics` returns in-process counters (requests, rate-limited counts, per-tool successes/errors); for multi-worker setups, aggregate externally.

## Testing

- Unit tests: `pytest` (or `pytest --cov=qortal_mcp --cov=tests --cov-report=term-missing` after installing `requirements-dev.txt` which includes `pytest-cov`).
- Live integration (requires a running Qortal node): `LIVE_QORTAL=1 pytest tests/test_live_integration.py` (optionally set `QORTAL_SAMPLE_ADDRESS` / `QORTAL_SAMPLE_NAME`).

## Deployment notes

- Run with uvicorn or gunicorn+uvicorn workers, e.g.:
  - `uvicorn qortal_mcp.server:app --host 0.0.0.0 --port 8000`
  - `gunicorn -k uvicorn.workers.UvicornWorker -w 2 qortal_mcp.server:app`
- Rate limits and metrics are per-process; if you run multiple workers or behind a reverse proxy, consider external aggregation and/or adjust `per_tool_rate_limits`.
- Terminate TLS at a reverse proxy (nginx/caddy/traefik) and restrict access to trusted clients if exposing beyond localhost.
- `/metrics` returns in-process counters (requests, rate-limited counts, per-tool successes/errors).
```

Once running, the server can be wired into your LLM tooling as an MCP server or
as an HTTP tool host, depending on your integration.

### Available tool routes (v1)

- `GET /health`
- `GET /metrics`
- `GET /tools/node_status`
- `GET /tools/node_info`
- `GET /tools/account_overview/{address}`
- `GET /tools/balance/{address}?assetId=0`
- `GET /tools/validate_address/{address}`
- `GET /tools/name_info/{name}`
- `GET /tools/names_by_address/{address}?limit=...`
- `GET /tools/trade_offers?limit=...`
- `GET /tools/qdn_search?address=...&service=...&limit=...`

## Roadmap (short)

1. **Milestone 1**
   - Project skeleton
   - `qortal_api.client`
   - `get_node_status`, `get_account_overview`
2. **Milestone 2**
   - Remaining v1 tools (`get_node_info`, `get_name_info`, etc.)
   - More robust error handling, logging, and tests
3. **Milestone 3**
   - Example agent / MCP integration configs
   - Optional extended tools (DEX views, QDN convenience tools)

See **`DESIGN.md`** for the current authoritative plan.
