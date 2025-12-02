# Qortal MCP Tools/Call Response Audit and Fix Plan

## Spec Requirements vs. Current Implementation

According to the MCP specification v2025-03-26, tool call results should be returned in a content array with known content types (e.g. "text", "image", "audio", or resource types). Structured JSON output was not explicitly supported in the 2025-03-26 spec except as unstructured text[1]. A typical tools/call response example from the spec shows a single text content item and an isError flag, with no arbitrary "object" type[2]. Key points to note:

- Content Array Structure: The result of a tools/call must include a content list, where each item has a type and the corresponding data field for that type. Valid types in 2025-03-26 included "text", "image", "audio", "resource" (embedded resource), and "resource_link"[3][4]. There is no mention of a "type": "object" in the official content types for that version.
- Structured Output in Newer Spec: The concept of returning structured JSON natively was introduced in MCP v2025-06-18 via a separate structuredContent field[1]. In that update, servers can include a top-level structuredContent (usually a JSON object or array) alongside a human-readable text summary in the content array[5][6]. Clients supporting 2025-06-18 will look at structuredContent for programmatic data. In v2025-03-26, however, any structured data would have to be encoded as text (e.g. JSON string within a text content item).
- Lists of Objects: If a tool returns a list of items (e.g. an array of trade offers), the 2025-03-26 spec does not define a special "list" content type. The correct approach in that spec would be to either combine the list into a single text output (for the LLM to interpret), or return multiple content items (e.g. multiple text entries) describing each item. The spec leans toward a single content payload unless multiple different types are needed[7]. In the new structured output approach (2025-06-18), a list of objects would simply be placed as an array in structuredContent, with an optional text summary. There is no valid scenario where a content item of type: "object" wraps a raw JSON list – that format is not recognized by the protocol.
- “object” Type in Content: Using {"type": "object", "object": {...}} as a content item is not supported in MCP v2025-03-26. The spec expected only the defined content types. This means the server’s current habit of wrapping JSON data in an "object" content type is non-compliant. A client following the spec (e.g. Codex CLI) will encounter an unknown content type "object" and likely raise an error (hence the “Unexpected response type” message).
- Codex CLI Expectations: The Codex CLI (an MCP client) likely expects either a plain text response for these tools (if it’s assuming 2025-03-26 behavior), or a proper structuredContent field (if it was built with awareness of 2025-06-18). What it does not expect is a content item of an unrecognized type. Given that we see an error, it’s safe to conclude that Codex CLI doesn’t accept type:"object" in the content array. It may have been looking for a structuredContent field instead, or simply for a "text" content. In summary, under MCP 2025-03-26 the server should return structured data as text, and under 2025-06-18 it should use structuredContent (with a text fallback in content). The current implementation does neither correctly.

Conclusion: Per the spec, structured JSON must not be placed directly in the content array as type "object". Instead, for protocol 2025-03-26, structured data should be serialized to a text string (or otherwise made into a supported content type). The newer protocol version 2025-06-18 allows a separate structuredContent field (which the Codex CLI may be expecting if it’s up-to-date). In any case, the server’s current output format deviates from spec, which is the root cause of the “Unexpected response type” error.

## Mismatches Identified in qortal-mcp-server (Commit 353df38)

Reviewing the server code reveals several points where the implementation diverges from MCP 2025-03-26 requirements:

- Use of type: "object" in Content: The _wrap_tool_result function wraps all non-string results in a content item with type: "object"[8]. For example, a call to validate_address("bad") returns {"isValid": False}, which the wrapper transforms into:

```text
"result": {
  "content": [ { "type": "object", "object": {"isValid": False} } ]
}
```

- Tests confirm this behavior[9]. Similarly, get_node_status returning a dict, or list_trade_offers returning a list, get wrapped in the same way. This is not an MCP-defined content format, causing the client to throw an “Unexpected response type: object” error. Only "text", "image", "audio", "resource", etc., are expected in content[3][4] – the server’s custom "object" type is invalid.
- Lists Wrapped as a Single Object: In the case of list_trade_offers, the function returns a list of offer dicts[10][11]. The wrapper then produces "object": [ {...}, {...}, ... ] under one content item. This means the entire array is being sent as if it were one “object” content element[8]. There is no notion of an array content element in MCP 2025-03-26; a list should either be broken out or turned into text. The server essentially treats the list as an opaque JSON, which the client doesn’t know how to handle (since it’s labeled as type object). This triggers the Codex CLI error specifically for list-returning tools like list_trade_offers. The first erroneous content item shape would be:

```json
{ "type": "object", "object": [ {offer1...}, {offer2...} ] }
```

