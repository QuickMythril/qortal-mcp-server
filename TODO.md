# MCP TODO – API coverage & gaps

This list merges the gaps I found and the other CLI agent’s findings. Use it as the working checklist for upcoming fixes.

## Parameter gaps in existing tools
- `/crosschain/tradeoffers`: consider exposing `/crosschain/tradeoffers/hidden` (read-only) if still within safety guidelines.

## Endpoint coverage not yet implemented (read-only Core surface)
- Address utilities: Core offers `GET /addresses/lastreference/{address}`, `/addresses/validate/{address}` (server-side), `/addresses/online`, `/addresses/online/levels`, `/addresses/publickey/{address}`, `/addresses/convert/{publickey}`. Decide which to expose (all read-only) and add input validation.
- Trade portal extras: consider whether to expose hidden offers (`/crosschain/tradeoffers/hidden`) and/or detailed trade info endpoints, with limits.
- Admin read-only: currently exposing `/admin/status`, `/admin/info`, `/admin/summary`, `/admin/uptime` only. Core also has `/admin/settings`, `/admin/settings/{setting}`, `/admin/summary/alltime` (API key), `/admin/enginestats` (API key), `/admin/mintingaccounts`, etc. Add only the safe, read-only ones; rely on API key checks where required.

## Housekeeping / docs
- When adding new endpoints or parameters, update `DESIGN.md` to document the expanded whitelist, validation, and limits.
- Add/adjust tests for new parameter handling and validation (especially for the new arbitrary/search and crosschain filters, and offset clamping).

## New work items (blocks/transactions)
- Add block/time mapping tools: `/blocks/timestamp/{timestamp}`, `/blocks/height`, `/blocks/byheight/{height}`, `/blocks/summaries`, `/blocks/range/{height}` with chunked limits.
- Add transaction search tool wrapping `/transactions/search` with Core constraints (txType or address or limit<=20; block ranges only with CONFIRMED); clamp limits.
- Update MCP manifest/registry and config limits for block summary/range paging; add tests for validation.

## Block/transaction fixes (in progress)
- `get_block_at_timestamp`: mapped BLOCK_UNKNOWN/404/400 “block not found” responses to “No block at or before timestamp.” (retest genesis-edge).
- `list_block_signers`: removed from MCP surface for now; if re-enabled later, include limit/offset/reverse with safe defaults and verify `/blocks/signers` wiring.
- `get_minting_info_by_height`: removed from MCP surface for now; only re-add if we need minting info, with clear error mapping for missing/invalid heights.
- `list_transactions_by_creator`: added explicit confirmationStatus requirement earlier; now also maps INVALID_PUBLIC_KEY to a clear error. Re-test against Core.
- `list_transactions_by_block`: added limit/offset/reverse params with clamping and improved block-not-found mapping; retest against tip blocks/signature edge cases.

## Trade validation (pending)
- Validate `get_trade_detail` against live offers now that AT addresses are surfaced; add AT-format validation if needed. Optional but useful for end-to-end sanity.

## Optional/Deferred endpoints
- Address utilities (read-only): `/addresses/lastreference/{address}`, `/addresses/online`, `/addresses/online/levels`, `/addresses/publickey/{address}`, `/addresses/convert/{publickey}`.
- Admin read-only (optional): `/admin/settings`, `/admin/settings/{setting}`, `/admin/summary/alltime`, `/admin/enginestats`, `/admin/mintingaccounts`.
- Additional block/tx endpoints currently skipped: `/blocks/signature/{signature}/data`, `/blocks/signature/{signature}/transactions`, `/blocks/child/{signature}`, `/blocks/onlineaccounts/{height}`, `/blocks/signer/{address}`; transaction helpers like unitfee/fee/convert/raw/processing remain out of scope for now.

## New tasks from latest review
- QDN publisher field: confirm Core search payload; if present, include `publisher` in search_qdn outputs and update DESIGN to match (else document intentional omission).
- Name listing defaults: in name normalization, default `isForSale` to False when missing; keep `salePrice` null if absent. Add tests.
- Trade offer docs: clarify that `tradeAddress` is the AT address; current mapping supersedes the “creator trade address” suggestion.
- Asset balances roadmap: keep TODO to add limited assetBalances to account overview in a future iteration.
- MCP initialize test: add JSON-RPC `/mcp` initialize integration test to assert envelope fields.
- Docs cleanup: ensure DESIGN/README reflect current outputs (search_qdn example fixed; trade address semantics documented).
