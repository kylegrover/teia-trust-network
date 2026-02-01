# v4 — review & summary notes

Purpose: review `v1.md`, `v2.md`, `v3.md`, `v3-claude-notes.md` against `v4.md` and capture
what was kept, what was lost, what Claude added that is not yet addressed, and prioritized
suggested edits for `v4`/implementation. Use this as a living checklist while you iterate.

---

## Executive summary ✅

- Big win: `v4` is **engineering-ready** — clear phases, concrete infra (DipDup, Postgres,
  EigenTrust++), and federation plans. Many of Claude's reuse recommendations are
  integrated (Bluesky/Nostr, EigenTrust seed ideas, forensic modules).
- Keep from earlier drafts: the **Traffic-Light UX**, **Depth-2 cap**, and **default
  Teia banlist** are preserved and should remain central.
- Restore / clarify (high priority): **reason_hash** on distrust reports, a small set
  of human-readable fallback heuristics for Phase 2 (transparent weights / decay),
  explicit **subscription-privacy** guarantees, and explicit mention of **Teztok/TzKT**
  as Phase‑1 data sources.
- Short-term outcome: add the items below to `v4` (or append an explicit "MVP heuristics"
  section) and implement the Depth-2 neighbor materialized cache + monitoring.

---

## How I reviewed

- Read: `plan/v1.md`, `plan/v2.md`, `plan/v3.md`, `plan/v3-claude-notes.md`, `plan/v4.md`.
- Goal: identify ideas in earlier docs or Claude notes that are **missing**, **weakened**,
  or **need operational specificity** in `v4`.

---

## Major wins in `v4` (keep these) ✅

- Phased roadmap (DipDup → Trust API → Trust Engine → Federation) — actionable.
- Traffic-Light UX preserved (good for transparency & UX).
- Explicit plan for Sybil resistance, wash-trade detection, and identity anchors.
- Federation plan (Bluesky labeler + Nostr lists) is well thought-out and decoupled.
- Operational focus: materialized snapshots, DipDup, Postgres schema — ready for devs.

---

## Items present earlier but under-specified or missing in `v4` (recommend restore) ⚠️

1. reason_hash on `distrust()` (v1, v2): enables verifiable explanations (IPFS link)
   - Why keep: auditability + appeals; low-cost UX improvement.
   - Suggested insertion (contract API):

```text
distrust(target_address, reason_hash)  // reason_hash = IPFS CID (optional)
```

2. Simple, transparent Phase‑2 heuristics (from v1): human-readable fallback used by
   the frontend while the Trust Engine converges (Direct=1.0, 2nd=0.4, explicit vouch=2.0)
   - Why keep: makes MVP explainable and debuggable for users and auditors.
   - Suggested snippet for `v4`'s Phase 2 / MVP heuristics (copy-paste):

```text
MVP heuristic (client-side, transparent):
- Direct collection (Depth 1): +1.0
- 2nd-degree collection (Depth 2): +0.4
- Explicit vouch: +2.0
- Time decay / repeated collections: +0.1 per repeat (cap 1.0)
- If banlist match → RED overrides
```

3. Time-weighting / repeated-collection signal (v1): not explicit in Phase 3
   - Why keep: improves Sybil resistance and rewards continued engagement.
   - Suggest: add as an input feature to EigenTrust++ or as a pre-normalization step.

4. Teztok & TzKT as explicit Phase‑1 data sources (Claude notes / v3):
   - Why keep: Teztok already exposes collector→creator relations; TzKT provides
     accurate account age and transfer metadata.
   - Suggested line for `v4`: "Phase 1 data sources: Teztok (primary NFT graph),
     TzKT (account metadata), plus DipDup for live contract indexing." 

5. Subscription privacy & label granularity (Claude):
   - Missing detail: guarantee that subscribing to a banlist is a client-side
     preference (not broadcast) and the ability to attach labels to specific
     tokens as well as accounts.
   - Suggestion: add a short privacy spec and per-token label capability to Phase 2.

6. Appeal / dispute workflow + provenance for `distrust()` (v1 & v2):
   - Missing detail: process for an artist to rebut a distrust signal and how
     revocations are audited; add a small appeals subsection.

---

## Claude's notes — what's already addressed vs. what's still open

- Addressed in `v4`:
  - Study/borrow from Bluesky (labelers) and Nostr — **implemented** in federation plan.
  - Performance caution: materialize Depth-2 neighbor sets and snapshotting — **explicit**.
  - EigenTrust / seed strategy idea — **present** in Phase 3.
  - Reuse Tezos tooling patterns (indexer → cache) — **present**.

- Not (or only partially) addressed in `v4`:
  - **Label subscription privacy** (Claude: private subscription semantics) — not specified.
  - **Per-token labels** (attach label to a token not only an account) — not explicit.
  - **Explicit recommendation to use Teztok/TzKT** is present in Claude notes but only
    partially reflected in `v4` (add to Phase 1 data-source list).

---

## Prioritized recommended edits for `v4.md` (copy-paste ready) — implement in this order