- which is clearly not compliant.
- Missing structuredContent Field: The server does not use the structuredContent field at all in responses. In MCP 2025-03-26, this field didn’t exist, but in 2025-06-18 it’s the proper place for JSON outputs[5]. The Codex CLI might expect structuredContent if the client and server negotiate a newer protocol version or if output schemas are provided. By providing only a content array with an unknown type, the server fails to meet either older or newer spec expectations.
- Tool Execution Errors Not Marked: When a tool returns an error (e.g., {"error": "Node unreachable"}), the current code still wraps it as type:"object" content (since it’s a dict) and does not set the isError flag[8]. According to the spec, tool execution errors should be indicated by "isError": true in the result, and typically the content would contain a human-readable error message[12]. The server’s behavior means clients might not recognize that the result is an error. For example, a failed get_balance on an invalid address now returns:

```text
"result": { "content": [ { "type": "object", "object": {"error": "Invalid Qortal address."} } ] }
```

- with no isError:true. This is a spec mismatch. The client might simply treat the content as a successful call with some object, rather than an error, or (in Codex CLI’s case) might not handle it at all due to the unknown type.
- Primitive Results Handling: While most tools return dicts or lists, any tool returning a bare primitive (e.g. a number, boolean, or None) would also hit the else branch of _wrap_tool_result and be wrapped as {"type":"object","object": 123} (or true, or null)[8]. This is equally problematic. There is no spec support for a content item of type object holding a raw number or boolean. It’s unlikely in this codebase to have such a tool (most wrap output in dicts), but this is a potential bug if a future tool returns a simple value. It should ideally be returned as a string (type text) or handled via structuredContent if adopted.
- requestId Field in Responses: The server includes a custom "requestId" field in JSON-RPC responses when available[13]. For example, _jsonrpc_success_payload and _jsonrpc_error_payload attach requestId (a UUID) if present. This field is not part of the official MCP 2025-03-26 response schema – the spec examples do not show a requestId in successful responses (only the "id" from JSON-RPC)[14][15]. In some contexts (streaming or cancellation notifications) requestId is used to correlate messages, but a standard tools/call result should not need it. Including this extra field is benign for many clients (they might ignore unknown fields), but it’s technically an unsupported extension. We should verify that Codex CLI isn’t confused by it. Most likely, the CLI ignores it, and the real issue is the content formatting – but for completeness, we note this discrepancy.
- capabilities.tools.listChanged Setting: The server responds to initialize with "listChanged": false in the tools capabilities[16]. The spec allows this flag to indicate whether notifications/tools/list_changed will be sent when tools change[17]. Using false here is acceptable (meaning “this server will NOT send tool-list change events”). There is no requirement to omit the flag; false is a valid boolean value. In short, this is not a protocol violation. (Some implementations might leave out the flag if no notifications are supported, but the spec doesn’t forbid false. In our case, keeping it is fine and explicit.)

Summary: The primary cause of the Codex CLI error is the server’s use of an unsupported content wrapper (type: "object") for structured results, especially when wrapping an entire list. Additionally, the server doesn’t leverage structuredContent (which the client might prefer for JSON data) and doesn’t mark errors with isError as expected. The requestId inclusion is optional (likely not the breaking issue), and listChanged: false is correctly used (no change needed there). These mismatches need to be corrected to align with MCP protocol expectations and to have Codex CLI accept the responses.

## Correct Content Wrapping (Spec-Compliant Strategies)

To fix the response format, we should adjust how tool outputs are packaged in the JSON-RPC result. Different return types require different handling:

- Single Object Result (Map/Dictionary): For tools like get_node_status or get_account_overview that produce a JSON object, the result should not be stuffed verbatim into the content array. Instead, the server has two options:
- As Text (for 2025-03-26 compliance): Serialize the object to a JSON string and return it in a content item of type "text". For example:

```text
"content": [
  {
    "type": "text",
    "text": "{\"height\":123,\"isSynchronizing\":false,...}"
  }
]
```

- This way, the structured data is conveyed as plain text (which the LLM can read or parse if needed). This approach stays within the older spec’s bounds (since everything is text)[1].
- As Structured + Text (forward-compatible): Return a text block and use the structuredContent field to include the raw object. According to the 2025-06-18 spec, when a tool has structured output, the response can include:

```text
"content": [ { "type": "text", "text": "<serialized JSON or summary>" } ],
"structuredContent": { ...object... }
```

- This is the ideal format for structured results[6]. For instance, get_node_status could return:

```text
"content": [ { "type": "text", "text": "{\"height\":123,\"isSynchronizing\":false,...}" } ],
"structuredContent": { "height": 123, "isSynchronizing": false, ... }
```

