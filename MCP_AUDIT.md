# Audit of Qortal MCP Server Implementation

## Alignment with Design Intent and Security Policies

The Qortal MCP server’s implementation closely follows the original design goals and security rules outlined in the planning docs. All tools and endpoints are implemented as intended, using only the whitelisted read-only Qortal Core APIs and enforcing the safety constraints:

- Whitelisted Read-Only Endpoints: The server only calls the safe GET endpoints listed in the design. These include GET /admin/status, GET /admin/info, addresses and names lookups, trade offers, and QDN search[1]. No state-changing or sensitive admin endpoints are used (e.g. no /transactions, /admin/stop, or peer management calls)[2][3]. The HTTP client layer confirms this by defining only the allowed paths (e.g. /admin/status, /addresses/{addr}, /names/{name}, /crosschain/tradeoffers, /arbitrary/search) and nothing beyond[4][5].
- Implemented Tools vs Planned: All the v1 tools described in DESIGN.md are present and correctly implemented. For example:
- get_node_status and get_node_info (node health/version) match the design’s schema, pulling from /admin/status and /admin/info respectively[6][7]. The code returns exactly the fields specified (height, sync flags, connection count, version, etc.), normalizing different core field names to a standard output[8][9].
- Account tools get_account_overview and get_balance are implemented to fetch base address info, QORT balance, and names owned[10][11]. The code calls /addresses/{address}, /addresses/balance/{address}, and /names/address/{address} as intended[12], and returns a summary with address, publicKey, blocksMinted, level, balance (QORT) and an array of names[13]. (Note: an assetBalances list is present in the output per design, but currently always empty[14] – populating other assets could be a future enhancement, though QORT balance is already included as balance.)
- Name tools get_name_info and get_names_by_address use /names/{name} and /names/address/{addr} respectively[15][16]. The implementation returns owner, data, sale status for a name[17] and the list of names owned by an address (with optional limit)[18][19].
- list_trade_offers calls /crosschain/tradeoffers?limit=N and returns open Trade Portal offers[20][21]. The code iterates through the returned list and normalizes each offer’s fields (tradeAddress, creator, offeringQort, expectedForeign, etc.)[22][23].
- search_qdn calls /arbitrary/search with address/service filters and returns only metadata (signature, publisher, service, timestamp)[24][25], exactly as designed (no raw data bytes, in line with the v1 scope).

These implementations align with the design’s Tool Catalog and use the correct core API endpoints in each case. There are no unexpected or extra tools beyond those planned for v1[26].

- Input Validation: The server rigorously validates inputs before querying Qortal, as required[27]. Qortal addresses are checked against a regex (Q[1-9A-HJ-NP-Za-km-z]{33}) for proper format[28][29]. Name strings are validated for allowed characters and length (3–40 chars, alphanumeric plus . _ -)[30][31]. Numeric parameters like assetId, limit, and service codes are validated or clamped to safe ranges. For example, get_balance ensures the assetId is a non-negative integer[32], and search queries require at least an address or service and validate the 16-bit service range[33][34]. If any input fails validation, the tool returns a clear error without calling the core (e.g. "error": "Invalid Qortal address.")[35][36]. This meets the “reject bad input early” rule[37].
- No Secrets or State Changes: By design, the server never handles private keys or passwords, and indeed no tool accepts any secret material. All inputs are public identifiers (addresses, names, IDs). The Qortal API key needed for certain admin calls is loaded internally from config but never exposed or logged[38]. The code ensures any unauthorized error from the node (like missing API key) is reported simply as "Unauthorized or API key required." without leaking the actual key or internal details[39][40]. There are also no functions that write to Qortal or perform transactions – the server omits any /transactions or admin-mutating calls in compliance with the read-only mandate[41].
- Output Sanitization and Limits: The results returned by each tool are trimmed and made LLM-friendly as specified. For example, long text fields are truncated with a suffix: the get_name_info tool limits the data field of names to a preview length (config.max_name_data_preview, default 1000 chars) and appends "… (truncated)" if needed[42][17]. List results are capped: get_names_by_address and list_trade_offers both apply a limit (default and max defined in config) and slice the results accordingly[43][44]. The config sets sane maximums (e.g. max 100 names, max 100 trade offers, max 20 QDN results)[45], and the code enforces these via a clamp_limit helper[46]. This prevents flooding the LLM or client with unbounded data, satisfying the output size limits from the design[47]. Additionally, binary content is not returned at all – the QDN search tool deliberately excludes raw data bytes (it only returns metadata and never calls /arbitrary/raw)[48], per the v1 scope.
- Error Handling: The implementation carefully catches exceptions and translates them into user-facing JSON errors, never exposing internal stack traces[49]. The qortal_api.client class maps Qortal’s error codes/messages to specific exception types (e.g. invalid address, name not found)[50][51]. The tool functions catch these and return clean error messages like {"error": "Address not found on chain."} or {"error": "Name not found."}[40][52]. Any unexpected exceptions are logged server-side and result in a generic "Unexpected error while ..." message to the client[53], ensuring no Python traceback or sensitive info leaks out. This meets the requirement to never expose raw errors and to provide clear, safe error responses[49].
- Rate Limiting and Resource Use: A basic per-tool rate limiter is implemented (token-bucket style) to prevent abuse or tight loops[54][55]. By default it allows ~5 requests per second per tool (configurable)[56][55]. If a client exceeds this, the server returns HTTP 429 with {"error": "Rate limit exceeded"}[57]. This addresses the concern of an LLM agent accidentally spamming heavy endpoints like search, as mentioned in the design[58]. The server also provides a lightweight health check and in-process metrics endpoint[59], and tracks metrics like request counts, error rates, and durations for observability[60][61]. These aren’t in the design per se, but they improve reliability and monitoring.

