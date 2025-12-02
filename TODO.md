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
- `get_block_at_timestamp`: core returns errors at/just before genesis (e.g., 1593450000000). Add clearer error mapping for timestamps before first block (e.g., “No block at or before timestamp.”) or clamp to genesis min timestamp.
- `list_block_signers`: currently returns “Node unreachable”; verify client path/response handling (`/blocks/signers`, expect list) and fix wiring.
- `get_minting_info_by_height`: returns “Node unreachable”; verify path (`/blocks/byheight/{height}/mintinginfo`) and response type; map missing height to clear error.
- `list_transactions_by_creator`: Core requires `confirmationStatus`; tool currently omits it, causing “Invalid parameters.” Add required confirmation_status, validate Base58 public key, and clamp limits.
- `list_transactions_by_block`: inconsistent “Qortal API error” for some block signatures; add Base58/length validation, ensure client uses `expect_dict=False`, map BLOCK_UNKNOWN/INVALID_SIGNATURE to clear errors.

## Trade validation (pending)
- Validate `get_trade_detail` against live offers now that AT addresses are surfaced; add AT-format validation if needed. Optional but useful for end-to-end sanity.

## Optional/Deferred endpoints
- Address utilities (read-only): `/addresses/lastreference/{address}`, `/addresses/online`, `/addresses/online/levels`, `/addresses/publickey/{address}`, `/addresses/convert/{publickey}`.
- Admin read-only (optional): `/admin/settings`, `/admin/settings/{setting}`, `/admin/summary/alltime`, `/admin/enginestats`, `/admin/mintingaccounts`.
- Additional block/tx endpoints currently skipped: `/blocks/signature/{signature}/data`, `/blocks/signature/{signature}/transactions`, `/blocks/child/{signature}`, `/blocks/onlineaccounts/{height}`, `/blocks/signer/{address}`; transaction helpers like unitfee/fee/convert/raw/processing remain out of scope for now.