- In practice, including structuredContent even when the protocolVersion is 2025-03-26 should be harmless – older clients will ignore the unknown field, and newer clients (like Codex CLI if updated) will utilize it. The key is that the content array now contains a valid type (text) instead of an invalid object. Yes, type: "object" as a content entry should be completely eliminated.

Which approach to choose? Ideally, implement the structuredContent with text fallback. This covers both bases: it maintains backward compatibility (text for any client or LLM that only reads content) and provides structured data for those who can use it. It effectively brings the server in line with the newer MCP spec without breaking the declared 2025-03-26 compatibility. If, for some reason, we want to stick strictly to 2025-03-26 behavior, then simply returning text content (option 1) is the way – but given that Codex CLI likely expects structured output by name, option 2 is strongly recommended.

- List of Items Result: For tools like list_trade_offers (returns a list of similar objects) or search_qdn (list of search results), the same principle applies. We should not wrap the array in a fake object content. Instead:
- Provide a textual representation of the list. This could be a JSON array string (e.g. "[{\"tradeAddress\": \"Q...\", ...}, {...}]"). Since JSON arrays can be long, ensure it’s properly truncated or limited as per config (the tool already does limiting). This text will allow the LLM to see the contents. Alternatively, a bullet-point list or summary in text could be returned, but the most straightforward is a JSON string for accuracy.
- Include the actual list under structuredContent as a JSON array. For example:

```text
"content": [ { "type": "text", "text": "[{\"tradeAddress\":\"Q...\",\"creator\":\"...\"}, {...}]" } ],
"structuredContent": [
   { "tradeAddress": "Q...", "creator": "...", ... },
   { ... next offer ... }
]
```

- If the list is empty, structuredContent should be [] and the text could be "[]" (or a plain message like "No offers found.", depending on how we want the LLM to see it).
- By doing this, the client will see a content item of type text (valid), and if it’s capable, it can parse the structuredContent array directly. Under no circumstance should we use multiple {"type":"object"} entries for each item either – that would still be invalid and redundant. The correct representation of multiple results is either one aggregated text or leveraging structuredContent.
- String and Primitive Results: Tools that already return a simple string (e.g. an error message or a confirmation) are already handled as type: "text" by the wrapper[18] – we should keep that behavior. If a tool were to return a bare number or boolean in the future, we should handle it explicitly:
- Numbers/Booleans: Convert them to strings for the content. For example, if a hypothetical add_numbers tool returned 42, we’d return content [ { "type": "text", "text": "42" } ]. We could also set structuredContent: 42 (as a JSON number) if we adopt structured outputs.
- Null/None: If a tool returns None (no output), we should decide on a representation. The safe approach is to return an empty content array or perhaps a text content with "null". An empty content array ("content": []) is a valid result meaning “no content to display.” This might actually be a clean way to signify no data, as some clients might treat an empty content list as essentially a no-op result. Including structuredContent: null could further clarify it. In practice, none of our current tools return None explicitly (they return either data or an error object), so this is more of a precaution.
- TL;DR: Continue returning strings as text, and ensure any non-string primitive is not left as a raw object type. Cast or serialize everything into the appropriate format.
- Tool Errors as Content vs. Error Field: For error results (where the tool function returns {"error": "... message ..."}), the spec expects these to appear as a normal result (not a JSON-RPC error), but with isError: true and typically a text message describing the error[12]. Our server should:
- Include an isError: true flag in the result when returning a tool’s error outcome.
- Return the error message in a text content block. E.g. for an unauthorized call, instead of {"type":"object","object":{"error":"Unauthorized"}}, we send:

```text
"content": [ { "type": "text", "text": "Unauthorized or API key required." } ],
"isError": true
```

- The text is exactly the message that was in the error dict. This way the LLM can read the error easily. If we want, we can still include a structuredContent with the error structure, but that’s likely unnecessary (the text says it all in this case).
- Note that JSON-RPC’s own error mechanism ("error": { code, message } at the top level) is reserved for protocol issues (like invalid method, bad JSON, etc.). For tool execution errors, using the result with isError is the correct approach[19][12]. Our current code logs tool errors but passes them through as content; we should formalize it with isError.
- Maintain capabilities.tools.listChanged: We will leave this as false (still included) since that accurately tells clients we won’t send tools/list_changed notifications. This is compliant; no changes needed except to re-confirm it stays in the initialize response after our modifications[20].
- Protocol Version and structuredContent: We plan to keep the advertised protocolVersion as "2025-03-26" (the server currently echoes whatever the client requests on initialize). Introducing structuredContent is technically a 2025-06-18 feature. However, using it does not appear to break anything: the spec suggests servers should provide a text fallback for backward compatibility[5], which we are doing. Clients that only know 2025-03-26 will simply see an extra field and ignore it (which is fine). This approach has been seen in practice – some servers on 03-26 provide structuredContent anyway for forward compatibility. So, we can implement it now without changing the version, or we might consider bumping the supported version in the future once we fully adopt output schemas, etc. For now, the focus is on making Codex CLI happy and staying spec-aligned.

