# MCP Compliance Audit and Fix Plan for Qortal MCP Server

## MCP Protocol Handling (Initialize & Tool Calls)

Handshake – initialize/initialized: The server’s HTTP POST gateway must implement the MCP handshake sequence exactly. Upon receiving an initialize request, it should return a JSON-RPC 2.0 response with an InitializeResult object containing: - the negotiated protocolVersion (e.g. "2024-11-05"), - a capabilities map advertising supported features (at minimum "tools": {} since this server provides tools[1]), - and a serverInfo block with the server’s name and version[2].

For example, a correct initialize response would be:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "Qortal MCP Server", "version": "X.Y.Z" }
  }
}
```

After this, the client will send a notifications/initialized call (a JSON-RPC notification with method "initialized" and no ID) to confirm the handshake[3][4]. The server should gracefully handle this by not treating it as an unknown method. In practice, the server can implement a no-op handler that simply returns HTTP 200 with no JSON body (since notifications have no response) or a trivial success response. If the server currently lacks a handler for "notifications/initialized", this is a compliance gap to fix. Not handling it leads to handshake errors or timeouts on the client side (the Codex CLI likely waits for an acknowledgment)[5][6]. Ensure the server explicitly allows or ignores this method without error[7].

Tool Discovery – tools/list: The server must respond to tools/list requests with a JSON-RPC result containing a tools array[8]. Each entry in tools should include the tool’s name, description, and an inputSchema (plus optional outputSchema or annotations if applicable)[9]. Verify that the implementation wraps the list in a JSON object with a tools field. For example:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [ { "name": "...", "description": "...", "inputSchema": { ... } }, ... ]
  }
}
```

If the current code returns the tools list directly as an array (without the enclosing object), that is incorrect – it must be under "tools": [...] per MCP spec[8]. Cross-check the actual response structure in tests or logs against the expected format. This ensures Codex recognizes the tools.

Tool Invocation – tools/call: This is the area likely causing the “Unexpected response type” error in Codex CLI. According to MCP, a tool call response should be a JSON-RPC result containing a content array of output items[10]. Each item can be of various types (text, image, etc.), but for structured data (JSON objects), the convention is to include it as either a structured content field or as an object-type content item. The simplest fix is to wrap the tool’s return object in the content list. For example, if a tool returns an object result, the server’s response should be:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "object", "object": { ...tool result fields... } }
    ]
  }
}
```

This tells the client that the content is a JSON object. Currently, the server likely just places the tool’s output dict directly in the result, which Codex CLI doesn’t interpret as a valid content payload (hence the “unexpected response type” error). Codex expects a content array even if there is only one item[11]. We need to modify the tools/call handler to wrap outputs accordingly. For purely textual outputs, use "type": "text", "text": "...string..."; for JSON outputs, using "type": "object", "object": {…} is appropriate (the MCP spec allows structured content via a structuredContent field as well[12][13], but using a content item of type object is a straightforward approach consistent with many implementations).

Error Handling – Protocol vs. Tool Errors: The server must differentiate JSON-RPC protocol errors from business logic errors in tool execution[14]. Protocol errors (invalid JSON, unknown method, invalid params) should produce a top-level JSON-RPC error with an error object (code, message) and no result[15]. For example, an unknown method "foo/bar" should return an error with code -32601 (Method not found). Verify that server.py checks for supported methods (initialize, tools/list, tools/call, etc.) and returns a proper JSON-RPC error if the method is not recognized. Likewise, if tools/call is missing a required field (e.g. no tool name or arguments), the server should return a JSON-RPC error (e.g. code -32602 Invalid params).

Conversely, tool execution errors (e.g. invalid user input, or an underlying Qortal API failure) should not use the top-level JSON-RPC error, but instead return a successful JSON-RPC response whose result indicates the error. The MCP spec suggests including an error indicator in the result content (for instance, an isError: true flag or an error message in the content)[15]. A simple approach (used in the design) is returning a result object with an "error" field describing the problem. For example, if get_account_overview is called with an invalid address, the result could be:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": { "content": [
    { "type": "text", "text": "Error: Invalid Qortal address format." }
  ]}
}
```

