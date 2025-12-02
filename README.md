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
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure Qortal Core connection (defaults usually OK)
#    e.g. edit config file or set environment variables as described in DESIGN.md

# 4. Run the server (example – adjust module/path once implemented)
uvicorn qortal_mcp.server:app --reload
```

Once running, the server can be wired into your LLM tooling as an MCP server or
as an HTTP tool host, depending on your integration.

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