Overall, the current codebase adheres to the safety constraints and goals set out in the design. There are no major deviations or violations: all implemented tools are read-only and use only the allowed Qortal APIs[1], inputs are validated, outputs are constrained, and sensitive operations are excluded[41][3]. The only minor gap is that get_account_overview does not yet list secondary asset balances in the response (the design had an assetBalances field) – currently it returns an empty list for that field[14]. This means non-QORT assets are not included in the overview, but this doesn’t pose a safety risk; it’s an acknowledged v1 simplification that could be enhanced later. Documentation in the design also flagged some features (e.g. DEX asset views, online accounts) as “deferred”[62], and indeed those are not implemented yet, as expected. In summary, the implementation is well-aligned with the intended design: the server acts only as a safe, read-only bridge to provide node status, account info, name data, trade offers, and QDN search results, exactly as the project’s purpose described[63][64].

## Agent Usability for LLM Integration

The MCP server is clearly built to be used by large language model agents (OpenAI Codex, ChatGPT plugins or Tools, etc.), and in principle it should allow an AI agent to answer plain-English questions about Qortal by invoking these tools. Several aspects of the implementation make it LLM-friendly:

- Self-Describing Tool Interface: The server provides a JSON-RPC endpoint (POST /mcp) through which an agent can list available tools and call them dynamically[65]. The mcp.list_tools() function returns a list of tool definitions including each tool’s name, description, and parameters schema[66]. For example, list_tools will show entries like {"name": "get_node_status", "description": "Summarize node synchronization and connectivity state.", "params": {}} and so on for each tool[67][68]. This allows an AI agent to discover what it can do. The descriptions are concise and in plain language, suitable for an LLM to reason about which tool might answer a user’s question. The parameter listings (e.g. "address": "string (required)") also help the agent format calls correctly[68][69].
- Natural Mapping to Questions: The tools were designed to cover common blockchain queries (node status, balances, names, offers, searches)[70][71], so an agent can map user questions to these functions. For instance, if a user asks “What is the latest block height and is my node synced?”, the agent can invoke get_node_status to get the height and sync status. If asked “Who owns the name ‘AGAPE’?”, the agent uses get_name_info. The server returns structured JSON which the agent can easily read and incorporate into a natural language answer. The JSON responses are simplified for clarity (e.g. numeric values are converted to strings to avoid formatting issues, booleans are normalized, field names are intuitive)[8][22]. This aligns with the design guideline to present compact, LLM-friendly schemas[72].
- Read-Only and Safe for Agents: Because the server has no dangerous side effects, it’s suitable for autonomous agents. An LLM using these tools cannot perform any harmful action on the Qortal network – it can’t modify data or steal keys even if it tries, thanks to the enforced read-only policy. This is crucial for AI safety. The agent is essentially sandboxed to a narrow, safe API. The security checks (address validation, error handling) also mean the agent gets clear feedback if it makes a mistake (e.g. querying an invalid address yields a clean error JSON, not a confusing stacktrace[35][40]). Such predictable behavior makes it easier for the AI to learn how to use the tools correctly.
- Integration Mechanism (MCP): The server’s MCP JSON-RPC gateway is meant to plug into AI systems. In fact, the repository provides an example manifest (mcp-manifest.json) describing the server’s capabilities and endpoint[73]. This manifest advertises the server’s name, version, and the HTTP endpoint (http://localhost:8000/mcp) with protocol jsonrpc-2.0[74], along with the list of tool names it offers[75]. In a compatible AI environment (such as the Codex CLI or ChatGPT plugins that support external tools), one can register this MCP server. The expectation is that the AI client will read the tool list (either from the manifest or via the list_tools call) and then allow the LLM to invoke these tools when needed. The README explicitly mentions using this server with “an MCP-capable client (e.g., ChatGPT/Codex IDE)” and instructs pointing the client at the manifest[76]. This shows that the intended use-case is exactly an LLM agent interacting through the MCP interface.
- Tool Usability: Each tool is designed to require minimal input and produce a focused answer. For example, get_balance only needs an address (and optional asset ID) and returns just an address, assetId, and balance triple[77][78] – perfect for an agent to answer “How much QORT does address QXXXX have?”. More complex queries like “Show me open trade offers” are handled by list_trade_offers which returns a list of offers with key details (amounts, currencies, addresses) but omits any extraneous info[79][22]. By not overloading the outputs, the server makes it easier for an LLM to scan the JSON for the relevant piece of information to return to the user.

In summary, yes – the server is suitable for use by LLM agents. Once connected, an agent can ask plain-English questions about the Qortal blockchain or QDN, and behind the scenes those can be resolved by calling the appropriate tool. The design’s emphasis on simple JSON and read-only operations is evident in the code, which should allow a system like ChatGPT or Codex to reliably use these tools without confusion. The logging and metrics in the server can also assist developers in understanding how an AI agent is using the tools (e.g. to see which tools are called and if any errors occur, via the tool_success/tool_error counters and log messages)[61][80].

One caveat is that this server is very new (v0.1.0) and experimental[81] – so documentation and minor tweaks may be needed to smooth out integration. But functionally, the available toolset covers the core use cases for on-chain Qortal queries, and the server’s interface is designed with agent integration in mind.

## Analysis of Codex MCP Integration Failure

Despite the server’s design for MCP, the user’s attempt to use it via the Codex CLI failed during startup handshake, yielding the error:

```text
MCP startup failed: handshaking with MCP server failed: expect initialized result, but received: Some(EmptyResult(EmptyObject))
```

This error indicates that the MCP handshake protocol between the Codex client and the server did not complete as expected. In the Model Context Protocol (MCP), when a client connects to a server, the first step is an initialize request to negotiate version and capabilities[82][83]. The client (Codex, in this case) will send a JSON-RPC message like:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": { ... },
    "clientInfo": { "name": "...", "version": "..." }
  }
}
```

According to the MCP spec, the server must reply to this with an object confirming the protocol version and advertising its own capabilities[84][85]. For example, a proper response would be:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": { "listChanged": true }
      /* ...other categories if supported... */
    },
    "serverInfo": { "name": "Qortal MCP Server", "version": "0.1.0" },
    "instructions": "..." (optional)
  }
}
```