(Or as an object: { "type": "object", "object": { "error": "Invalid address format." } }.)

Ensure the implementation consistently does this. Review each tool function to see how it handles error cases – they should catch exceptions or bad responses from Qortal Core and embed an error message in the result rather than letting an exception propagate. The audit should confirm that no raw stack traces or unhandled exceptions reach the client. If any tool currently raises a server exception (which might be turning into a JSON-RPC error), wrap it so that the JSON-RPC response is still result (with an error message inside). This aligns with MCP’s guidance that tool errors be reported in-band as part of the tool result[15].

HTTP 404 for /.well-known/oauth-authorization-server: The Codex CLI’s logs showing 404 on this path likely stem from the client (or underlying library) trying an OpenID Connect discovery URL. This is unrelated to MCP functionality – our server does not use OAuth. These 404s can be safely ignored; they are not an MCP protocol requirement. We should document that no OAuth2 well-known endpoints are provided (since this MCP server doesn’t require auth for read-only data). The 404s do not indicate a problem with our MCP implementation and can be left as-is (or we could consider adding a dummy response at that URL to silence the log, but it’s purely cosmetic). The key is that all essential MCP endpoints (initialize, notifications/initialized, tools/list, tools/call) are present and correct – those are the only mandatory parts for Codex integration[16][3].

## Tool Input/Output Schema Compliance

Each tool’s definition (as returned by tools/list) should include an inputSchema that accurately describes the expected parameters. The schema must be a valid JSON Schema fragment. The current implementation should be checked against the design spec in DESIGN.md to ensure consistency:

- Format of inputSchema: According to MCP, it should be a JSON object with at least "type": "object" and a "properties" map of expected inputs[9]. Confirm that every tool’s inputSchema follows this pattern. For example, for a tool that takes an address and an optional limit, inputSchema might look like:

```json
{
  "type": "object",
  "properties": {
    "address": { "type": "string", "description": "Qortal address (starts with Q...)" },
    "limit": { "type": "integer", "description": "Max results (1-20)", "minimum": 1, "maximum": 20 }
  },
  "required": ["address"]
}
```

If any tool’s schema is missing the "type": "object" or uses a non-JSON-Schema structure, that needs correction. The Codex CLI and other MCP clients use these schemas to validate inputs, so they must be precise. Check especially any complex inputs: e.g., if a tool requires an enum or a pattern (like service codes or Qortal address format), using JSON Schema keywords like "pattern" or "enum" is ideal. If inputSchema currently omits these, consider adding them for completeness (while ensuring the server still does its own validation). This will make the tools more self-documenting to the AI.

