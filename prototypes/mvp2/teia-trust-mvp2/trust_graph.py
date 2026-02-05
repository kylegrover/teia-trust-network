"""Lightweight TrustGraph implementation — rustworkx-compatible API with a NetworkX fallback.
- Optional backend: 'rustworkx' (if installed) or 'networkx' (default).
- Async loader from the index DB (re-uses existing get_index_conn), and a sync constructor for tests.
- No Redis/caching here — parity with your requested prototype.
"""
from __future__ import annotations

import math
import os
from typing import Dict, Iterable, List, Mapping, Optional

try:
    import rustworkx as rx
    _HAS_RX = True
except Exception:
    rx = None
    _HAS_RX = False

from database import get_index_conn

EdgeRow = Mapping[str, object]


class TrustGraph:
    """Rustworkx-only TrustGraph.

    This project uses rustworkx as the single graph backend. The constructor
    will raise a helpful error if rustworkx is not installed.
    """

    def __init__(self, backend: Optional[str] = None) -> None:
        # backend parameter exists for API parity but only 'rustworkx' is supported
        if not _HAS_RX:
            raise RuntimeError(
                "rustworkx is required for TrustGraph — install with: uv add rustworkx==0.17.1 && uv sync"
            )

        self.graph = rx.PyDiGraph()
        self.node_map: Dict[int, int] = {}
        self.rev_node_map: Dict[int, int] = {}
        self._nodes_loaded = False

    # ------------------------ loaders ------------------------
    async def load_from_index_db(self) -> None:
        """Async loader that reads from the `trust_connections` view in the index DB.

        Be tolerant of view column-name variations (`total_mutez` vs `total_volume_mutez`) so
        the indexer and engine can be rolled out independently.
        """
        async with get_index_conn() as conn:
            # check whether `total_mutez` exists in the view to avoid UndefinedColumnError
            has_total = await conn.fetchval(
                """
                SELECT EXISTS(
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema = current_schema()
                    AND table_name = 'trust_connections'
                    AND column_name = 'total_mutez'
                )
                """
            )

            if has_total:
                rows = await conn.fetch("SELECT source_id, target_id, trade_count, total_mutez FROM trust_connections")
            else:
                # fall back to the legacy column name (if present)
                rows = await conn.fetch("SELECT source_id, target_id, trade_count, total_volume_mutez AS total_mutez FROM trust_connections")

        edges = [dict(r) for r in rows]
        self.build_from_edges(edges)

    def build_from_edges(self, edges: Iterable[EdgeRow]) -> None:
        """Build internal graph from an iterable of rows with keys:
        `source_id`, `target_id`, `trade_count` (optional), `total_mutez` (optional).
        This method is sync to make testing easy.
        """
        edges = list(edges)
        if not edges:
            self.graph = rx.PyDiGraph() if self._use_rx else nx.DiGraph()
            self.node_map = {}
            self.rev_node_map = {}
            self._nodes_loaded = False
            return

        unique_nodes = {int(e["source_id"]) for e in edges} | {int(e["target_id"]) for e in edges}
        node_list = list(unique_nodes)
        self.node_map = {uid: idx for idx, uid in enumerate(node_list)}
        self.rev_node_map = {idx: uid for uid, idx in self.node_map.items()}

        # rustworkx path (only path supported)
        self.graph = rx.PyDiGraph()
        self.graph.add_nodes_from(list(range(len(node_list))))

        # prepare weighted edge list in rustworkx-friendly form: (u_idx, v_idx, weight)
        rx_edges = []
        for e in edges:
            u = self.node_map[int(e["source_id"])]
            v = self.node_map[int(e["target_id"])]
            trade_count = float(e.get("trade_count") or 0.0)
            total_mutez = float(e.get("total_mutez") or 0.0)

            tez_weight = math.log1p(total_mutez / 1_000_000.0) if total_mutez > 0 else 0.0
            weight = (1.0 + math.log1p(trade_count)) * (1.0 + 0.5 * tez_weight)
            rx_edges.append((u, v, weight))

        # bulk-add (creates nodes if missing and is fastest)
        self.graph.extend_from_weighted_edge_list(rx_edges)

        self._nodes_loaded = True

    # ------------------------ algorithms ------------------------
    def compute_global_pagerank(self, alpha: float = 0.85) -> Dict[int, float]:
        """Return raw PageRank mapping (node_index -> score).

        The returned dict keys are rustworkx node indices — caller should map
        back to DB ids using `rev_node_map`.
        """
        if not self._nodes_loaded:
            return {}

        scores = rx.pagerank(self.graph, alpha=alpha, weight_fn=lambda w: w)
        return {int(k): float(v) for k, v in scores.items()}
    def get_user_trust_vector(self, user_db_id: int, alpha: float = 0.85, min_score: float = 1e-5) -> Dict[int, float]:
        """Personalized PageRank seeded at `user_db_id`.
        Returns a mapping holder_id -> score (not normalized to 0-100).
        """
        if not self._nodes_loaded or user_db_id not in self.node_map:
            return {}

        seed_idx = self.node_map[user_db_id]

        # rustworkx PPR (personalization uses node-index)
        scores = rx.pagerank(self.graph, alpha=alpha, weight_fn=lambda w: w, personalization={seed_idx: 1.0})
        out = {self.rev_node_map[int(k)]: float(v) for k, v in scores.items() if float(v) >= min_score}
        return out


__all__ = ["TrustGraph"]