In summary, every tool response should be wrapped in a content array of standard types, typically just one "text" entry, and (if structured data) accompanied by a structuredContent field containing the raw JSON. This will make the output MCP-compliant and remove the “unexpected type” error.

## Request ID Handling in Responses

The requestId field currently appended to responses is not part of the MCP spec’s normal response object. In MCP, the JSON-RPC "id" is used to match requests and responses. The separate "requestId" (often a UUID in our case) is more of an internal tracking or used in server->client notifications (e.g., a cancel notification might include the requestId of the operation being cancelled)[21][22].

- Spec Stance: In the 2025-03-26 spec documentation and examples, no requestId appears in a standard tools/call result. The initialize response example, for instance, shows only jsonrpc, id, result, etc.[14]. The presence of requestId in our responses is therefore unofficial. It’s likely meant for debugging (the server generates a UUID per request and returns it, possibly so that logging or client-side can correlate the HTTP request).
- Client Impact: Well-behaved MCP clients should ignore unknown fields, so including requestId probably doesn’t break anything (the Codex CLI error is about response type, not an unknown field). However, to be safe and clean, we might remove or make optional the inclusion of requestId. The Codex CLI or other clients have no defined use for it on success messages (they have the JSON-RPC id to correlate). Removing it will make our responses closer to spec examples, eliminating any chance of confusion.
- Conclusion: Treat requestId as optional debug info. We can omit it in the final JSON sent to the client. If we want to keep it (for our own logging), ensure the clients truly ignore it – but given it’s not needed, the simplest path is to drop it. We’ll verify after changes that the output exactly matches what clients expect (no superfluous fields).

(In summary, requestId is unsupported by MCP spec in this context – neither required nor recommended. We will likely remove it from the payload to be strictly compliant.)

## Validity of capabilities.tools.listChanged = false

The server currently responds to initialize with:

```text
"capabilities": { "tools": { "listChanged": false } }
```

This is actually in line with the spec’s intention. The spec says servers that support tools must declare the tools capability and use listChanged to indicate whether they send list change notifications[23][17]. It does not forbid using false.

- Setting it to true means the server will push notifications/tools/list_changed events when its available tools list updates. Our server’s tools are static (and we haven’t implemented any such notification), so we set it to false. This explicitly tells the client “don’t expect tools/list_changed events.”
- Omission vs False: If we omitted listChanged entirely, a client might assume the server doesn’t support the feature (which effectively is the same as false). However, since the spec example always shows the flag (and other implementations do send "listChanged": false when appropriate), it’s perfectly valid to include it and set it false. In the PowerPlatform forum example, the Python SDK server also returned "listChanged": false[24], and the Node one returned true[25] – both are acceptable. There’s no indication that we must remove the flag when false.
- Therefore, we will keep listChanged: false. It’s correctly indicating our server’s behavior and is spec-compliant. No changes needed here, other than ensuring we don’t accidentally remove or misspell it during refactoring. This value will remain in the initialize response.

(For completeness: if in the future we implement dynamic tools or want to comply with 2025-06-18 changes, we might add other capability flags or set listChanged: true along with actually sending notifications. But that’s out of scope for now.)

## Action Plan for Code Changes and Testing

Based on the above findings, here is a step-by-step plan to fix the server’s tools/call response format and validate it:

1. Modify _wrap_tool_result in qortal_mcp/server.py:
- Remove the "object" content type usage. Instead of treating all non-strings as type: object, we will branch logic more finely: - If result is a dict and contains an "error" key, handle it as an error case (see step 2 below). - Elif result is a dict (and not an error dict), or a list, or any other JSON-serializable structure: - Create a content item of type: "text" and set its "text" to a JSON string representation of result. Use json.dumps(result) to ensure proper JSON formatting (keys in quotes, etc.) rather than Python’s str(). This yields a string like "{\"isValid\": false}" for a dict or "[{...}, {...}]" for a list. - Also, prepare to include a structuredContent field set to the original result object itself. (We should deep-copy or ensure it’s JSON-safe; since our results are already JSON-compatible dicts/lists from the Qortal API, this should be fine. Just be careful if any custom objects appear – not the case here.) - Example code change:

