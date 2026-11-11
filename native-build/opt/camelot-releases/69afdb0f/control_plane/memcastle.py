#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""MemCastle — local vector fortress for Camelot-OS (the edge brain, Tier 2).

A real, dependency-light vector store backed by SQLite + sqlite-vec (vec0).
Stores text + embeddings + metadata locally so the Empire still has a queryable
knowledge graph when the cloud (NotebookLM) is unreachable.

Storage:  03_VAULT/memory/memcastle.db (override via MEMCASTLE_DB).
Vectors:  vec0 virtual table (sqlite-vec KNN); payload in a companion table.

The embedder here is a deterministic, dependency-free hashing embedder — good
enough to exercise KNN end-to-end. Swap `hash_embed` for a real model (ONNX
MiniLM, sentence-transformers, or the NotebookLM embedding API) by passing your
own vectors to `store`/`search`; the storage layer is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import sqlite3
import struct
import time
from pathlib import Path
from typing import Optional

try:
    import sqlite_vec
except ImportError as e:  # pragma: no cover
    raise SystemExit("MemCastle requires sqlite-vec: pip install sqlite-vec") from e

DEFAULT_DIM = 256
DEFAULT_DB = Path(
    os.environ.get(
        "MEMCASTLE_DB",
        str(Path(__file__).resolve().parent.parent / "03_VAULT" / "memory" / "memcastle.db"),
    )
)


def hash_embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    """Deterministic char-3gram hashing embedder (placeholder, no deps).

    Real semantic search should replace this with a learned model; the vector
    contract (a list[float] of length `dim`, L2-normalized) stays the same.
    """
    vec = [0.0] * dim
    t = f"  {text.lower().strip()}  "
    for i in range(len(t) - 2):
        gram = t[i : i + 3]
        h = int.from_bytes(hashlib.blake2b(gram.encode(), digest_size=8).digest(), "little")
        bucket = h % dim
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[bucket] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _serialize(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


class MemCastle:
    def __init__(self, db_path: Path = DEFAULT_DB, dim: int = DEFAULT_DIM):
        self.dim = dim
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False lets the connection back a single-threaded HTTP
        # service (cognitive_service) whose handler runs in a different thread than
        # construction. Requests are serialized, so there is no concurrent access.
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.execute(
            f"create virtual table if not exists mc_vectors using vec0(embedding float[{self.dim}])"
        )
        self.db.execute(
            """create table if not exists mc_items(
                   id integer primary key,
                   text text not null,
                   source text,
                   knight text,
                   ts text not null
               )"""
        )
        self.db.commit()

    def store(
        self,
        text: str,
        embedding: Optional[list[float]] = None,
        source: Optional[str] = None,
        knight: Optional[str] = None,
    ) -> int:
        if embedding is None:
            embedding = hash_embed(text, self.dim)
        if len(embedding) != self.dim:
            raise ValueError(f"embedding dim {len(embedding)} != {self.dim}")
        cur = self.db.execute(
            "insert into mc_items(text, source, knight, ts) values (?,?,?,?)",
            (text, source, knight, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        rowid = cur.lastrowid
        self.db.execute(
            "insert into mc_vectors(rowid, embedding) values (?, ?)",
            (rowid, _serialize(embedding)),
        )
        self.db.commit()
        return rowid

    def search(self, query: str, k: int = 5, embedding: Optional[list[float]] = None) -> list[dict]:
        if embedding is None:
            embedding = hash_embed(query, self.dim)
        rows = self.db.execute(
            """select v.rowid, v.distance, i.text, i.source, i.knight, i.ts
                 from mc_vectors v join mc_items i on i.id = v.rowid
                where v.embedding match ? and k = ?
                order by v.distance""",
            (_serialize(embedding), k),
        ).fetchall()
        return [
            {"id": r[0], "distance": r[1], "text": r[2], "source": r[3], "knight": r[4], "ts": r[5]}
            for r in rows
        ]

    def count(self) -> int:
        return self.db.execute("select count(*) from mc_items").fetchone()[0]

    def recent(self, limit: int = 200) -> list[dict]:
        """Most-recent items, newest first — used to build the NotebookLM push snapshot."""
        rows = self.db.execute(
            "select id, text, source, knight, ts from mc_items order by id desc limit ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "text": r[1], "source": r[2], "knight": r[3], "ts": r[4]} for r in rows
        ]

    def close(self) -> None:
        self.db.close()


def _cli() -> None:
    p = argparse.ArgumentParser(description="MemCastle — local sqlite-vec vector store")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("store", help="store text")
    s.add_argument("text")
    s.add_argument("--source")
    s.add_argument("--knight")
    q = sub.add_parser("search", help="KNN search")
    q.add_argument("query")
    q.add_argument("-k", type=int, default=5)
    sub.add_parser("stats", help="row count + db path")
    args = p.parse_args()

    mc = MemCastle()
    if args.cmd == "store":
        rid = mc.store(args.text, source=args.source, knight=args.knight)
        print(f"stored id={rid} (total={mc.count()})")
    elif args.cmd == "search":
        for r in mc.search(args.query, k=args.k):
            print(f"  [{r['distance']:.4f}] #{r['id']} {r['text'][:80]}  ({r['source'] or '-'})")
    elif args.cmd == "stats":
        print(f"db={mc.db_path}  items={mc.count()}  dim={mc.dim}")
    mc.close()


if __name__ == "__main__":
    _cli()