This “initialize result” tells the client what the server can do (here we at least include tools capability since our server exposes tools) and confirms the version. Only after receiving this does the client send an "initialized" notification to finalize the handshake[86][87], and then normal tool calls can begin.

In our case, the MCP server did not implement the initialize method at all – any JSON-RPC method other than list_tools or call_tool falls through to an “Unknown method” handler[88][89]. So when Codex sent the initialize request, the server responded with a JSON containing result: {"error": "Unknown method."} (wrapped in the JSON-RPC envelope). This is not what the client expects; the Codex MCP client likely treated it as an empty or invalid result because it didn’t contain the required fields (no protocolVersion, no capabilities). The error message “expect initialized result, but received: EmptyResult(EmptyObject)” reflects this – Codex was waiting for a non-empty result object from the initialize call, but got essentially an error/empty response instead. In other words, the handshake failed due to the server’s lack of protocol compliance.

It’s important to note this is not a bug in Codex; rather, it’s a missing piece in our server. The design docs did mark the JSON-RPC integration as “minimal” and experimental, likely targeting an older or simpler MCP usage. The README.md examples show directly calling list_tools and call_tool on the /mcp endpoint[65], implying an assumption that clients might skip formal initialization. However, the modern MCP standard (2025 spec) requires the init handshake first, and Codex (especially newer versions or the VSCode extension) have adopted that.

