# Teia Trust Network — Existing Work & Reuse Opportunities

This document maps your plan against existing research, libraries, protocols, and projects that can be directly reused or adapted. It's organized by the layer of your system each item touches.

---

## 1. The Academic Foundation — Trust Graph Theory

Your Validity Graph (Layer 1) is essentially a **depth-limited, personalized Web of Trust**. This is a well-studied problem, and your Depth-2 cap is a smart, pragmatic constraint that sidesteps the hardest parts of the theory.

### Guha et al. — *Propagation of Trust and Distrust* (WWW 2004)

This is **the** foundational paper for what you're building. The authors developed a framework of trust propagation schemes and evaluated them on a network of 800K trust scores among 130K people (from the Epinions review site). The key finding: a small number of expressed trusts and distrusts per person is enough to predict trust between *any* two people with high accuracy.

Why it matters to you: your plan already implicitly does this — a collection is an implicit trust signal, and your `distrust()` contract action maps directly to their model. Their "atomic propagation" operators (Direct Propagation, Co-citation, Transpose Trust) are exactly the kinds of graph traversals your indexer will compute. Your Depth-2 cap (`You → A → B → Stop`) is their "Direct Propagation" operator applied twice, which they found to be among the most effective schemes.

**Read:** [Guha et al., WWW 2004 — Stanford/SNAP mirror](https://snap.stanford.edu/class/cs224w-readings/guha04trust.pdf)

### Kamvar et al. — *The EigenTrust Algorithm* (WWW 2003)

EigenTrust assigns each peer a global reputation score based on local trust values, weighted by the reputations of the peers doing the trusting. It's essentially PageRank applied to a trust graph, and it was designed specifically for P2P file-sharing networks to isolate peers distributing bad files.

Why it matters: you deliberately *don't* want a global score (your traffic light is personalized, not ranked), but EigenTrust's approach to **pre-trusted seeds** is directly relevant to your cold-start problem. Their system used a set of known-good peers as anchors; you could do the same with a curated set of "seed" collectors whose trust graph bootstraps the system for new users.

**Read:** [Kamvar et al., WWW 2003 — Stanford](https://nlp.stanford.edu/pubs/eigentrust.pdf)

### Douceur — *The Sybil Attack* (IPTPS 2002)

The original paper defining the threat model your system is designed to resist. The core argument: without a centralized identity authority, Sybil attacks (one entity controlling many identities) are theoretically always possible. Your system's defense is economic — Sybils are expensive to create because they require real spend (collections) or real gas (vouches) to generate trust signals. This is a well-understood and accepted mitigation strategy in the literature.

**Read:** [Douceur, IPTPS 2002](https://www.freehaven.net/anonbib/cache/sybil.pdf)

---

## 2. The Bluesky / AT Protocol Ecosystem — Your Closest Architectural Sibling

The AT Protocol's moderation system is the most direct real-world parallel to what you're proposing. The structural similarities are striking, and several components can be studied (or even forked conceptually) for Teia.

### Ozone — Stackable Labeling & Moderation

Bluesky's moderation architecture is built on **labelers**: independent services that tag content or accounts with labels (e.g., `spam`, `copymint`, `verified`). Users subscribe to labelers they trust, and their client stacks those labels on top of Bluesky's default moderation.

This maps almost exactly onto your **Layer 2 (Safety Layer)**:

| Your System | Bluesky/AT Protocol |
|---|---|
| "Teia Moderation" banlist (default) | Bluesky's hardcoded in-house labeler (default) |
| Subscribe to 3rd-party banlists | Subscribe to community labelers (up to 19 additional) |
| Content blurred with "click to reveal" | Labels trigger blur/hide/warn, configurable per-label |
| User can opt out of default list | User can switch to a different AppView with different defaults |

**Key design decisions you can steal:**
- Labels are attached to specific *posts or accounts*, not just accounts. This lets you block a copymint without nuking a legitimate artist who had one bad token.
- Subscription to a labeler is **private** — the PDS/AppView can infer it, but it's not broadcast. This is good for your privacy model.
- The label schema is extensible. Bluesky defines a core set (`porn`, `gore`, `spam`), but labelers can define custom labels. You could define `copymint`, `verified-artist`, `new-account` as your core set.

**GitHub:** [bluesky-social/ozone](https://github.com/bluesky-social/ozone)
**Labeler SDK:** [@skyware/labeler](https://skyware.js.org/guides/labeler/introduction/getting-started/) — a clean TypeScript library for building labeler services

### Blacksky — Community-Governed Moderation as a Case Study

Blacksky is an AT Protocol project that built a full community moderation stack on top of Bluesky for Black social media users. It's the closest existing example of a *community-specific* moderation layer on a decentralized protocol, and they've published extensively about their architecture.

Their stack includes: a self-hosted Ozone instance, an automated labeler (`rsky-labeler`) that scans new content, a "Green List" of shareable block lists, and a tool called SAFEskies that lets community moderators reorder and remove feed content without admin approval.

Why it matters to you: Blacksky proves that the "subscribe to community-maintained lists" model actually works at scale (their feeds are used by over 2.5M people). Their governance challenges and solutions are directly instructive for how Teia's moderation lists will evolve.

**GitHub:** [blacksky-algorithms](https://github.com/blacksky-algorithms)
**Website:** [blackskyweb.xyz](https://blackskyweb.xyz)

### AT Protocol Architecture — What NOT to Copy

The AT Protocol is purpose-built for social media with user-generated content. Some of its infrastructure doesn't translate to an NFT marketplace:

- **DIDs and PDSes** are for portable social identity. Teia users already have portable identity: their Tezos wallet address. You don't need this layer.
- **The Relay/Firehose** is for real-time streaming of all social activity. Your trust graph is updated periodically (your 30-min snapshot interval), not in real time. A simpler indexer → cache model is more appropriate.
- **Lexicons** (AT Protocol's schema language) are for cross-app interoperability. If Teia's trust system stays within Teia, you don't need a formal schema language — but if you ever want other Tezos marketplaces to consume your trust signals, this is worth revisiting.

**What you *should* study from AT Protocol:** the separation of concerns between infrastructure (indexing/relay) and application logic (labeling/moderation). Your Dual-Layer Architecture already does this well.

---

## 3. Nostr — A Simpler Parallel for Identity and Trust

Nostr is a radically simple decentralized social protocol. It's relevant here for two reasons.

### NIP-05 — DNS-Based Identity Verification

NIP-05 lets Nostr users map their public key to a human-readable domain-based identifier (e.g., `alice@example.com`). The domain owner vouches for the key by serving a JSON file at `/.well-known/nostr.json`.

This is a lightweight, decentralized identity verification pattern. You probably don't need it for Phase 1 (wallet addresses are sufficient), but for Phase 2, you could let artists link a verified domain or social handle to their Tezos address as an additional trust signal. This is essentially free to implement and adds a layer of "this is a real person" on top of your on-chain history.

**Spec:** [NIP-05 — nostr-protocol/nips](https://github.com/nostr-protocol/nips/blob/master/05.md)

### NIP-02 — Follow Lists as Trust Graphs

Nostr's follow list (Kind 3 events) is structurally identical to your implicit trust graph. When User A follows User B on Nostr, that's a public, on-chain signal of trust — the same signal your system derives from collections. Nostr clients already build and traverse these graphs for feed curation.

The key difference: Nostr follows are *explicit* social signals. Your system uses *implicit* economic signals (collections) as the primary trust edge. This is actually stronger for Sybil resistance, because collections cost money.

---

## 4. Tezos-Specific Infrastructure — Your Phase 1 Toolbox

Your Phase 1 ("The Lens") requires an indexer that can answer: *"Given wallet X, what creators have they collected from, and what have those creators' other collectors collected from?"* This is a 2-hop graph query on existing on-chain data. The good news: the infrastructure to do this already exists.

### Teztok — The Core Indexer

Teztok is an open-source indexer that aggregates and normalizes NFT data across the Tezos blockchain and exposes a **GraphQL API**. It's marketplace-agnostic and already tracks the `collector → creator` relationships you need.

This is almost certainly your Phase 1 indexer. You would query it to build the `User → Collected → Creator` graph, then compute Depth-2 neighborhoods client-side or in a caching layer.

**GitHub:** [teztok/indexer](https://github.com/teztok/indexer)

### TzKT — Blockchain-Level API

TzKT is the most popular general-purpose Tezos blockchain indexer and API. It provides token balance queries, transfer histories, and account metadata. It's the backbone that tools like NFTBiker use.

For your system, TzKT is useful for the **account age signal** in your Yellow (Unknown) state. You can query first-transaction timestamps directly: `/v1/accounts/{address}` returns account creation data.

**API:** [api.tzkt.io](https://api.tzkt.io)

### TzPro — Commercial NFT API

TzPro (by Trisigma/Trili) is a commercial API that decodes NFT marketplace activity across Teia, Objkt, fxhash, and many others. It already normalizes trades, listings, and offers into a unified format.

If Teztok's free tier isn't sufficient for your indexer's needs, TzPro is the production-grade alternative. It already understands Teia's contract patterns.

**Docs:** [TzPro NFT API](https://docs.tzpro.io/api/nft)

### Objkt GraphQL API

Objkt exposes its own GraphQL API at `data.objkt.com`. Since Objkt is the largest Tezos NFT marketplace and indexes most tokens (including those minted on Teia), this is a high-value data source for your trust graph. You can query collectors, creators, and transfer histories directly.

**Explorer:** [data.objkt.com/explore](https://data.objkt.com/explore)

---

## 5. Existing Teia Moderation Infrastructure — What You're Building On Top Of

Your plan doesn't start from zero on the safety side. Teia already has moderation infrastructure that maps directly onto your Layer 2.

### teia-community/teia-report — The Banlist

This GitHub repository is where Teia's moderation team maintains the account restriction list. It contains JSON files for restricted accounts, accounts under review, and IPFS URIs flagged for double-minting.

This is *literally* the data source for your default "Teia Moderation" banlist in Phase 1. Your indexer just needs to fetch and parse these JSON files — no new moderation workflow is required for the MVP.

**GitHub:** [teia-community/teia-report](https://github.com/teia-community/teia-report)

### copyminter.xyz — Community Detection Tools

This community-maintained site contains tools for detecting copyminters on Tezos. It's built on NFTBiker's toolset and uses TzKT as its data source.

For Phase 1, you don't need to replicate this — you just consume Teia's existing restricted list. But for Phase 2, the detection heuristics used here (account age, minting velocity, reverse image search signals) could be integrated as automated signals that feed into your banlist.

**Site:** [copyminter.xyz](https://copyminter.xyz)

### NFTBiker — The Community Tooling Standard

NFTBiker has built the most comprehensive suite of Tezos NFT tools: tracking, auditing, giveaways, batch operations. Everything is built on TzKT's API and runs client-side (no personal data collected).

NFTBiker's collection grouping tool already highlights copyminted OBJKTs — this is a manual version of what your Green/Red signals will automate. The tooling patterns here (browser extension with contextual menu, client-side graph computation) are worth studying for your frontend UX.

**Site:** [nftbiker.xyz](https://nftbiker.xyz)

---

## 6. Summary — What to Reuse, What to Study, What to Build

| Component in Your Plan | Reuse / Adapt | Study for Patterns | Build From Scratch |
|---|---|---|---|
| Validity Graph (Layer 1) | Guha et al. propagation model | EigenTrust seed strategy | Graph computation on Teztok data |
| Safety Layer (Layer 2) | teia-report banlist (direct) | Bluesky Ozone labeler architecture | Phase 2 custom list subscription |
| Indexer (Phase 1) | Teztok + TzKT APIs | — | Depth-2 neighbor cache layer |
| Traffic Light UX | — | Bluesky label severity/blur/warn | Badge components + account age display |
| Vouch Contract (Phase 2) | — | Nostr NIP-05 for identity linking | Trust Registry smart contract |
| Cold Start | EigenTrust seed concept | Blacksky onboarding patterns | Default subscription + first-collect trigger |
| Fail-Safe / Raw Mode | — | AT Protocol's "credible exit" principle | Graceful degradation when indexer is offline |

---

## 7. One Architectural Note

The biggest risk in your plan is **Phase 1 performance**. Computing Depth-2 neighborhoods for every active user every 30 minutes is a graph operation that will get expensive as the collector base grows. A few things from the existing work that bear on this:

Bluesky solves a similar problem (computing personalized feeds from a large social graph) by having the **AppView** do the heavy lifting, not the client. Their Relay aggregates and indexes, and the AppView pre-computes what each user needs. Your "Indexer Snapshots" approach is the same idea. The key implementation detail: store the pre-computed neighbor sets in a simple key-value store (wallet address → set of Depth-2 addresses), and invalidate on a rolling basis rather than recomputing everything at once.

Teztok's GraphQL API supports the queries you need, but you'll likely want to **materialize the graph locally** rather than hitting Teztok on every page load. A nightly or hourly batch job that walks the collector graph and writes neighbor sets to a cache (Redis, a simple database, or even a static JSON blob) is the standard pattern here — and it's what your 30-minute snapshot interval implies.