# Qortal MCP Server – Design

This document describes the design of the Qortal MCP server implemented in
Python. It covers goals, security model, tool catalog, architecture, and
implementation milestones.

The content below is distilled from a deeper analysis of the Qortal Core
codebase and HTTP API surface. fileciteturn0file0turn0file1

---

## 1. Goals & scope

### 1.1 Purpose

The Qortal MCP server acts as a **read‑only bridge** between Qortal Core and
LLM agents (Codex, ChatGPT Agents, etc.). It exposes a small set of well‑typed
tools that allow agents to:

- Check node health and version
- Inspect account / balance / name information
- Discover open cross‑chain Trade Portal offers
- Search QDN / arbitrary transaction metadata

All tools are **non‑mutating**: they never sign or broadcast transactions and
never attempt to change node configuration or network state. fileciteturn0file0

### 1.2 Out of scope

The following remain out of scope for v1 and likely for the lifetime of this
project:

- Building or broadcasting any transaction (names, assets, trades, etc.)
- Interacting with `/transactions` APIs
- Changing node configuration, peers, or chain state
- Publishing QDN content
- Handling private keys, seeds, or wallet passwords in any form fileciteturn0file0

---

## 2. Security model

The central design constraint is **safety**: an LLM must not be able to cause
harm to the Qortal node or leak sensitive information through this server.

### 2.1 Endpoint whitelist

The server only uses a curated subset of **GET** endpoints that Qortal Core
exposes. These are considered read‑only and safe when combined with sane
limits and validation: fileciteturn0file0

- `/admin/status`, `/admin/info`, `/admin/uptime`, `/admin/summary`
- `/addresses/{address}`
- `/addresses/balance/{address}`
- `/addresses/validate/{address}` (optionally, for validation)
- `/addresses/online` (optional, for online minting accounts)
- `/names/{name}`
- `/names/address/{address}`
- `/names/forsale` (deferred)
- `/crosschain/tradeoffers`
- `/arbitrary/search`
- A small subset of `/assets/*` read‑only endpoints (DEX views – deferred)

No POST/PUT/DELETE operations are ever used. No endpoints that require
transaction payloads or private keys are exposed. fileciteturn0file0

### 2.2 Input validation

For every tool, the server validates inputs **before** calling Qortal Core: fileciteturn0file0

- **Addresses** – must match Qortal address format (Q‑prefixed Base58,
  correct length).
- **Names** – must follow Qortal name rules (valid characters, length).
- **Service codes / IDs** – must be integers in a safe range.
- **limit / offset** – always clamped to internal maxima (e.g. `limit <= 100`).

Invalid inputs are rejected early with structured JSON errors; Core is not
called for obviously bad data.

### 2.3 Output limits & sanitization

To keep results safe and LLM‑friendly: fileciteturn0file0

- Large lists are truncated to internal maximums (e.g. at most 100 entries).
- Long text fields may be truncated with an explicit `"… (truncated)"` suffix.
- Large or binary QDN payloads are not returned in v1; tools focus on
  metadata (signatures, service codes, timestamps, publishers).
- Errors from Qortal are mapped to concise JSON objects such as
  `{"error": "Invalid Qortal address."}`.

### 2.4 Authentication & API key handling

Some Qortal admin endpoints (e.g. `/admin/status`) may require an API key. fileciteturn0file0

- The MCP server reads the Qortal API key from configuration (e.g. a local
  file or environment variable).
- The key is added to outbound requests when needed.
- The key is never logged or returned to callers.
- If a key is missing or incorrect, the tool returns an appropriate error
  instead of leaking details about the underlying failure.

### 2.5 Rate limiting

To protect both the node and LLM context, the server should enforce basic
rate limits, especially for heavier tools (QDN search, trade listings):

- Reasonable per‑tool QPS caps (e.g. a few requests per second at most).
- Optional global concurrency limits.

Exact values can be tuned as real usage patterns become clear.

---

## 3. Tool catalog (v1)

This section lists the planned tools, grouped by category. Each entry notes
its purpose, inputs, outputs, backing Qortal endpoints, and whether it is
targeted for v1 or deferred.

### 3.1 Node tools

#### `get_node_status` (v1)

**Purpose** – Summarize current node synchronization and connectivity state
for health checks.

**Inputs**

- none