Therefore, the primary cause of the startup failure is the server not handling the initialize method. A related issue is protocol version negotiation: the client proposed version “2025-03-26”. Our server currently has no concept of protocol versions – it neither specifies one nor can it negotiate. Ideally, the server should simply echo back the version if it’s supported. Since we haven’t implemented any version checks, the path of least resistance is to assume we support the client’s version (e.g. 2025-03-26) and respond accordingly. Not doing so (or responding with an error) would also break the handshake. In this case, since we didn’t implement initialize at all, the version negotiation never got off the ground.

Another potential mismatch is the method naming convention for listing and calling tools. Our server expects method: "list_tools" and "call_tool" (with a tool parameter)[88], which we chose for simplicity. However, the official MCP spec uses category namespaces – likely method: "tools/list" and "tools/call" for these actions (as hinted in community examples). If the Codex client strictly followed the spec, it might be calling "tools/list" rather than "list_tools". If so, even after a successful initialize, our server would treat "tools/list" as unknown. It’s not confirmed which naming Codex CLI uses (some clients read the manifest and might call our exact names), but this is a compatibility concern. The manifest we provide lists tool names but doesn’t explicitly define the RPC method name for listing; the protocol field just says "jsonrpc-2.0"[74]. In absence of explicit instruction, a standard client might default to the standard "tools/list". So this could be a secondary cause: the server might also need to handle "tools/list" and "tools/call" as aliases. The error message from Codex doesn’t mention “tools/list” (it failed earlier at initialize), but it’s worth noting to prevent the next integration hiccup.

In summary, the MCP integration failed due to an incomplete implementation of the MCP protocol on the server side. The server did not respond to the initial handshake in the expected way (missing the initialized result object with protocol and capabilities), causing Codex to abort the connection. There is no indication of a low-level transport issue (Codex clearly reached the server, since it got a response). The EmptyResult(EmptyObject) means the JSON-RPC response lacked the fields Codex needed. This is almost certainly resolved by implementing the MCP handshake properly.

## Recommendations and Fixes for MCP Compatibility

To ensure the Qortal MCP server works seamlessly with Codex and ChatGPT (or any MCP client), we need to update the server’s MCP endpoint to fully comply with the MCP handshake and method conventions. Here are the key fixes and improvements:

- Implement the initialize Method: The server should recognize "method": "initialize" requests on the /mcp endpoint and respond with the expected JSON structure. Specifically:
- Protocol Version: Read the incoming params.protocolVersion. If it’s a version we support (e.g., "2025-03-26"), respond with the same version in the result. Since we don’t have an older/newer version to negotiate, we can accept whatever the client sent (assuming it’s a known spec date). For future-proofing, we might maintain a list of supported versions or just mirror the requested one if compatible. For now, echoing the requested version is simplest.
- Capabilities: Return a capabilities object that advertises what this server can do. At minimum, include the "tools" capability, since our server’s primary function is exposing tools. We should also indicate any sub-features. For example, we are not planning to send live updates when tools list changes (our tool set is static during runtime unless the server is updated), so we might set "tools": { "listChanged": false } (or omit listChanged to indicate no support for notifications of changes). If we eventually support the logging or resources APIs of MCP (we do have a logging mechanism, but we are not streaming logs via MCP), we could add those capabilities too (e.g., a "logging": {} entry to indicate basic logging is available). However, it’s safest to keep it minimal: advertise just the tools capability and possibly logging if we intend to use MCP’s structured logging feature. The key is that the response must include a capabilities field, otherwise the client will consider it invalid[85][90].
- Server Info: Provide a serverInfo object with a human-readable name and version for the server. We can use the name from our manifest ("qortal-mcp-server") and the version "0.1.0" which is already set in the FastAPI app metadata[91] and manifest[92]. This is mainly informational, but it’s part of the spec and lets the client log what it’s connected to.
- Instructions: Optionally, we could include an "instructions" string if we want to convey any special info to the client (some servers use this for human operator instructions in certain UIs). This is not required; it can be left out or empty.