```text
import json
def _wrap_tool_result(result: Any) -> Dict[str, Any]:
    content_item = {}
    if isinstance(result, str):
        content_item = {"type": "text", "text": result}
        return {"content": [content_item]}  # No structuredContent for plain text
    if isinstance(result, dict) and "error" in result:
        # Handle error separately (we'll do this in step 2)
        ...
    else:
        # Handle structured (dict/list/number) result
        try:
            json_text = json.dumps(result)
        except Exception:
            json_text = str(result)  # Fallback: in case of non-serializable, use str()
        content_item = {"type": "text", "text": json_text}
        wrapped = {"content": [content_item]}
        # Attach structuredContent if result is dict/list (structured data)
        if isinstance(result, (dict, list)):
            wrapped["structuredContent"] = result
        else:
            # For primitives (int, bool), we can also put them in structuredContent directly
            wrapped["structuredContent"] = result
        return wrapped
```

This is a sketch; the actual code should integrate with existing logging and structure. The idea is clear: always return text content, and add structuredContent for non-string outputs. - Why json.dumps? Using json.dumps ensures that, for example, Python False becomes false in the text, etc. The text will be a proper JSON snippet that the client (or the LLM) can parse if needed. The double quotes in the JSON will be escaped in the string – which is fine. (Clients may display it prettily or the LLM can read it as code.) We need to ensure ensure_ascii=False in dumps if we want to preserve unicode in text, but that’s a minor detail. - Do not return multiple content items for each list element; we stick to one content item carrying the whole JSON string (this keeps the response concise and logically grouped). - Edge cases: If result is already a JSON string (some tool might conceivably return a JSON string), our code would treat it as str and just return it, which is fine. If result is None, json.dumps(None) yields "null" as a string, which is acceptable. - This change directly addresses the “Unexpected response type” issue: after this, all content items will have a valid, known type (usually "text"), so the Codex CLI will not choke on an unknown type.

2. Implement Proper Error Result Handling: - In _wrap_tool_result, add a branch for error dictionaries. Many tool functions return {"error": "...message..."} on failure (we saw this in list_trade_offers, get_balance, etc. functions)[26][27]. We should detect this and format accordingly: - Extract the error message string (e.g. msg = result.get("error")). - Create a content item: {"type": "text", "text": msg} to convey the error. - Set an isError flag in the output result object: e.g. wrapped = {"content": [ {...} ], "isError": True}. - Do not include the entire {"error": "..."} struct in structuredContent, unless we want to for completeness. Typically, the plain message suffices. If we think it's useful, we could set structuredContent = result as well so that programmatic clients know the error in structured form. However, since result in this case is just {"error": "some text"}, the text and structuredContent would be duplicative. We might skip structuredContent here to avoid confusion – or we include it for consistency. (Including it doesn’t hurt, but it’s arguably redundant.) - This aligns with spec examples, where tool execution errors are indicated by isError: true and a human-readable explanation in content[12]. - Example: get_balance with an invalid address currently returns {"error": "Invalid Qortal address."}. After our change, the JSON-RPC result would be:

```json
{
  "content": [ { "type": "text", "text": "Invalid Qortal address." } ],
  "isError": true
}
```

(Optionally, we might attach structuredContent: {"error": "Invalid Qortal address."} as well, but likely unnecessary.) - Update logging or metrics if needed: currently _log_tool_result in server.py logs success vs error by checking if result.get("error")[28]. After our changes, if we encapsulate the error inside the result’s content, the original result passed to _log_tool_result is still the error dict (since we call _log_tool_result before wrapping in JSON-RPC payload)[29]. That remains unchanged, so logging will still catch it. Just ensure we don’t accidentally double-wrap errors somewhere. - Protocol errors (like -32601 unknown method) remain handled separately in _mcp_gateway (returning JSON-RPC "error" fields) – we don’t touch those. We only format tool execution errors inside the result.

3. Remove or disable the extra requestId in responses: - Check the implementation of _jsonrpc_success_payload (it’s not shown in the snippet, but likely analogous to _jsonrpc_error_payload we saw[13]). It probably adds requestId similar to the error payload function. We should modify these helpers so that they do not inject requestId into the final payload (or do so only if absolutely needed for some reason). - Since request_id is used internally for logging and we set it as the X-Request-ID header, we can continue generating it for correlation between logs and responses, but we don’t have to include it in the JSON body. Many clients (like VSCode or Copilot) ignore it, but it’s cleaner to remove. So: - In _jsonrpc_success_payload, simply return {"jsonrpc": "2.0", "id": rpc_id, "result": result} (and no requestId). - In _jsonrpc_error_payload, return {"jsonrpc": "2.0", "id": rpc_id, "error": {code, message}} (and no requestId). - If we want to keep it for debugging, perhaps hide it behind a configuration or include it only in non-production mode. However, likely not needed. We have the header and logs for that. - This ensures the output strictly adheres to JSON-RPC 2.0 + MCP spec format. We should verify that after this change, our initialize response still contains capabilities, etc., but no extraneous fields.