**Outputs**

```json
{
  "height": 0,
  "isSynchronizing": false,
  "syncPercent": null,
  "isMintingPossible": false,
  "numberOfConnections": 0
}
```

**Qortal endpoint**

- `GET /admin/status` (may require API key) fileciteturn0file0

#### `get_node_info` (v1)

**Purpose** – Provide static node information (version, uptime, node id,
current time).

**Inputs**

- none

**Outputs**

```json
{
  "buildVersion": "3.x.x",
  "buildTimestamp": 0,
  "uptime": 0,
  "currentTime": 0,
  "nodeId": "…"
}
```

**Qortal endpoint**

- `GET /admin/info` fileciteturn0file0

### 3.2 Account tools

#### `get_account_overview` (v1)

**Purpose** – Provide a concise summary of an account combining identity,
minting metrics, balance, and optionally owned names. fileciteturn0file0

**Inputs**

- `address` (string, required) – Qortal address

**Outputs** (example shape)

```json
{
  "address": "Q...",
  "publicKey": "…",
  "blocksMinted": 0,
  "level": 0,
  "balance": "0.00000000",
  "assetBalances": [
    {
      "assetId": 0,
      "assetName": "QORT",
      "balance": "0.00000000"
    }
  ],
  "names": ["example-name"]
}
```

**Qortal endpoints**

- `GET /addresses/{address}` – base account info
- `GET /addresses/balance/{address}` – QORT balance (or `/assets/balances`) fileciteturn0file0
- `GET /names/address/{address}` – names owned by the address

#### `get_balance` (v1, simple helper)

**Purpose** – Lightweight balance query when only a single asset balance is
needed.

**Inputs**

- `address` (string, required)
- `assetId` (integer, optional; default = 0 for QORT)

**Outputs**

```json
{
  "address": "Q...",
  "assetId": 0,
  "balance": "0.00000000"
}
```

**Qortal endpoint**

- `GET /addresses/balance/{address}?assetId={assetId}` fileciteturn0file0

#### `validate_address` (v1, utility)

**Purpose** – Check whether a string is a syntactically valid Qortal address.

**Inputs**

- `address` (string)

**Outputs**

```json
{ "isValid": true }
```

**Qortal endpoint**

- `GET /addresses/validate/{address}` (or local validation logic) fileciteturn0file0

### 3.3 Name tools

#### `get_name_info` (v1)

**Purpose** – Retrieve details about a registered name: owner, data, and sale
status. fileciteturn0file0

**Inputs**

- `name` (string, required)

**Outputs** (example shape)

```json
{
  "name": "example-name",
  "owner": "Q...",
  "data": "",
  "isForSale": false,
  "salePrice": null
}
```

**Qortal endpoint**

- `GET /names/{name}`

#### `get_names_by_address` (v1)

**Purpose** – List names currently owned by the given address.

**Inputs**

- `address` (string, required)

**Outputs**

```json
{
  "address": "Q...",
  "names": ["example-name-1", "example-name-2"]
}
```

**Qortal endpoint**

- `GET /names/address/{address}` fileciteturn0file0

### 3.4 Trade Portal tools

#### `list_trade_offers` (v1)

**Purpose** – List open cross‑chain Trade Portal offers (e.g. QORT ↔ BTC). fileciteturn0file0

**Inputs**

- `limit` (integer, optional; default e.g. 50, maximum 100)

**Outputs** (example shape)

```json
[
  {
    "tradeAddress": "Q...",
    "creator": "Q...",
    "offeringQort": "500.00000000",
    "expectedForeign": "0.01000000",
    "foreignCurrency": "BTC",
    "mode": "OFFER",
    "timestamp": 0
  }
]
```

**Qortal endpoint**

- `GET /crosschain/tradeoffers?limit={limit}`

### 3.5 QDN tools

#### `search_qdn` (v1)

**Purpose** – Search QDN / arbitrary data transactions by publisher address
and/or service code, returning metadata only. fileciteturn0file0

**Inputs**

- `address` (string, optional)
- `service` (integer, optional)
- `limit` (integer, optional; default 10, max 20)

At least one of `address` or `service` must be provided.

**Outputs** (example shape)

```json
[
  {
    "signature": "…",
    "publisher": "Q...",
    "service": 1,
    "timestamp": 0
  }
]
```