- Validation of inputs: Cross-check that for each tool, the server enforces the rules described in DESIGN.md. For instance, get_account_overview: the design says to validate the Qortal address format (should start with 'Q' and be base58 of length 34) before calling the Core[17]. Ensure the code indeed does this (likely via regex or a checksum util). If not, add this check – it prevents unnecessary Core calls and provides quicker feedback (e.g., returning {"error": "Invalid address format."}). Similarly, tools that accept a limit parameter (like perhaps a search_names or search_QDN tool) should clamp that value. In the design, for example, QDN search results were to be capped (default 100, max 20 if user specifies larger)[18][19]. Verify the implementation of such a tool: does it enforce a reasonable maximum? If the code currently passes user-provided limits directly to the Core API, that could yield huge outputs, so we should modify it to impose the designed limits. All input constraints mentioned in the design (e.g., service codes for QDN or trade search – only allow known codes 1/2/3/etc., non-negative values for certain fields, etc.) should be enforced in code. Each tool should sanitize or validate every incoming parameter.
- Output schema and content limits: The server should ensure outputs are formatted and limited per design. For example, the name lookup tool (get_account_overview which retrieves names owned by an address) might need to truncate or limit the list of names if an account has too many, though likely that’s not a big issue. More importantly, QDN search results can contain large data blobs; the design called for not returning raw binary data[20]. Confirm that the search_QDN tool (if implemented) only returns metadata (hashes, identifiers, sizes, etc.) and not the full content of files. If the Core returns a large data field, the server should strip or truncate it before constructing the result. The same goes for any Base64 or binary fields – these should either be omitted or replaced with a short summary (to avoid overwhelming the LLM with irrelevant data). Check the code for any places where it might directly relay Core responses; ensure any such fields are sanitized as per the design rules (the design mentions stripping binary fields and possibly providing a safe representation like base64 for small text files, but likely v1 just omits them)[21].
- assetBalances in get_account_overview: The design hinted at retrieving all asset balances for an account via the /assets/balances endpoint[22], but the implementation might not have fully done so. If in the current code the get_account_overview tool returns only the QORT balance and leaves other assets empty or not included, this needs clarification. Two options:
- Implement full asset listing: Use Qortal’s GET /assets/balances?address={addr} to fetch all assets for the address (with excludeZero=false to include zero balances as needed[22]). Then include an assetBalances array in the result, e.g. [ { "asset": "QORT", "balance": 123.45 }, { "asset": "TokenX", "balance": 1000 }, … ]. This would be most informative, but requires parsing that response.
- Document the limitation: If we choose not to implement full asset support in this version, we should document that assetBalances is currently omitted or always empty. For instance, update the tool’s description or README to state that only the QORT balance is returned in get_account_overview for now. In tests or output, ensure it’s either not present or an empty list to avoid confusion.

The fix plan should decide on one approach. A minimal fix is to remove or document the field to prevent misinterpretation. Given this is a read-only info tool, providing at least the QORT balance is done (via /addresses/balance/), but if assetBalances is always empty, it’s better to not include it at all in the output (or clearly comment that multi-asset support is forthcoming). Action: either implement the multi-asset retrieval or adjust the output schema to exclude assetBalances to match actual behavior.

- Cross-verify tool outputs with schemas: For each tool, ensure that the actual JSON it returns fits the schema (if an outputSchema is defined) or at least matches the implied structure. For example, if get_node_status returns boolean fields like isMinting, ensure they are proper booleans in JSON, not strings (the design mentioned converting "true"/"false" to actual booleans)[23]. If any field is renamed or formatted differently than in the Core API, update the output accordingly. The test results in test_mcp_gateway.py can be used to confirm this (they likely assert certain keys in the JSON). Any discrepancy between the design docs and implementation (like a field name or data type) should be resolved either by changing the code or updating the docs to reflect reality.

In summary, all input schemas and validation logic should adhere to the spec and design, and all tool outputs should be safe, bounded in size, and correctly structured. We will enforce any missing validations (address format, limits, etc.) and strip any disallowed or overly large data from responses.

## Test Coverage and Documentation Gaps

Test Audit (test_mcp_gateway.py): The existing test suite should cover the core MCP flows, but we need to double-check coverage and add cases if necessary:

