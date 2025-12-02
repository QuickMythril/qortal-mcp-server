# Qortal MCP Server – AGENTS.md

This file is for **AI coding agents** (Codex, ChatGPT, etc.) working in this
repository. Follow these rules strictly.

---

## 1. Project purpose

- Implement a **read‑only** Python server that exposes a safe subset of the
  Qortal Core HTTP API (port `12391`) as LLM‑friendly tools.
- The server must **never** sign transactions, broadcast transactions, or call
  any state‑changing / admin endpoints beyond whitelisted read‑only calls.
- Primary use cases:
  - Node health / status checks
  - Account / balance / name lookups
  - Trade Portal (cross‑chain) offer listings
  - QDN / arbitrary transaction search (metadata only)

For design details, always consult **`DESIGN.md`** before making changes.

---

## 2. Hard security rules (MUST NOT break)

1. **Read‑only only**
   - Do **NOT** call any endpoint that creates, signs, or broadcasts
     transactions (e.g. anything under `/transactions`, name registration,
     asset issuance, order creation/cancellation, etc.).
   - Do **NOT** call `/admin/stop`, `/admin/orphan`, `/admin/forcesync`,
     `/peers/*`, or any other endpoint that mutates node state or reveals
     low‑level network details.

2. **No secrets in or out**
   - Never accept private keys, seeds, mnemonics, wallet passwords, or backup
     data as tool inputs.
   - Never log or return the Qortal Core API key or any credential material.
   - If a caller passes obviously secret data, **reject the request** and
     return a clear error message.

3. **Endpoint whitelist only**
   - Only call Qortal endpoints that are explicitly allowed in `DESIGN.md`
     (read‑only GET endpoints under `/admin`, `/addresses`, `/names`,
     `/crosschain/tradeoffers`, `/arbitrary/search`, and a limited subset of
     `/assets`).
   - Do not generate code that builds arbitrary URLs based on user input. All
     HTTP paths must come from constants or safe templates in the client
     library.

4. **Input validation**
   - Validate all external inputs before hitting the Qortal API:
     - **Addresses**: Qortal address format (Q‑prefixed Base58, correct length).
     - **Names**: allowed characters and length per Qortal name rules.
     - **Service codes / IDs**: integers within reasonable ranges.
     - **limit / offset**: clamp to safe maximums (e.g. `limit <= 100`).
   - If validation fails, do **not** call Qortal Core; return a structured error.

5. **Output size limits**
   - Do not return unbounded amounts of data.
   - Enforce sane caps:
     - Max list lengths (e.g. 100 items) even if Core returns more.
     - Truncate large strings with a suffix like `"... (truncated)"`.
   - Do **not** stream or embed large binary payloads (QDN raw data, files,
     images). For now, focus on metadata and small text; raw/binary QDN content
     is out of scope for v1.

6. **Error handling**
   - Never expose Python stack traces or internal exceptions to the caller.
   - Catch and map Qortal errors (e.g. `INVALID_ADDRESS`, `ADDRESS_UNKNOWN`)
     to clear JSON error objects like:
     `{"error": "Invalid Qortal address."}` or
     `{"error": "Address not found on chain."}`.
   - When the node is unreachable or times out, return a concise error
     message (e.g. `"Node unreachable"`).

7. **Rate limiting**
   - Assume this server may sit in front of a mainnet node.
   - Avoid tight loops or aggressive polling of heavy endpoints, especially
     QDN search and trading tools.
   - If you add logic that could trigger many calls, include throttling or
     caching and document it in `DESIGN.md`.

---

## 3. Tech stack & style guidelines

- Language: **Python 3.11+**
- HTTP server: **FastAPI** (ASGI) + **Uvicorn** (or similar)
- HTTP client: **httpx**
- Optional validation: **Pydantic** models for tool inputs/outputs.

Coding style:

- Follow PEP 8 and use type hints for all public functions.
- Keep functions small and focused.
- Prefer explicit, readable code over clever one‑liners.
- Include docstrings for all public functions, especially tool handlers and
  client methods.

Project structure (target):

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

Responsibilities:

- `config.py` – base URL, API key location, timeouts, limits, environment
  selection (mainnet/testnet/regtest).
- `qortal_api.client` – thin, well‑typed wrappers around whitelisted Qortal
  endpoints, plus shared error handling.
- `tools.*` – LLM‑facing tool implementations that validate inputs, call
  client helpers, and shape outputs.
- `server.py` – FastAPI app that exposes tools to the outside world (and
  later, MCP integration / JSON‑RPC glue if needed).

---

## 4. Tool design guidelines

When adding or modifying tools:

1. **Check DESIGN.md first**
   - Only implement tools that are defined there, or propose updates to the
     design doc before adding new ones.

2. **Simple, LLM‑friendly schemas**
   - Keep inputs small and explicit – avoid generic “options” blobs.
   - Return compact JSON objects, not raw Qortal responses; rename fields when
     it improves clarity (document the mapping in comments).

3. **No hidden side effects**
   - Tools must not change node state or write to disk in unexpected ways.
   - If you add any caching or local storage, document it in DESIGN.md and keep
   it strictly read‑only from Qortal’s perspective.

4. **Pagination and limits**
   - For tools that may return lists (names, offers, QDN search results),
     always support `limit` and optionally `offset`.
   - Enforce upper bounds in code even if the caller asks for more.

5. **Testing**
   - Add unit tests for new tools where reasonable, especially for validation
     and error mapping.
   - When tests rely on Qortal Core, use testnet/regtest and/or mock HTTP
     responses where possible.

---

## 5. When in doubt

If there is any conflict between convenience and safety, **choose safety**.

- Prefer to reject a request with a clear error rather than risk exposing too
  much data or hitting a dangerous endpoint.
- If you are unsure whether an endpoint is safe or how to normalize its
  output, update `DESIGN.md` with the open question instead of guessing.

This project’s priority order is:

1. **Safety & correctness**
2. **Clarity for LLMs**
3. Performance and convenience
