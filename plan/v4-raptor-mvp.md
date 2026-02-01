# Trust MVP — spec, API & examples

Purpose: provide a concise, developer-ready spec for the Traffic-Light MVP (Phase 1–2)
including the canonical API, JSON shapes, acceptance criteria, short reason-code taxonomy
(for `distrust`), caching/TTL rules, and minimal DB schema for rapid implementation.

---

## TL;DR ✅
- UI shows three states: `GREEN` / `YELLOW` / `RED` (Traffic-Light).  
- Server provides an auditable, deterministic fallback (MVP heuristics) and a
  materialized Depth‑2 neighbor cache.  
- `distrust` uses a short reason code (enum) for fast UX and optional `evidence_cid`
  (IPFS) for forensic detail.

---

## Public API (MVP)

1) GET /trust/{observer}/{target}
- Purpose: single canonical truth for frontend badge and explanation.
- Cache: 30m TTL (stale-while-revalidate allowed).

Response (200):
{
  "status": "GREEN|YELLOW|RED",
  "reasons": ["direct_collect", "vouched_by:tz1...", "banlist:teia-moderation"],
  "score_breakdown": {
    "direct": 1.0,
    "second_degree": 0.4,
    "vouch": 2.0,
    "repeats": 0.2,
    "decay_factor": 0.85
  },
  "trust_paths": [
    {"via": "tz1...", "edge": "collected_from", "weight": 1.0}
  ],
  "computed_at": "2026-01-31T12:00:00Z"
}

2) POST /trust/distrust  (authenticated)
- Purpose: allow users to add an on-chain (Phase 2) or off-chain (Phase 1 cache)
  distrust signal.  Immediate client feedback; on-chain tx optional/async.

Request body (client-side quick-report):
{
  "reporter": "tz1...",
  "target": "tz1...",
  "reason": "copymint",           // enum: see taxonomy below
  "note": "(optional) short human text",
  "evidence_cid": "ipfs://bafy..." // optional
}

Response (201):
{
  "status": "accepted",
  "id": "report_0123",
  "visible_in_ui": true
}

3) GET /trust/path?observer=...&target=...  
- Purpose: feed the "show trust path" UI. Returns up to N (default 5) shortest
  Depth‑2 provenance paths with edge provenance & timestamps.

---

## Reason-code taxonomy (short enum) — primary UX model
- copymint
- spam
- nsfw
- fraud
- harassment
- other

Notes: use short, machine-friendly keys in UIs and contracts. `other` requires a
non-empty `note` or optional `evidence_cid` (IPFS) to be accepted by moderation.
Allow `evidence_cid` for forensic reproducibility but do not require it for quick reports.

---

## MVP heuristics (deterministic & auditable)
- Direct collection (Depth 1): +1.0
- 2nd-degree collection (Depth 2): +0.4
- Explicit vouch: +2.0
- Repeated collects from same observer→creator: +0.1 per repeat (cap +1.0)
- Time decay: half-life = 180 days (apply multiplicatively to aged edges)
- Banlist membership (subscribed list) → RED (overrides GREEN)
- Final status resolution:
  - If any subscribed banlist contains target → RED
  - Else if weighted_sum >= 1.0 → GREEN
  - Else → YELLOW

Display rules: always show `reasons` and the minimal `trust_paths` used to
compute the status. Provide a one-click "View raw calculation" for auditors.

---

## Contract / on-chain API (Phase 2 — minimal)
- vouch(target_address)
- revoke_vouch(target_address)
- distrust(target_address, reason_code)     // reason_code: short enum
- revoke_distrust(target_address)
- (optional) attest_subscribe(list_id)     // public opt-in if user wants

Design note: store short `reason_code` on-chain; storing full `evidence_cid`
is optional to save gas (can instead reference an off-chain indexer record).

---

## DB schema (minimal — Postgres)

profiles
- address (pk), alias, first_seen_at, metadata_json

edges
- id, source_address, target_address, type (COLLECTED|VOUCH|MINTED),
  weight (numeric), last_seen_at, count

banlists
- id, source, address, reason_code, added_at, evidence_cid

distrust_reports
- id, reporter, target, reason_code, note, evidence_cid, created_at, on_chain_tx

materialized_neighbors
- address (pk), depth2_addresses jsonb, computed_at

Indexes: edges(source_address), edges(target_address), materialized_neighbors(computed_at)

---

## Privacy & subscription semantics (MVP)
- Subscriptions to third-party banlists are local preferences by default
  (client-side only). Back-end may store aggregated counts but **not** individual
  subscriber lists unless explicitly opted-in by user.  
- Public attestation: user may optionally publish a signed on-chain `subscribe(list)`
  if they want to signal alignment publicly.

---

## Example flows (UI + API)

A) New user visits artist page (no prior graph):
- GET /trust/{user=tzX}/{artist=tzY} → returns YELLOW + account_age
- UI: show `🟡 Unknown — First tx: 2h ago` and CTA: `Vouch` or `Subscribe to Teia Moderation`.

B) User reports a copymint quickly:
- Client POST /trust/distrust { reason: "copymint", note: "identical token" }
- Response: accepted; UI blurs token locally for that reporter's session.
- Indexer picks up report; if multiple unique reporters from different wallets
  cross threshold, add to provisional banlist.

C) Vouch without buying:
- Client calls on-chain `vouch(target)` (Phase 2) or POST /trust/vouch (Phase 1,
  cached). Frontend shows updated GREEN if weighted sum crosses threshold.

---

## Acceptance criteria (MVP)
- [ ] GET /trust/{observer}/{target} returns deterministic status using MVP heuristics.
- [ ] UI displays the `reasons` and at least one trust path for GREEN statuses.
- [ ] POST /trust/distrust accepts a short `reason` code and optional `evidence_cid`.
- [ ] Materialized Depth‑2 neighbor cache exists and can be refreshed incrementally.
- [ ] Subscription preferences are client-side by default; aggregated counts exist server-side.
- [ ] Unit tests for heuristic thresholds, decay, and banlist override behavior.

---

## Monitoring & metrics (MVP)
- Metric: pct. pages served with trust badge (target: >90% of profile views)
- Metric: avg response time for GET /trust (target: <120ms cached)
- Metric: false-positive rate from banlist takedowns (monitored with appeals)

---

## Next dev tasks (minimal sprint)
1. Implement FastAPI endpoint `GET /trust/{observer}/{target}` returning JSON above.
2. DipDup handler to populate `edges` and `materialized_neighbors` for active users.
3. React `TrustBadge` component that calls the API and renders `Traffic-Light` UI.
4. POST /trust/distrust endpoint + light-weight admin review UI for provisional banlist.