4. Integrate Output Schema (optional but recommended):
(This is an optional enhancement for completeness)
Since we are effectively implementing structured output, we can also specify an outputSchema for each tool in the TOOL_REGISTRY (in qortal_mcp/mcp.py). This schema is a JSON Schema that describes the structure of structuredContent. Doing so is part of MCP 2025-06-18 features (tools can advertise their output format)[30][31]. While our server will still declare itself 2025-03-26, adding outputSchema is harmless metadata in the tools/list response and can help future-proof: - For example, define output_schema for get_node_status as:

```text
"outputSchema": {
    "type": "object",
    "properties": {
        "height": { "type": "integer" },
        "isSynchronizing": { "type": "boolean" },
        "syncPercent": { "type": ["integer","null"] },
        "isMintingPossible": { "type": "boolean" },
        "numberOfConnections": { "type": "integer" }
    },
    "required": ["height","isSynchronizing","isMintingPossible","numberOfConnections"]
}
```

(and so on for others). This matches the design’s output examples[32]. - For list_trade_offers, outputSchema could be:

```json
{ "type": "array", "items": {
    "type": "object",
    "properties": {
       "tradeAddress": {"type":"string"}, "creator": {"type":"string"},
       "offeringQort": {"type":"string"}, "expectedForeign": {"type":"string"},
       "foreignCurrency": {"type":"string"}, "mode": {"type":"string"}, "timestamp": {"type":"integer"}
    },
    "required": ["tradeAddress","creator","offeringQort","expectedForeign","foreignCurrency","mode","timestamp"]
  }
}
```

(This is based on what _normalize_offer produces[33].) - Add these schemas to the ToolDefinition entries in TOOL_REGISTRY. The structure might involve adding an output_schema field to the ToolDefinition dataclass and including it in list_tools() output. If modifying that is too large a change, this step can be skipped for now. It’s not strictly required to fix the CLI error – it’s more for clarity and to fully embrace structured outputs. We mention it here as a recommendation. - If implemented, the tools/list response will include each tool’s outputSchema (clients like Codex CLI or others might use it to validate or better format the results). This complements our use of structuredContent.

5. Adjust Tests to the New Response Shape:
We need to update unit tests to match the new wrapping logic: - In tests/test_mcp_gateway.py, the tests that currently expect content[0]["type"] == "object" must be changed. For example: - test_mcp_call_tool_validate_address: It posts a call to validate_address with an invalid address and then does:

```text
content = data["result"]["content"][0]
assert content["type"] == "object"
assert content["object"] == {"isValid": False}
```

After our fix, the response for that call (address "bad") will be a successful call (not an error, since isValid:false is a legitimate result). We expect: - content[0]["type"] == "text" - The text should be the string "{"isValid": false}" (JSON representation). - And data["result"]["structuredContent"] == {"isValid": False} (the actual JSON object). - So we will change the assertions to something like:

```text
assert content["type"] == "text"
assert isinstance(content["text"], str)
parsed = json.loads(content["text"])
assert parsed == {"isValid": False}
assert data["result"]["structuredContent"] == {"isValid": False}
assert "isError" not in data["result"] or data["result"]["isError"] is False
```

(The last assert just confirms no error flag for this case.) - We might need to import json in the test or otherwise compare the string. Simpler: we could do assert "\"isValid\": false" in content["text"] to ensure the text contains the JSON snippet. But a proper parse is safer to avoid formatting issues. - test_mcp_tools_call_alias: This is essentially the same call using "method": "tools/call" alias, and expects the same structure[34]. We’ll update it in parallel with the above. - No other tests in that file check the content structure except those. The list tools are not directly tested via MCP gateway in this commit’s tests (they test list_trade_offers in isolation). We should add new tests: - A test for a list output via the MCP endpoint. For example, we can simulate or stub list_trade_offers similar to how the unit test does, but through the API. Since the TestClient would call the real implementation, we might not want to hit an actual node. Instead, we can monkeypatch default_client.fetch_trade_offers or inject a stub client in the app context. Simpler: call the mcp endpoint with {"name": "list_trade_offers", "arguments": {"limit": 1}} after perhaps seeding one dummy offer. - Alternatively, adjust list_trade_offers to have a deterministic output for test (not great to alter code for test). Given time, we might skip adding a new test for list output here, but manual testing with curl (see step 6 below) will cover it. If we do add:

