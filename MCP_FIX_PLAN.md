# MCP Fix & Enhancement Plan for Qortal MCP Server

This document is for **AI coding agents (Codex, etc.)** working on the
`qortal-mcp-server` project.

The goal is to:
1. Fix the **MCP handshake** so MCP clients (especially Codex) can connect
   cleanly.
2. Ensure **method naming compatibility** with the current MCP spec.
3. Make minor **usability and completeness improvements** (asset balances,
   logging, docs) without weakening any security guarantees.

Read and follow **AGENTS.md** and **DESIGN.md** before making changes. Do **not**
relax any security rules.

---

## 1. Context & Current Issues

The server already implements the v1 tool set described in `DESIGN.md` and uses
only whitelisted, read-only Qortal endpoints. That part is in good shape.

However, there are several integration issues that prevent Codex (and other
MCP clients) from using the server as intended:

1. **MCP initialize handshake is not implemented**  
   - MCP clients (e.g. Codex) send an `initialize` JSON-RPC request as the
     first call to the server.  
   - Our `/mcp` endpoint does **not** handle `method: "initialize"` and
     effectively returns an “unknown method”/empty result.  
   - Codex expects an `InitializeResult` object with `protocolVersion`,
     `capabilities`, and `serverInfo`, but instead receives an empty/invalid
     result, causing startup failure.

2. **Method naming may not match the MCP spec**  
   - The server currently expects method names like `list_tools` and
     `call_tool`.  
   - The MCP spec and some clients use namespaced methods such as
     `tools/list` and `tools/call`.  
   - If a client calls `tools/list`, we currently return “unknown method”.

3. **JSON-RPC error semantics are loose**  
   - For most tool calls we embed errors inside `result` (e.g.
     `{ "result": { "error": "..." } }`) rather than using the top-level
     `"error"` object as JSON-RPC 2.0 recommends.  
   - For the handshake this can confuse clients which expect a proper
     `result` object or an explicit JSON-RPC error.

4. **Small completeness/usability gaps**  
   - `get_account_overview` currently returns a field `assetBalances` but
     typically leaves it empty. The design suggests including asset balances
     (where reasonable).  
   - Logging around MCP handshake is minimal, which makes debugging client
     issues harder.  
   - README/DESIGN do not explicitly describe MCP handshake support.

The tasks below are ordered by priority. **Tasks 1 and 2 are blocking** for
Codex/agent usage and must be completed first.

---

## 2. Non‑negotiable Constraints

When performing changes:

- **Do not** introduce any write or state-changing Qortal calls. The server
  must remain **strictly read‑only**.  
- **Do not** accept or log any secrets (private keys, seeds, passwords, API
  key contents).  
- Maintain or tighten all validation and output limits defined in `DESIGN.md`
  and `AGENTS.md`.  
- All public changes should be covered by tests where practical (especially
  protocol and validation logic).

If any change appears to conflict with `AGENTS.md` or `DESIGN.md`, update the
design **first** and keep the change minimal and well-documented.

---

## 3. Task 1 – Implement MCP `initialize` Handshake (High Priority)

### Goal

Implement full support for the MCP `initialize` request/response on the `/mcp`
JSON‑RPC endpoint, in line with the current MCP spec.

### Requirements

1. **Recognize the `initialize` method**

   - On the `/mcp` endpoint, detect JSON‑RPC requests where
     `method == "initialize"`.

2. **Parse `params`**

   - Expect a `params` object with at least:
     - `protocolVersion` (string, e.g. `"2025-03-26"`)
     - `capabilities` (object – can be ignored or checked)
     - `clientInfo` (object with `name`, `version`)

   - We do **not** need to negotiate multiple versions yet; it is acceptable
     to accept any known version string and echo it back.

3. **Return a valid `InitializeResult`**

   For a successful `initialize` request, reply with a JSON‑RPC response of
   the form:

   ```json
   {
     "jsonrpc": "2.0",
     "id": <same as request>,
     "result": {
       "protocolVersion": "2025-03-26",
       "serverInfo": {
         "name": "qortal-mcp-server",
         "version": "0.1.0"
       },
       "capabilities": {
         "tools": {
           "listChanged": false
         }
       }
     }
   }
   ```

   Notes:

   - `protocolVersion` in the result SHOULD match the client’s requested
     `params.protocolVersion` if we support it. For now, assume we support
     the version the client sends and echo it.  
   - `serverInfo.name` and `serverInfo.version` must be consistent with our
     manifest and application metadata.  
   - The `capabilities` object must at minimum include `"tools"` since this
     server exposes tools. Use `{ "tools": { "listChanged": false } }`
     unless we add more MCP features (e.g. logging or resources).

4. **Error handling for initialize**

   - Only if we truly cannot support a requested protocol version (e.g. the
     string is completely unknown and incompatible) should we return a
     **JSON‑RPC error** response with a top‑level `"error"` field, e.g.:

     ```json
     {
       "jsonrpc": "2.0",
       "id": <same as request>,
       "error": {
         "code": -32601,
         "message": "Protocol version not supported"
       }
     }
     ```

   - In practice, we should avoid rejecting initialize unless necessary.
     Start by simply echoing the version for known MCP spec strings.