- Handshake: There should be a test that simulates a client initialization. Ideally, the test posts an initialize JSON and expects a well-formed response containing protocolVersion, capabilities, and serverInfo. Verify if this test exists. If not, we must add one. This would catch issues like a missing field or wrong structure early. Similarly, we should test that the server can handle a follow-up notifications/initialized. Many implementations overlook this, so adding a test where the client POSTs {"jsonrpc":"2.0","method":"notifications/initialized"} and asserting that the server responds with 200 (and no error) would be valuable. If the current tests do not cover this, it’s a notable gap – we’ll create a test case to ensure the server doesn’t crash or return a method-not-found error for the initialized notification.
- Tool listing and calling: The tests likely include calling GET /tools/list or a POST request with method tools/list and checking the response. Ensure the test asserts that the response JSON has the "tools" key and that at least one known tool is listed. If the test was only checking length or status code, augment it to validate structure (i.e., each tool has name, description, inputSchema). For tools/call, the tests probably invoke a couple of tools. For example, a test might call tools/call for get_node_status (with no params) and expect certain keys in the result. The critical part to add in tests now is asserting the presence and format of the content field. If the current test is doing resp.json()["result"] and comparing to a dict, it might be missing that our new format requires an array. We should update the tests to expect result["content"] to be a list of one item for these tools. Specifically, after our fixes, result won’t directly contain the fields of the tool output; those will be nested inside result["content"][0]["object"] (for object outputs). We must reflect this in tests. Add assertions like: assert result.get("content") and result["content"][0]["type"] == "object". Also test that the actual object is correct: e.g., result["content"][0]["object"]["isMinting"] is whatever the core reported, etc.
- Error conditions: We should add tests for major error modes that an LLM agent might encounter. This includes:
- Calling tools/call with a non-existent tool name (expect a JSON-RPC error with code -32601 or a similar “Tool not found” error object).
- Calling a tool with invalid inputs: e.g., get_account_overview with an invalid address. The test should verify that the response is a success (HTTP 200 with JSON-RPC result) and that the content indicates an error (e.g., contains "error": "Invalid address format" or a similar message). This ensures our tool-level error handling is working and that we’re not mistakenly using the JSON-RPC error channel for business errors.
- If any tool can produce a runtime exception (like network failure to the Qortal node), we should simulate that (maybe by pointing the API client to a wrong port or by mocking the HTTP call to throw) and ensure the server catches it and returns a graceful error in the result. A test could monkeypatch the api_client.fetch_* method to throw an exception and then call the tool, expecting an "error" in the content.
- Codex usage patterns: The Codex CLI will typically perform the handshake then rapid tool calls. One pattern is that no tool calls should be processed before the initialize/initialized sequence is done[7][24]. In a stateless HTTP server, we might not track session state for initialization, but if we did implement session handling, we should test that calling tools/list or tools/call without a prior initialize yields an error or is queued. If we decide to enforce that, add tests accordingly (though many servers do not strictly enforce it beyond the client’s own behavior). Another pattern: test concurrent calls or multiple calls back-to-back. While Python’s FastAPI can handle concurrent requests, our tests (running synchronously) might not easily simulate that. But we can at least call multiple different tools in sequence to see if any global state carries over incorrectly (there shouldn’t be any, since each call should be independent and stateless).

Documentation Audit: Now, ensure the project documentation reflects the true behavior:

- README.md: Does it mention the MCP handshake and version? We should update the README to explicitly state that the server speaks MCP (and list the supported protocolVersion, presumably 2024-11-05 which is the current spec version in use). If README has a usage example, update it to show the correct JSON format for calling the server. For instance, if it currently shows a raw tool output, change it to demonstrate the content wrapper. Also, if any instructions about “just run the server and call the endpoints” are given, clarify that a client like Codex CLI should be used and that an initialize call is required first. In short, align the README with the reality of a JSON-RPC based MCP server (some earlier docs might have imagined one endpoint per tool or direct GET calls – if that changed, reflect it).
- DESIGN.md: This likely contains the intended design of inputs/outputs. If our implementation deviated (for example, perhaps we didn’t implement a tool that was planned, or changed a field name), note those changes. The design doc should be updated to mark which tools are included in v1 and how they function under MCP. Also incorporate any decisions like not implementing multi-asset balances (with rationale). Ensure the design doc’s examples of JSON responses match the new format with content. This is important if other developers or auditors refer to the design doc to understand the server.
- mcp-manifest.json: This file is used when publishing the server (e.g., to the MCP registry). It typically contains metadata like server name, version, description, and possibly the list of tools or a URL to fetch them. Check that the manifest’s content is accurate:
- The protocolVersion the server supports (if listed) should match what we actually use (if we’re using 2024-11-05, ensure that is stated).
- The manifest might also declare the transport (HTTP) and any authentication (for us, none required). Since clients like Claude Desktop or others might look at the manifest, it’s crucial it doesn’t advertise capabilities we don’t have. For example, if there’s a field for “resources” or “prompts” capabilities and we only implemented tools, make sure only tools are listed.
- If the manifest is incomplete (some tools servers auto-generate it), consider updating it to include all tools with their descriptions and schemas. This would mirror tools/list output in a static JSON form.
- Ensure serverInfo in the manifest (if present) matches the code (same name/version).

