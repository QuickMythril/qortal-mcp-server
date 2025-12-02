# Qortal MCP Server (Python)

Read-only Model Context Protocol (MCP) server for exposing Qortal node and QDN data as tools to AI agents.

- Wraps a local Qortal node's HTTP API (e.g. http://localhost:12391).
- v1 is strictly read-only: no transaction signing or broadcasting.
- Initial focus: node status and account/balance queries.
