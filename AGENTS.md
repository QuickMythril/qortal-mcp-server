# Qortal MCP Server – AGENTS.md

## Purpose

This repository implements a read-only MCP server in Python that exposes Qortal blockchain and QDN data as tools for AI agents.

## Security Rules (MUST follow)

- **Read-only only.** Do NOT call any Qortal API endpoint that signs or broadcasts transactions, or that requires raw private keys.
- Never accept or log private keys, seeds, mnemonics, or wallet passwords.
- Assume the Qortal node may hold real funds. Any new tool must be reviewed for side effects before use.

## Qortal Node Assumptions

- Node HTTP API is available at `http://localhost:12391` by default.
- Sensitive endpoints may require an API key (`X-API-KEY`, `X-API-VERSION`).
- All network errors and invalid responses should be handled gracefully and surfaced as structured MCP errors.

## Coding Guidelines

- Language: Python.
- Prefer small, pure functions for each Qortal API wrapper (e.g. `get_node_status`, `get_account_overview`).
- Tool outputs should be compact, well-typed JSON objects designed for LLM consumption (no huge raw payloads unless strictly needed).
- For new tools, include docstrings that explain:
  - When the tool should be used.
  - What Qortal endpoint(s) it calls.
  - Any performance or rate-limit concerns.
