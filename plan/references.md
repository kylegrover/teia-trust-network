## Development References

Teia
- Teia UI Repository: The existing frontend where badges will be integrated.
    - (https://github.com/teia-community/teia-ui)
- Teia Marketplace Contracts: The smart contracts for marketplace operations.
    - hen minter: KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9
    - Hen mkt: (https://tzkt.io/KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton/operations)
    - Hen v2: (https://tzkt.io/KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn/operations)
    - teia market: KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w
- Teia Moderation Banlist: The source for flagged accounts.
    - 
- teia hicdex fork: https://github.com/teia-community/hicdex/
- teia teztok plugin:
    https://github.com/teztok/indexer/tree/main/src/plugins/teia
    this is the live data source used for teia ui currently feb 4 2026



Tezos Data & Indexing
- DipDup Framework: The primary tool for building the custom indexer.
    - (https://dipdup.io/docs/quickstart-tezos/)
- TzKT API: Essential for fetching raw block data and account metadata.
    - (https://api.tzkt.io/)
- Tezos Profiles (TZP): For linking Tezos addresses to social identities (Twitter/Discord).
    - (https://github.com/spruceid/tzprofiles)
- Teztok: (shutdown but open source)
    - https://github.com/teztok/indexer
- https://docs.tezos.com
    - https://docs.tezos.com/allPageSourceFiles.txt for full docs search
    - /developing/ipfs
    - /architecture/tokens
    - /architecture/data-availability-layer
    - /architecture/accounts
    - etc
- tezos tallin: https://spotlight.tezos.com/tallinn-is-live/

Algorithms & Math
- EigenTrust++: The core algorithm for global reputation scoring.
    - (https://faculty.cc.gatech.edu/~lingliu/papers/2012/XinxinFan-EigenTrust++.pdf)
    - https://github.com/Karma3Labs/ts-eigencaster
    - https://github.com/Karma3Labs/go-eigentrust
- Graphology: JavaScript library for client-side or Node.js graph analysis.
    - (https://graphology.github.io/)
- NetworkX: Python library for backend cycle detection (wash trading) and complex network analysis.
    - (https://networkx.org/)
    - https://github.com/Dreamerryao/nft-wash-trading

Federation Protocols

- Bluesky Ozone: The reference implementation for a Labeler Service.
    - (https://github.com/bluesky-social/ozone)
- AT Protocol Labels: Specification for creating custom trust labels.
    - (https://atproto.com/specs/label)
    - https://github.com/bluesky-social/atproto
- Nostr NIP-51: Standard for creating "Lists" (mute/allow lists).
    - (https://github.com/nostr-protocol/nips/blob/master/51.md)
- Nostr NIP-32: Standard for "Labeling" entities.
    - (https://nips.nostr.com/32)



UI
- Force Graph https://github.com/vasturiano/force-graph
    - Force-directed graph rendered on HTML5 canvas.
