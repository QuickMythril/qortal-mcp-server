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

## Optional/Deferred endpoints
- Address utilities (read-only): `/addresses/lastreference/{address}`, `/addresses/online`, `/addresses/online/levels`, `/addresses/publickey/{address}`, `/addresses/convert/{publickey}`.
- Admin read-only (optional): `/admin/settings`, `/admin/settings/{setting}`, `/admin/summary/alltime`, `/admin/enginestats`, `/admin/mintingaccounts`.
- Additional block/tx endpoints currently skipped: `/blocks/signature/{signature}/data`, `/blocks/signature/{signature}/transactions`, `/blocks/child/{signature}`, `/blocks/onlineaccounts/{height}`, `/blocks/signer/{address}`; transaction helpers like unitfee/fee/convert/raw/processing remain out of scope for now.

## New tasks from latest review
- QDN publisher field: confirm Core search payload; if present, include `publisher` in search_qdn outputs and update DESIGN to match (else document intentional omission).
- Asset balances roadmap: keep TODO to add limited assetBalances to account overview in a future iteration.