By implementing the above, the server’s reply to initialize will go from the current “Unknown method” error to a proper result. That should satisfy the Codex CLI’s expectation of an “initialized result.” The client will then send a {"jsonrpc":"2.0","method":"notifications/initialized", ...} notification (no response needed from server). Our server can simply ignore this or log it; the spec says the server should not send any requests until it receives this notification[93], which we don’t anyway, so that’s fine.

- Ensure JSON-RPC Compliance in Responses: In our current implementation, even error messages are placed inside the "result" field (e.g. {"result": {"error": "Invalid address."}}). The JSON-RPC 2.0 spec actually dictates an "error" field at the top level for errors. This hasn’t caused functional issues for tool calls, because the consuming agent likely just checks if result.error exists. However, for the handshake it might be more strict. When implementing initialize, make sure to only return an "error" field at top-level if something is truly wrong (for example, if the client requests a protocol version we absolutely cannot speak). In the happy path, we’ll return a proper "result" as described. If we cannot handle the requested protocol (unlikely in our case), we could return an error object like {"jsonrpc":"2.0","id":1,"error": {"code": -32601, "message": "Protocol version not supported"}} or similar. But ideally, we design it such that we support the client’s version to avoid this scenario. The main point here is to follow the JSON-RPC structure on the handshake, because the Codex client clearly didn’t parse our non-standard error-in-result reply. Once the handshake is done, the simpler approach we use for tool errors (embedding the message in result) is tolerable, but aligning with JSON-RPC for all responses would be a good long-term improvement.
- Method Name Compatibility (tools/list vs list_tools): To cover all bases, update the /mcp handler to accept both our original method names and the standardized names:
- Treat "method": "tools/list" as equivalent to "list_tools", and "tools/call" as equivalent to "call_tool". This can be a simple alias mapping in the code. For example, if method == "tools/list", route it to mcp.list_tools() just like we do for "list_tools". Same for call. This will make the server robust to whichever convention the client uses. Our manifest advertised the tools by name but didn’t explicitly advertise how to list them, so a client might reasonably default to the spec "tools/list". Supporting both does no harm and ensures we won’t see another “Unknown method” error right after initialization.
- Alternatively, we could change our manifest/approach to explicitly instruct the client to use list_tools (if the MCP client even allows such custom naming – the spec is leaning toward standardized method naming, so it’s better we adapt to it rather than expect clients to adapt to us).
- Update Documentation and Manifest: Once we implement the handshake, we should update the README to mention that the server supports the MCP initialization phase. For example, note which MCP protocol versions are supported (we’ll support 2025-03-26, which is current). The manifest might also be extended to include a protocolVersion if that becomes a convention (some manifests or configurations allow specifying the version). At the very least, ensure the manifest’s endpoint is correct and consider adding any new capabilities to it if relevant. (The current mcp-manifest.json is very simple and doesn’t include capabilities, which is fine – it’s mainly to register the transport and tools list.)
- Testing the Integration: After making these changes, it’s important to test with the Codex CLI or another MCP client. We should run the Codex CLI with our updated server to verify that:
- The handshake (initialize) succeeds and the Codex client logs the server as connected.
- The tool listing is obtained (Codex might use its internal knowledge from the manifest or explicitly call tools/list, depending on the client; either way, ensure our list_tools or alias responds with the full tool list including descriptions and params).
- A sample tool call from Codex works (for example, in the Codex environment, try using the tool – maybe ask a question that triggers get_node_status – and see if the result comes through). We should also run the existing test suite; adding a unit test for the new initialize flow would be wise. For instance, simulate a POST to /mcp with an initialize payload and assert that the response contains the expected fields (protocolVersion, capabilities, etc.). This will prevent regressions.
- Other Reliability Improvements: Aside from the handshake, the core implementation is solid, but here are a few additional recommendations:
- Complete the Asset Balances Feature: As noted, get_account_overview currently returns an empty assetBalances list[14]. If the intention is to show assets besides QORT, we could fetch /assets/balances/{address} (which returns all asset balances) and include a truncated list of assets. Even if we include only QORT for now (since we already provide balance for QORT), it might avoid confusion to either populate this with at least the QORT balance or remove the field entirely in v1. Cleaning this up will make the output more consistent with the design spec and user expectations.
- Logging and Debugging: Enable a debug log mode where the server logs incoming MCP requests and their params. We have good error logging for exceptions, but during development or integration testing it helps to see “Received initialize request from client X” or the raw JSON. Given our logging is currently either JSON or simple info level[94][95], we might add a few debug statements around the MCP handshake to trace the flow. This can be turned off in production, but it’s useful when things don’t work out-of-the-box.
- Security Audit Checks: Our audit did not find any violations of the hard security rules – which is great. To maintain this, we should continue cross-referencing any new Qortal API we consider adding with the whitelist and ensure it’s read-only. Also handle any new error codes from Qortal in the mapping (the current mapping covers common ones like INVALID_ADDRESS, UNKNOWN, etc. – if Qortal adds new error strings, we may update the _map_error in client.py accordingly).
- Performance and Timeout Settings: By default, we use a 10-second timeout for Qortal API calls[96]. If many tools are used concurrently or if the Qortal node is slow, that could queue up. It’s worth considering timeouts per tool or overall request timeouts via FastAPI to ensure one slow call doesn’t hang an agent indefinitely. FastAPI/Uvicorn can have request timeouts configured, or we can rely on the client’s own handling. This is more of a nice-to-have for robustness.
- Future Capabilities: Looking ahead, if we add features like subscribing to new blocks or streaming events (out of scope for now), we’d need to advertise those in capabilities and handle them. For now, our use-case is static queries, so no action needed there.