**Qortal endpoint**

- `GET /arbitrary/search?...` (with appropriate filters)

Raw data bytes from `/arbitrary/raw/{signature}` are **not** returned in v1.

### 3.6 Optional / future tools

These are candidates for later milestones and are not required for v1: fileciteturn0file0

- `get_online_accounts` – list of currently online minting accounts.
- DEX views (`get_order_book`, `get_recent_trades` for `/assets/*`).
- Block / transaction lookup (`get_block`, `get_transaction`).
- Higher‑level convenience tools wrapping `search_qdn` for specific services
  (e.g. Q‑Chat, Q‑Mail).

---

## 4. Architecture

### 4.1 Qortal integration

- The MCP server assumes a running Qortal Core node with HTTP API enabled on
  `http://localhost:12391` (configurable).
- A minimal HTTP client is implemented using `httpx`.
- Some admin endpoints (e.g. `/admin/status`) may require an API key; this is
  loaded from configuration and attached only where necessary. fileciteturn0file0

### 4.2 Internal layout

Target module layout:

```text
qortal_mcp/
  __init__.py
  config.py
  qortal_api/
    __init__.py
    client.py
  tools/
    __init__.py
    node.py
    account.py
    names.py
    trade.py
    qdn.py
  server.py
```

Responsibilities: fileciteturn0file0

- `config.py` – base URL, timeouts, limits, and API key loading.
- `qortal_api.client` – strongly‑typed wrappers for whitelisted Qortal
  endpoints; handles headers, timeouts, and mapping of Core error codes.
- `tools.*` – tool implementations that validate inputs, orchestrate calls to
  `qortal_api.client`, and normalize outputs.
- `server.py` – FastAPI app exposing each tool as an HTTP endpoint and/or
  MCP/JSON‑RPC method, depending on integration. Also provides `/health` and a
  minimal MCP gateway (see `mcp-manifest.json`).

### 4.3 Error handling

- Client helpers translate HTTP errors and Qortal `ApiError` codes into Python
  exceptions or structured error objects.
- Tool functions catch these and return standardized error JSON to callers.
- Unexpected exceptions are logged and surfaced as generic errors without
  stack traces. fileciteturn0file0

### 4.4 Rate limiting & response shaping

- Tools that can return many entries (names, trade offers, QDN search) always
  enforce `limit` and optionally support `offset`.
- Outputs are kept compact; where a Qortal response contains many fields, the
  tool selects and renames only those needed by LLMs.
- Future optimization (if needed): per‑tool caching or memoization for very
  common queries.

---

## 5. Implementation milestones

### Milestone 1 – Skeleton + two tools

**Goal** – Get a working server with minimal but end‑to‑end functionality.

Deliverables:

- Python package scaffold (`qortal_mcp`).
- `config.py` with base URL and API key loading.
- `qortal_api.client` with:
  - `fetch_node_status()`
  - `fetch_address_info(address)`
  - `fetch_address_balance(address, asset_id=0)`
  - `fetch_names_by_owner(address)`
- `tools.node.get_node_status()`.
- `tools.account.get_account_overview(address)`.
- `server.py` exposing both tools via FastAPI routes.

This milestone is the recommended first target for Codex.

### Milestone 2 – Full v1 tool set

Add remaining v1 tools:

- `get_node_info`
- `get_balance`
- `validate_address`
- `get_name_info`
- `get_names_by_address`
- `list_trade_offers`
- `search_qdn`

Also add:

- More complete tests (unit + basic integration).
- Better logging and error mapping.

### Milestone 3 – Agent / MCP integration

- Provide example configuration for:

  - Codex / IDE tooling
  - ChatGPT Agents / MCP client registries

- Optionally expose a JSON‑RPC / MCP‑native interface if needed by upstream
  tooling.

---

## 6. References

Key references in the Qortal Core repository and docs:

- Qortal API reference (`api_calls` wiki page)
- `AdminResource`, `AddressesResource`, `NamesResource`, `AssetsResource`,
  `CrossChainResource`, `ArbitraryResource`, and associated data models
  (`NodeStatus`, `AccountData`, `CrossChainTradeData`, etc.) fileciteturn0file0

These sources are the ground truth for endpoint behaviour and field names; the
tool definitions in this document are derived from them.