```text
def test_mcp_call_tool_list_offers(monkeypatch):
    # Monkeypatch the client call to return a known list
    monkeypatch.setattr(qortal_mcp.tools.trade, "default_client", DummyClientReturningOneOffer())
    client = TestClient(app)
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "list_trade_offers", "arguments": {}}
    })
    data = resp.json()
    assert data["result"]["content"][0]["type"] == "text"
    text = data["result"]["content"][0]["text"]
    # Check that text is a JSON array (starts with '[')
    assert text.strip()[0] == '['
    # Parse and verify structuredContent
    offers = data["result"]["structuredContent"]
    assert isinstance(offers, list)
    assert offers and isinstance(offers[0], dict) and "tradeAddress" in offers[0]
```

This is a pseudo-test; actual implementation depends on how we can intercept the data source. - A test for an error case via MCP: e.g., call get_balance with an invalid address: python def test_mcp_call_tool_error(): client = TestClient(app) resp = client.post("/mcp", json={ "jsonrpc": "2.0", "id": 6, "method": "call_tool", "params": {"tool": "get_balance", "params": {"address": "INVALID"}} }) data = resp.json() # It should not have "error" at top-level (since it's a successful JSON-RPC response) assert "error" not in data result = data["result"] assert result.get("isError") is True content = result["content"][0] assert content["type"] == "text" assert "Invalid Qortal address" in content["text"] # No structuredContent expected or, if present, it's the error dict This ensures our error formatting is correct. Note: For this to work, the server must not require a valid address format (our implementation does validate addresses early). In get_balance, we have a check if not is_valid_qortal_address(address): return {"error": "Invalid Qortal address."}[35], so this will trigger our error handling nicely. - Update any expected values accordingly. Also, ensure the initialize test still passes: it expects protocolVersion echo and listChanged false, which we’ll still provide[20]. Removing requestId should not affect tests because our tests didn’t assert its presence. - Run the test suite. All tests should pass after adjusting them. The content structure assertions are the main ones to fix.

6. Manual Verification with cURL or CLI:
After implementing the changes and running unit tests, it’s important to verify the actual HTTP responses to ensure the format is correct and that Codex CLI will accept them. We can use curl or a similar tool to simulate the MCP client:

- Tool returning an object (e.g. get_node_status):
Run:

```text
curl -X POST http://localhost:PORT/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_node_status","arguments":{}}}'
```

- Expected response structure (formatted for clarity):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"height\":123,\"isSynchronizing\":false,\"syncPercent\":null,...}"
      }
    ],
    "structuredContent": {
      "height": 123,
      "isSynchronizing": false,
      "syncPercent": null,
      "isMintingPossible": false,
      "numberOfConnections": 8
    }
  }
}
```

- Verify that:
- There is no "type": "object" anywhere.
- content[0].type is "text".
- The text is a JSON string of the object (check that it starts with { and ends with } inside quotes, etc.).
- structuredContent exactly matches the JSON (we can compare after parsing the text).
- No requestId field in the payload.
- This should satisfy Codex CLI. The CLI will see a known content type and possibly use the structuredContent for structured data (depending on its sophistication).
- Tool returning a list (e.g. list_trade_offers):
If possible, set up a scenario where the node has at least one trade offer (or stub the response). Assuming it returns an array of offers:

```text
curl -X POST http://localhost:PORT/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_trade_offers","arguments":{}}}'
```

- Expected response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"tradeAddress\":\"Q...\",\"creator\":\"...\",\"offeringQort\":\"123\",...}, { ...second offer... }]"
      }
    ],
    "structuredContent": [
      {
        "tradeAddress": "Q....",
        "creator": "....",
        "offeringQort": "123",
        "expectedForeign": "0.005",
        "foreignCurrency": "LTC",
        "mode": "SELL",
        "timestamp": 1698791234
      },
      { ... next offer object ... }
    ]
  }
}
```

- If no offers exist, it might look like:

```text
"content": [ { "type": "text", "text": "[]" } ],
    "structuredContent": []
```

- We should check that the text is a JSON array string and that structuredContent is an array of objects or empty. Codex CLI should handle this gracefully now. It won’t see a strange type; it might either feed the text to the LLM or, if it’s advanced, iterate the structured array.
- Tool returning an error (e.g. get_balance with bad address):

```text
curl -X POST http://localhost:PORT/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_balance","arguments":{"address":"12345"}}}'
```