5. **No requests before initialize**

   - The server must not send any outbound MCP requests. It should only
     respond to client requests. Our current design already follows this, so
     no change is needed here.

6. **Tests**

   Add tests to cover initialize, for example:

   - A unit/integration test that sends an `initialize` JSON‑RPC request to
     `/mcp` and asserts that:
     - The response has `"result"` with `protocolVersion`, `serverInfo`,
       and `capabilities.tools`.  
     - `serverInfo.name` and `.version` match what is documented.  
     - No unexpected fields are present.

   - A negative test may be added if we choose to reject clearly invalid
     protocol versions.

7. **Manual verification instructions**

   Document (in README or comments) a `curl` example to debug initialize,
   e.g.:

   ```bash
   curl -sS -X POST http://127.0.0.1:8000/mcp      -H "Content-Type: application/json"      -d '{
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

   The output should contain a valid `result` as described above.

---

## 4. Task 2 – Support Standard MCP Method Names (High Priority)

### Goal

Ensure compatibility with MCP clients that use standard namespaced methods
for tools, such as `tools/list` and `tools/call`, in addition to our current
`list_tools` / `call_tool` names.

### Requirements

1. **Alias standard method names**

   - In the `/mcp` dispatcher, treat the following as equivalent:

     - `method == "tools/list"` → existing `list_tools` implementation.  
     - `method == "tools/call"` → existing `call_tool` implementation.

   - Keep backward‑compatible support for `list_tools` and `call_tool`
     unless we have a compelling reason to remove them.

2. **Parameter mapping for `tools/call`**

   - If a client uses `tools/call`, it will likely send params in the form:

     ```json
     {
       "name": "get_node_status",
       "arguments": { ... }
     }
     ```

   - Confirm the expected shape from MCP examples if available. If necessary,
     support both our current param structure and the standard one.  
   - Adjust the handler so it can read the tool name and arguments from the
     incoming `params`, and then route to the correct tool function.

3. **Unknown methods**

   - For any unrecognized method (excluding `initialize`, `tools/list`,
     `tools/call`, `list_tools`, `call_tool`), return a **proper JSON‑RPC
     error**:

     ```json
     {
       "jsonrpc": "2.0",
       "id": <same as request>,
       "error": {
         "code": -32601,
         "message": "Method not found"
       }
     }
     ```

   - Do not return a vague `{ "result": { "error": "Unknown method" } }`
     for protocol‑level errors.

4. **Tests**

   - Add tests that call `/mcp` with `method: "tools/list"` and verify the
     tool list is returned.  
   - Add tests that call `/mcp` with `method: "tools/call"` and a valid tool
     name, verifying that the correct underlying tool function is invoked.

---

## 5. Task 3 – JSON‑RPC Error Handling Improvements (Medium Priority)

### Goal

Align error handling more closely with JSON‑RPC 2.0, especially for protocol‑
level errors, while preserving the current LLM‑friendly error messages for
tool results.

### Requirements

1. **Protocol‑level errors**

   - For errors such as:
     - Unknown method (non‑tools / non‑initialize)
     - Malformed JSON‑RPC request (missing required fields)
     - Unsupported protocol version (if we choose to enforce this)

     Use **top‑level JSON‑RPC `"error"`** objects.

2. **Tool‑level errors**

   - For business logic or Qortal errors inside tools (invalid address,
     name not found, node unreachable, etc.) we may keep the current pattern
     of returning a `result` object with an `"error"` field, e.g.:

     ```json
     {
       "jsonrpc": "2.0",
       "id": 42,
       "result": {
         "error": "Invalid Qortal address."
       }
     }
     ```

   - This is acceptable for now because LLM clients can easily check for a
     result.error string.  
   - Document this behavior clearly, so downstream clients know to check both
     JSON‑RPC `"error"` and `result.error`.

3. **Consistency and documentation**

   - Ensure similar tool failures are mapped to the same error strings and
     structures (e.g. `"Address not found on chain."`, `"Name not found."`).
   - Update any comments in the MCP handler to reflect the JSON‑RPC behavior
     so future changes remain consistent.

4. **Tests**

   - Add tests for protocol‑level errors (unknown method, malformed request)
     verifying the presence of a top‑level `"error"` field.  
   - Maintain or extend existing tests for tool‑level error responses.

---

## 6. Task 4 – Optional: Asset Balances in `get_account_overview`

### Goal

Make `get_account_overview`’s `assetBalances` field more useful and consistent
with the design, without significantly increasing complexity or response size.

### Requirements

1. **Decide behavior (one of):**

   **Option A – minimal but consistent (recommended for now)**

   - Keep `assetBalances` but explicitly document in DESIGN.md that v1 only
     populates QORT’s balance in the top‑level `balance` field and leaves
     `assetBalances` empty.  
   - Make sure the schema in DESIGN.md and the code comments agree.

   **Option B – include a small set of asset balances**

   - Call a read‑only Qortal endpoint that returns asset balances for a given
     address (e.g. `/assets/balances?address=...`).  
   - Map that data to a list of objects like:

     ```json
     {
       "assetId": 0,
       "assetName": "QORT",
       "balance": "123.00000000"
     }
     ```

   - Enforce limits:
     - Maximum number of assets returned (e.g. 20).  
     - Optional filter to include only non‑zero balances.  
   - This must **not** introduce any new write/state‑changing API calls.

2. **Update docs**

   - If you change the behavior of `assetBalances`, update DESIGN.md to
     describe the exact semantics (what assets are included, limits, etc.).

3. **Testing**

   - Add tests that verify the `assetBalances` behavior (either confirming
     it is empty by design, or that it accurately reflects mocked asset
     balances).

If implementation time is limited, **Option A** is acceptable for v1 provided
it is clearly documented. The main goal is to avoid confusing or misleading
output.

---

## 7. Task 5 – MCP‑Focused Logging & Debuggability (Medium Priority)

### Goal

Make it easier to debug MCP integration issues without leaking sensitive
information.

### Requirements

1. **Log MCP requests at debug level (safe subset only)**

   - For each MCP request, log:
     - `method` name  
     - Tool name (for `tools/call` / `call_tool`)  
     - Request ID  
     - High-level status (success/error) and timing

   - Do **not** log full arguments if they may contain large blobs or
     potential PII; addresses and names are safe, but avoid logging raw QDN
     content or large JSON payloads.

2. **Log initialize flow**

   - Add debug logs for:
     - Receiving `initialize` request (including requested protocol version).  
     - Returning `InitializeResult` (at least log `protocolVersion` and
       `serverInfo.name`).

3. **Keep logs free of secrets**

   - Ensure that API keys, environment variables, and any other secrets are
     never logged.  
   - Double‑check that logging configuration doesn’t accidentally include
     headers or internal config details.

4. **Config toggles**

   - Use existing logging configuration and/or environment variables to
     control log verbosity. Default to safe, minimal logging in production,
     but allow more verbose logging during development.

---

## 8. Task 6 – Documentation & Manifest Updates (Medium Priority)

### Goal

Ensure project documentation matches the actual behavior and that MCP clients
have clear guidance on how to connect.

### Requirements

1. **README.md updates**

   - Add a short section “MCP Integration” describing:
     - That the server supports MCP `initialize`.  
     - Which MCP protocol version(s) are supported (e.g. `"2025-03-26"`).  
     - How to configure Codex or other clients to point at the `/mcp`
       endpoint and manifest.

   - Include the `curl` example for debugging `initialize` from Task 1.

2. **DESIGN.md updates**

   - Briefly mention MCP handshake behavior and the fact that we support
     `initialize`, `tools/list`, and `tools/call`.  
   - If `assetBalances` behavior is changed, update that section accordingly.

3. **Manifest updates (`mcp-manifest.json` or equivalent)**

   - Confirm that:
     - The `endpoint` URL is correct (e.g. `http://localhost:8000/mcp`).  
     - The `name` and `version` fields match `serverInfo`.  
     - The tools list is accurate (names, descriptions).

   - If MCP tooling expects a `protocolVersion` or additional metadata in the
     manifest, add it in a way that remains consistent with the implementation.