By updating the docs and manifest, we prevent confusion and make integration smoother. Codex CLI might not directly use our README or design, but human users will – so having correct documentation reduces integration mistakes.

Finally, verify AGENTS.md if it exists for this project. AGENTS.md usually guides AI agents on coding standards. It might require an update if any coding conventions were broken in our fixes. For instance, if it mentions not to hardcode secrets, and we add reading an API key from a file, that’s fine (just ensure we still comply). If we add tests, ensure they follow any style guidelines noted. Essentially, maintain consistency with any contributor guidelines in that file while implementing the fixes.

## Recommended Fixes (Prioritized)

Based on the audit findings above, here is a prioritized action plan to achieve full MCP compliance and Codex CLI compatibility. Each item lists the required changes, the files/functions likely involved, and references to relevant specification or design details:

- Wrap Tool Responses in content Array – (Critical)
Issue: tools/call currently returns tool outputs directly, causing Codex to report “Unexpected response type.”
Fix: Modify the tools/call handler (likely in server.py or mcp.py) to wrap the result. For every successful tool invocation, construct a response dict with content: [ { "type": "...", ... } ] instead of returning the raw object. Use "type": "object", "object": result_dict for structured results (most of our tools return JSON objects). For any purely textual tool (if any), use "type": "text", "text": "…" accordingly.
Where: In server.py, the function that processes JSON-RPC requests needs to detect method "tools/call". Inside, after obtaining the tool result (likely by calling a function from our tools modules), wrap it as described. Also adjust any unit tests expecting the old format.
Reference: MCP spec for tool call responses expects a content array[11]. This change directly addresses that requirement.
- Implement notifications/initialized Handler – (Critical)
Issue: The server may not handle the final handshake step. A JSON-RPC call with method notifications/initialized could be unrecognized, potentially leading to a JSON-RPC error and breaking the session initialization.
Fix: Add handling for "notifications/initialized" in the request dispatcher. Since it’s a notification (no id), we should not send a JSON-RPC response. If using a framework like FastAPI with a single endpoint, ensure that when method == "notifications/initialized", the server simply returns {"jsonrpc":"2.0","result":{}} or even an empty response with HTTP 204. The simplest approach: in the logic that parses incoming JSON, detect this method and short-circuit with a success acknowledgment (you might log “Session initialized” for debugging, then return an empty JSON object or appropriate response).
Where: Likely in the main request handler of server.py (or mcp.py if abstraction used). Also, add a unit test in test_mcp_gateway.py to POST a notifications/initialized and assert no error.
Reference: MCP handshake flow[3] – client sends this notification; our server must accept it without error.
- Ensure Proper JSON-RPC Envelope and Error Codes – (High Priority)
Issue: The server must strictly follow JSON-RPC 2.0 for request/response formatting. We need to verify and fix the following, if needed:
- All responses include "jsonrpc": "2.0" and an "id" matching the request (except for notifications which have none).
- Unknown method names yield a JSON-RPC error with error.code = -32601 and a message like “Method not found.”
- Invalid params (e.g., missing required fields in a request) yield error.code = -32602 (Invalid params).
- Internal exceptions (e.g., uncaught server error) yield error.code = -32603 (Internal error).
Fix: Audit the dispatcher in server.py. If it currently uses a series of if/elif on method, add an else branch that returns an error object as per JSON-RPC spec. Use a structure: {"jsonrpc":"2.0","id":req_id,"error":{"code": -32601, "message":"Method not found"}}. For param validation, since our tools do internal validation, this might be less common, but for example if a tools/call request is missing params, we can detect that and return a -32602. We might use JSON Schema validation or manual checks to implement this.
Additionally, confirm that initialize requests are handled even if they include extra fields like clientInfo (the spec expects the server to ignore or echo them). Our server should not error out if params.clientInfo is provided by the client – just ignore it or include it in response if needed.
Where: In server.py (request handling logic). Also update tests: add cases for an unknown method and check that the response contains the expected error code.
Reference: JSON-RPC 2.0 spec (error codes) and MCP guidelines[14] for distinguishing protocol errors.
- Embed Tool Business Errors in Results – (High Priority)
Issue: Tool-specific errors (invalid inputs, core API errors) should appear in the result object, not as top-level JSON-RPC errors. We need to ensure every tool function catches errors and returns a structured error message.
Fix: Go through each tool implementation (likely in src/qortal_mcp/... modules for node, account, etc.). For example:
- In get_account_overview(address): If the address fails regex validation, instead of raising an exception, return something like {"error": "Invalid address format"} (the calling tools/call handler will then wrap this in the content array as an object). Similarly, if fetch_address_info returns a 404 or an error code from Qortal (like ADDRESS_UNKNOWN), catch it and set a meaningful error in the result (e.g., "Address not found on chain").
- In get_node_status(): If the core API call fails (node offline, etc.), return an error like {"error": "Node unreachable or no response."} rather than throwing.
- For any search or list tools: if no results or any issue like invalid filter, respond gracefully (e.g., if user provided an invalid service code in a search, return {"error": "Unsupported service code."}).
Implementation-wise, this may involve wrapping external API calls in try/except and on exception, setting an error dict. We might also unify this by raising custom exceptions and catching them at a higher level – but given time, handling in each tool function is fine.
Where: Tool functions in tools/ modules and possibly the API client. Also, adjust tests: when invoking tools with bad input, expect a normal JSON-RPC result containing the error message. We can assert that result["content"][0]["object"]["error"] matches our error text.
Reference: MCP guidance on tool execution errors[15]. The design doc also recommended this pattern (returning {"error": "..."} in many places)[25][26].
- Validate and Clamp Tool Inputs – (High Priority)
Issue: Some tools may not be enforcing input rules from the design. This can lead to either crashes (if core gets bad input) or overly large responses.
Fix: Implement missing validation logic:
- For any tool taking an address (e.g., get_account_overview, maybe search_names_by_owner), ensure we validate the address format. If not already done, use a regex (^Q[1-9A-HJ-NP-Za-km-z]{33}$) or the Core’s /addresses/validate/{addr} endpoint to check validity quickly. Return an error if invalid, as noted.
- For tools with a limit or count parameter (e.g., search_QDN, get_trade_offers if exists): set a maximum (the design often said 20 or 100). If user’s requested limit > max, override it to the max (and perhaps note it in the response or just silently clamp). Also, if no limit provided and the core has a large default, perhaps set a safe default (like 100). Implement these in the tool’s logic before calling the Core.
- For tools with service codes or filters (e.g., QDN search by service, trade filters): ensure the inputSchema and code both restrict to allowed values. If an unknown value is given, return an error. For instance, if search_QDN accepts a service code, and user passes 99 (nonexistent), return error “Invalid service code.” The design suggests requiring at least one of service or address in QDN search to prevent unbounded queries[18]; implement that rule: if both are missing, refuse with an error “At least one filter (address or service) must be provided.”
- Minor: If any tool takes a string that could be extremely long (maybe none do in read-only context), you might trim it or reject overly long inputs as a safety measure (to avoid huge memory usage). Not explicitly in design, but good practice.
Where: In tool implementation functions (tools/*.py). Add conditional checks at top of each function for these conditions. The tests should be extended to cover at least one example (e.g., call get_account_overview with an obviously bad address "abc" and verify the error).
Reference: Design.md input validation sections (address validation[17], limit capping[27], etc.) to guide exact rules.
- Sanitize Tool Outputs (No Sensitive or Huge Data) – (Medium Priority)
Issue: The server should not output anything that violates security or that overwhelms the agent. This includes private data (which we are avoiding by design) and overly large blobs.
Fix: Review outputs for the following:
- Binary data or large strings: The QDN search might return an actual data hash or binary. Ensure we do not include raw file bytes. If we accidentally included a field like data or value that contains a full file, remove or truncate it. We can include a placeholder or a note to fetch via another route if needed (like instructing that the agent could use Qortal’s raw API if it really needs the content). The design explicitly said to strip binary content[21] – verify the code does so. If not, implement a filter: e.g., in the result dict, pop any key that is obviously binary (maybe Qortal marks raw bytes as base64 strings; if the field is huge or not human-readable, drop it).
- Sensitive fields: Our chosen endpoints are read-only public data, so likely no private keys or passwords appear. Just verify we’re not accidentally exposing something like an API key or internal config. E.g., if serverInfo includes a host or path, that’s fine; just nothing secret.
- Output size limits: If an account has thousands of names or transactions (not likely via our chosen tools, which are limited scope), ensure we either limit how many we return or at least caution that results are truncated. Perhaps not a big concern for v1. As a precaution, if any list in output exceeds, say, 100 entries, we might truncate and add an "truncated": true flag or similar. The design considered paging for names search but likely we won’t implement that now. Mention in docs if any built-in limits exist (for agent awareness).
Where: Possibly in the assembly of results in each tool. After getting data from Core, apply filters. For QDN search, for example, only return fields: name, service, size, timestamp, etc. – exclude actual data content. For trade or asset lists, if they exist, maybe cap the number of items returned.
Reference: Security and truncation guidelines in design[28][29].
- Update Unit Tests for New Expectations – (Medium Priority)
Issue: After making changes (#1–#6), some tests will fail if they were asserting the old response formats. We need to update and expand tests in test_mcp_gateway.py.
Fix: Adjust existing tests to the new response format with content. For example, if a test expected resp.json()["result"]["someField"], now it should expect resp.json()["result"]["content"][0]["object"]["someField"]. Specifically:
- When testing a successful tool call, assert the presence of content array and correct type.
- When testing error scenarios, assert that we still get a 200 response with a result containing an error message (instead of an HTTP error or JSON-RPC error).
- Add new tests as identified in the audit: unknown method returns JSON-RPC error, invalid tool input returns error in result, and the handshake sequence (initialize then initialized then tools/list works in order).
- Test that protocolVersion in the initialize response matches what we expect (perhaps parameterize it from server config if needed). Running the full test suite after changes is crucial; all tests should pass, and newly added ones should cover the edge cases.
Where: test_mcp_gateway.py (and any other test files related to MCP). Possibly add a new test class for handshake or integrate into existing ones.
- Documentation Updates (README, DESIGN, manifest) – (Medium Priority)
Issue: Documentation must not lag behind code; otherwise users or devs will be misled.
Fix:
- README.md: Update the usage instructions. If previously we documented REST endpoints (like /tools/node_status), update this to reflect that the server is used via JSON-RPC calls. Possibly provide a short example of an initialize request JSON and a tools/call request/response. Emphasize that the server is for use with MCP-compatible clients (like Codex CLI, Claude, etc.) and not a traditional REST API. List the available tools and their purpose briefly (or refer to DESIGN.md for details).
- DESIGN.md: Incorporate any changes made. For example, note that output is now wrapped in content arrays. If the design doc has pseudo-code or old assumptions (like separate endpoints per tool), rewrite that section to the actual design (single endpoint handling JSON-RPC messages). Ensure all tool descriptions in DESIGN.md match the implemented behavior (including error handling and any limitations). This doc is our internal blueprint, so it should be accurate for future audits.
- MCP_AUDIT.md & MCP_FIX_PLAN.md: Since these documents were used for the audit (possibly containing our findings and planned fixes), update them to mark issues as resolved once we implement the fixes. For example, in MCP_AUDIT.md, for each point (initialize compliance, tools/call format, etc.), add a note like “Fixed in commit XYZ: adjusted response format” or similar, so there’s a historical record. In MCP_FIX_PLAN.md, ensure each planned item was addressed or update the plan if we found new issues during implementation.
- mcp-manifest.json: Verify fields like name, version, and protocolVersion. If not present, add a protocolVersion. If the manifest format allows, include a pointer to our AGENTS.md or documentation. Also list the tool names provided (some manifests include a summary of tools or link to an endpoint for tools list). Since Codex CLI might fetch the manifest (some clients do to verify capabilities), having it accurate ensures smooth registration.
Where: Documentation files in repository root (or docs/ folder). No code changes, but these updates are important for clarity.
Reference: MCP manifest and docs aren’t in the spec per se, but accuracy here is for user trust and onboarding.
- Minor Code Cleanups and Compliance Checks – (Low Priority)
While not directly asked, it’s good to do a once-over for any other potential compliance or quality issues:
- Make sure the server sets appropriate HTTP headers (Content-Type: application/json) and response codes. JSON-RPC over HTTP typically uses 200 OK for valid JSON responses (even if the JSON contains an error object). If our FastAPI setup was returning 202 or other codes, consider using 200 for consistency (the StackOverflow discussion noted differences in 200 vs 202 accepted in library versions[30]).
- Confirm that CORS or other middleware isn’t interfering (if Codex CLI runs locally, it’s probably fine).
- If we generated any AGENTS.md content or followed its guidelines, ensure no credentials (like API key) are logged or exposed. The API key should be read from file as per design and not returned anywhere – double-check that.
- Logging: optionally, ensure that logging of requests/responses (if any) doesn’t log sensitive stuff. It might be useful to log tool calls and errors for debugging, but keep it moderate.
- Check package versions in requirements – not directly MCP, but for stability with Codex CLI (e.g., FastAPI or Uvicorn version might matter for SSE or streaming; our use is simple sync posts, so likely fine).

These are not major fixes but help polish the solution. After all changes, do a final integration test: run the server and connect with Codex CLI. The CLI should initialize without errors, list tools, and successfully call each tool, with no “unexpected response” messages or missing data. If anything still appears in the CLI log (like warnings or similar), address them if possible.

By completing the above fixes in order, the Qortal MCP server will adhere strictly to the MCP protocol and be fully compatible with Codex CLI (and other MCP clients). The handshake will be smooth, and tool calls will produce results in the exact format the client expects, eliminating startup errors and tool-call exceptions. All changes should be verified with the test suite and a live run with Codex CLI to ensure zero startup or tool-call errors as the end result.

[1] [2] [8] [9] [10] [11] MCP Message Types: Complete MCP JSON-RPC Reference Guide

https://portkey.ai/blog/mcp-message-types-complete-json-rpc-reference-guide/

[3] [4] [16] [24] [30] langchain - mcp server always get initialization error - Stack Overflow

https://stackoverflow.com/questions/79550897/mcp-server-always-get-initialization-error

[5] Model Context Protocol (MCP) Architecture, Workflow and Sample ...

https://medium.com/@lizhuohang.selina/model-context-protocol-mcp-architecture-workflow-and-sample-payloads-de17230f9633

[6] Missing handler for "notifications/initialized" method - Drupal

https://www.drupal.org/project/mcp/issues/3527765

[7] Model Context Protocol (MCP) | Traefik Hub Documentation

https://doc.traefik.io/traefik-hub/mcp-gateway/mcp

[12] [13] [14] [15] Tools - Model Context Protocol

https://mcp.mintlify.app/specification/2025-06-18/server/tools

[17] [18] [19] [20] [21] [22] [23] [25] [26] [27] [28] [29] Qortal MCP Server Design.docx

file://file_00000000d2cc71f5bc65de87d919be03