- (Use an obviously invalid address format to trigger the validation error.) Expected:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [ { "type": "text", "text": "Invalid Qortal address." } ],
    "isError": true
  }
}
```

- Confirm:
- The response is a JSON-RPC success (HTTP 200 with a "result" field, not an "error" field at the top – meaning the request was valid, it’s the tool execution that failed).
- Inside result, isError: true is set.
- The content has one item of type text with the error message.
- No structuredContent is fine here (not necessary). If our implementation included it (say as the original {"error":...} dict), verify it’s correct. But likely we won’t include it to keep it simple.
- This format will be recognized by clients. The CLI should see isError:true and know the tool failed, and the LLM will get “Invalid Qortal address.” as the output to possibly inform the user.
- We should also test the initialize flow quickly to ensure we didn’t break it:

```text
curl -X POST http://localhost:PORT/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":100,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}'
```

- Expected:

```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "result": {
    "protocolVersion": "2025-03-26",
    "serverInfo": { "name": "qortal-mcp-server", "version": "0.1.0" },
    "capabilities": { "tools": { "listChanged": false } }
  }
}
```

- Ensure listChanged is still false and present, and no requestId present. The tests already cover this scenario, so it should pass.

7. Documentation Updates:
- README/DESIGN: If the repository’s README or DESIGN.md document the response format for tools, we must update those examples. The DESIGN.md currently shows example outputs as raw JSON objects or arrays (assuming they are the content of the response)[32][36]. We should clarify that those are the structuredContent now, and that the actual JSON-RPC response will wrap them accordingly. - For instance, the DESIGN might have a section for how the MCP gateway responds. We can add a note: “Tool results are returned with a content array containing a text JSON representation, and a structuredContent field with the machine-readable JSON. Errors are indicated with isError:true.” Adjust any sample JSON in docs to match (similar to the examples we crafted above). - README Examples: If the README provided an example tools/call usage, update it. Make sure to remove any mention of the old "type": "object" format. Instead, showcase the new format. This will prevent confusion for developers reading the docs. - Changelog/Comments: It might be worth adding a note in code comments or a CHANGELOG about this change, since it affects clients. Something like: “Changed: Tools/call results now use content.type="text" (with JSON string) and structuredContent for structured outputs, instead of the non-standard type="object". This fixes compatibility with MCP clients (Codex CLI, etc.).” Also note that isError is now used for tool errors.

By following this plan, the MCP tools/call response will be fully compliant with the spec and the Codex CLI should accept it without errors. We will have:

- Proper wrapping of objects and lists (as text content + structuredContent).
- Correct error indication with isError.
- No extraneous fields in the JSON (only standard ones).
- The capabilities remain correctly advertised.

The outcome: Codex CLI and other MCP clients will no longer see “Unexpected response type,” and the structured data from Qortal (node status, trade offers, etc.) will be accessible in a standard way. The implementation will be aligned with MCP 2025-03-26 (with a nod to 2025-06-18’s structured output practice for future-proofing), which fulfills the audit recommendations.

[1] MCP 2025-06-18 Spec Update: AI Security, Structured Output, and User Elicitation for LLMs | Forge Code

https://forgecode.dev/blog/mcp-spec-updates/

[2] [7] [12] [17] [19] [23] Tools - Model Context Protocol

https://modelcontextprotocol.io/specification/2025-03-26/server/tools

[3] [4] [5] [6] [30] [31] Tools - Model Context Protocol

https://mcp.mintlify.app/specification/2025-06-18/server/tools

[8] [13] [16] [18] [28] [29] server.py

https://github.com/QuickMythril/qortal-mcp-server/blob/353df381779827972a362d5f06d93cc9bfa5f624/qortal_mcp/server.py

[9] [20] [34] test_mcp_gateway.py

https://github.com/QuickMythril/qortal-mcp-server/blob/353df381779827972a362d5f06d93cc9bfa5f624/tests/test_mcp_gateway.py

[10] [11] [26] [33] trade.py

https://github.com/QuickMythril/qortal-mcp-server/blob/beb2e613ae62c6db39948b3fb2d249e558dde7b1/qortal_mcp/tools/trade.py

[14] [15] [24] [25]  Power Platform Community Forum Thread Details

https://community.powerplatform.com/forums/thread/details/?threadid=7ec056e9-f950-f011-877a-7c1e5247028a

[21] A Comprehensive Guide to MCP-WebSocket Servers for AI Engineers

https://skywork.ai/skypage/en/A-Comprehensive-Guide-to-MCP-WebSocket-Servers-for-AI-Engineers/1972577355133153280

[22] GitHub modelcontextprotocol/modelcontextprotocol LLM Context

https://uithub.com/modelcontextprotocol/modelcontextprotocol/tree/main/docs/specification/2025-03-26

[27] [35] account.py

https://github.com/QuickMythril/qortal-mcp-server/blob/beb2e613ae62c6db39948b3fb2d249e558dde7b1/qortal_mcp/tools/account.py

[32] [36] DESIGN.md

https://github.com/QuickMythril/qortal-mcp-server/blob/353df381779827972a362d5f06d93cc9bfa5f624/DESIGN.md
