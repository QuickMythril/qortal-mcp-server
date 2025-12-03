# MCP TODO – active work items only

Use this as the working checklist. Completed items should be removed when done.

## Ongoing upkeep (always in effect)
- Keep DESIGN/README updated whenever adding or changing endpoints/parameters.
- Add/update tests alongside code changes (validation, limits, mappings).
- Document intentional omissions/constraints when deferring endpoints or fields.

## Bug fixes / correctness (highest priority)
- None open.

## Planned additions (medium priority)
- Chat (read-only): add `/chat/messages`, `/chat/messages/count`, `/chat/message/{signature}`, `/chat/active/{address}` tools with validation (txGroupId XOR two addresses, timestamp floor), safe limits, and data truncation; document outputs and add tests for validation/error mapping.
- Groups (read-only): add `/groups` listings, owner/member lookups, group detail, members, invites (by address or group), join requests, and bans with address/group ID validation, GROUP_UNKNOWN mapping, clamped limits for unpaged endpoints, and output normalization; tests for validation and error mapping required.
- Crosschain: consider exposing `/crosschain/tradeoffers/hidden` (read-only) with safe limits/validation.
- Address/admin utilities (read-only): decide whether to add `/addresses/lastreference/{address}`, `/addresses/validate/{address}`, `/addresses/online`, `/addresses/online/levels`, `/addresses/publickey/{address}`, `/addresses/convert/{publickey}`; optional admin reads `/admin/settings`, `/admin/settings/{setting}`, `/admin/summary/alltime`, `/admin/enginestats`, `/admin/mintingaccounts` with proper validation and API key handling.

## Optional improvements
- Additional block/tx helpers (read-only): `/blocks/signature/{signature}/data`, `/blocks/signature/{signature}/transactions`, `/blocks/child/{signature}`, `/blocks/onlineaccounts/{height}`, `/blocks/signer/{address}`, and transaction helpers (unitfee/fee/convert/raw/processing) — add only if needed with safe limits.
- QDN publisher field: confirm Core search payload; if acceptable, include `publisher` in `search_qdn` outputs and update docs, otherwise document the omission.
- Asset balances roadmap: consider adding a bounded set of `assetBalances` to account overview in a future iteration.

## Blocked / waiting
- None.