1. Add `distrust(reason_hash)` and appeals + provenance (Priority: P0 — small doc change).
   - Effort: tiny. Rationale: transparency + audit trail.
   - Patch text (suggested):

> Contract action: `distrust(target_address, reason_hash?)` — optional IPFS CID
> linking to evidence or explanation. All revocations are auditable and surfaced
> in the UI. Include a lightweight appeal flow: owner may submit `appeal(cid)`; appeals
> are recorded and visible to subscribers.

2. Add an "MVP heuristics" subsection under Phase 2 (P0 — important for UX clarity).
   - Effort: tiny. Rationale: keeps Traffic-Light deterministic and explainable.
   - Proposed snippet: (see above under "Simple, transparent Phase‑2 heuristics").

3. Explicitly list Phase‑1 data sources: Teztok + TzKT + DipDup (P0).
   - Effort: tiny. Rationale: developer onboarding & reproducibility.

4. Subscription privacy & per-token label capability (P1).
   - Effort: small doc + API design work. Rationale: privacy-preserving UX and
     finer-grained moderation.
   - Proposed acceptance criteria: "Subscribing to a list is a local preference by
     default; server may record an opaque subscriber count but not individual
     subscriptions unless the user opts in. Labels may target tokens and/or accounts."

5. Add time-decay / repeat-collection weighting to inputs (P1).
   - Effort: small. Rationale: improves Sybil resistance and UX signals.
   - Proposed rule: "Each repeated collect from the same observer→creator adds
     +0.1 up to a cap of +1.0; older interactions decay by half-life (e.g., 180 days)."

6. Document appeals & governance for disputed banlist entries (P1-P2).
   - Effort: medium (policy + UI + contract hooks). Rationale: legal & community trust.

---

## Concrete snippets you can paste into `v4.md` (exact, short)

1) Contract API addition (Phase 2 / Smart Contract)

```text
// Trust Registry — additions
distrust(target_address, reason_hash?)   // reason_hash: optional IPFS CID to evidence
revoke_distrust(target_address)
appeal(target_address, appeal_reason_cid?) // recorded on-chain for transparency
```

2) MVP heuristic (Phase 2)

```text
MVP Heuristic (client-side, auditable):
- Direct collection (Depth 1): +1.0
- 2nd-degree collection (Depth 2): +0.4
- Explicit vouch: +2.0
- Repeated collects: +0.1 per repeat, cap +1.0
- Banlist membership: RED (overrides green)
```

3) Phase 1 data-source sentence

```text
Phase 1 data sources: Teztok (primary NFT collection graph), TzKT (account & first-transaction metadata), plus DipDup for live contract event ingestion.
```

4) Subscription privacy acceptance criteria (short)

> By default, subscriptions to banlists are client-side preferences and are not
> broadcast; the system may expose only aggregated subscriber counts. Users may
> choose to publicly attest subscription on-chain if they want to signal alignment.

---

## Quick risk & mitigation summary (operational) 🔧

- Risk: Phase‑1 snapshot cost will grow with users.
  - Mitigation: materialize Depth-2 neighbor sets, incremental updates, TTL-based
    cache invalidation, monitor compute + storage per-user.
- Risk: Vouch/distrust spam or revenge reporting.
  - Mitigation: gas cost + rate limits + evidence `reason_hash` + reputation
    penalties in Trust Engine.
- Risk: Privacy concerns about list subscriptions.
  - Mitigation: default to local preference, only store aggregate metrics.

---

## Immediate next steps (recommended — 2-week sprint) 🏃‍♂️

1. Update `v4.md` with the P0 edits above (contract `reason_hash`, MVP heuristics,
   Phase‑1 data sources). — owner: product/tech writer. (1 day)
2. Add a minimal API spec for `/trust/{observer}/{target}` including the
   human-readable heuristic fallback and the canonical JSON shape. — owner: backend. (2 days)
3. Prototype DipDup handler + small script that materializes Depth‑2 neighbor sets
   for 10k active users; measure CPU/RAM/storage. — owner: infra. (5 days)
4. Draft subscription-privacy text and a per-token-label proposal for the UI.
   — owner: legal/ux. (3 days)

---

## Appendix — mapping (where an idea first appears)

- Traffic-Light UX: v2.md, v3.md → preserved in v4.md
- Depth-2 cap: v2.md, v3.md → preserved in v4.md
- `reason_hash` for distrust: v1.md → **restore in v4**
- Teztok / TzKT data-source recommendation: `v3-claude-notes.md` & v3.md → **add to v4**
- Subscription privacy & per-token labels: `v3-claude-notes.md` → **expand in v4**
- MVP heuristic weights: v1.md → **re-introduce in v4 for transparency**

---

If you'd like, I can (pick one):
1) Open a PR adding the P0 doc changes to `plan/v4.md` with the exact patches above; or
2) Create a small `trust-mvp.md` that expands the heuristic API + example JSON responses;
3) Start a DipDup prototype (I can scaffold handlers and a small dataset plan).

Which of the three should I do next? 