4. **Keep docs consistent**

   - Ensure AGENTS.md, README, and DESIGN.md tell a coherent story about:
     - Security guarantees (read‑only, whitelisted endpoints).  
     - Available tools and their intended usage.  
     - MCP protocol behavior.

---

## 9. How to Approach This as a Coding Agent

1. **Read the existing docs and code**

   - `AGENTS.md` – security and general coding rules.  
   - `DESIGN.md` – tool catalog and architecture.  
   - MCP server/gateway implementation (the `/mcp` handler).  
   - HTTP client and tools modules.

2. **Implement tasks in order of priority**

   - Complete Task 1 and Task 2 **first** and verify Codex (or another MCP
     client) can successfully connect and list tools without handshake errors.  
   - Then work through Tasks 3–6 as time allows, keeping changes small and
     well‑tested.

3. **Run and extend tests**

   - Ensure the existing test suite passes.  
   - Add new tests for:
     - `initialize` handshake.  
     - `tools/list` and `tools/call` aliases.  
     - JSON‑RPC protocol errors.  
     - Any changed behavior (e.g. asset balances).

4. **Manual verification**

   - Use `curl` or a small Python script to exercise `initialize`, `tools/list`,
     and `tools/call` directly against `/mcp`.  
   - Once those work, test with Codex CLI or another MCP client (as available)
     and confirm that tools can be invoked to fetch real Qortal data.

5. **Keep everything read‑only and safe**

   - If in doubt, err on the side of rejecting a request or limiting output
     rather than risking a security or privacy issue.