By implementing the MCP handshake properly and making these adjustments, the Qortal MCP server will become fully compliant and reliable for use in the Codex IDE or ChatGPT environment. The critical fix is handling the initialize request and returning the right fields[85][97] – this will resolve the “expect initialized result” error and allow the client to proceed. Once that is done, and considering the thorough alignment with security/design goals, we expect the MCP server to function as intended: a safe, useful bridge for natural-language blockchain queries. The agent will be able to list the tools, invoke them with proper parameters, and get back JSON answers that it can convert into user-friendly responses. This paves the way for features like asking ChatGPT (with the Qortal plugin) questions about Qortal data and receiving up-to-date answers retrieved from the user’s own Qortal node, all with the guarantees that nothing unsafe can be done through the interface.

Sources:

- Qortal MCP Server Design document[1][24] and Agent guidelines[41][37] (project repository)
- Qortal MCP Server source code (tool implementations and client API usage)[8][40][17]
- Model Context Protocol Specification (2025-03-26) – Initialization handshake requirements[98][90]

[1] [6] [7] [10] [11] [12] [15] [16] [20] [21] [24] [25] [27] [38] [47] [48] [58] [62] [64] [77] [79] DESIGN.md

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/DESIGN.md

[2] [3] [37] [41] [49] [54] [63] [70] [71] [72] AGENTS.md

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/AGENTS.md

[4] [5] [50] [51] client.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/qortal_api/client.py

[8] [9] [39] [53] node.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/node.py

[13] [14] [32] [35] [40] [78] account.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/account.py

[17] [18] [19] [36] [42] [43] [52] names.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/names.py

[22] [23] [44] trade.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/trade.py

[26] [65] [76] [81] README.md

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/README.md

[28] [29] [30] [31] [46] validators.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/validators.py

[33] [34] qdn.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/tools/qdn.py

[45] [56] [96] config.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/config.py

[55] [57] [59] [60] [61] [88] [89] [91] [94] [95] server.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/server.py

[66] [67] [68] [69] mcp.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/mcp.py

[73] [74] [75] [92] mcp-manifest.json

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/mcp-manifest.json

[80] metrics.py

https://github.com/QuickMythril/qortal-mcp-server/blob/a134bc8a217676dbd9da9114de0ec06ceb4faf43/qortal_mcp/metrics.py

[82] [83] [84] [85] [86] [87] [90] [93] [97] [98] Lifecycle - Model Context Protocol

https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle
