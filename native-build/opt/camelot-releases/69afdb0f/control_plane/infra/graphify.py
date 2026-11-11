#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Graphify — the butcher: unstructured text -> (subject, predicate, object)
triplets, fed into MemCastle (the vault).

This is the missing Tier-2 feeder: the existing titan/graph KnowledgeGraphEngine
extracts only *code* entities (def/class regex); general prose triplets had no
extractor. Graphify provides a real, deterministic, dependency-free NL extractor
and stores each triplet in MemCastle (sqlite-vec) for semantic recall.

The extractor is pluggable: pass `extractor=` your own callable (e.g. an LLM via
the bifrost provider matrix, or spaCy dependency parse) for higher recall; the
storage/query pipeline is unchanged. The default rule-based extractor needs no
models and is fully tested.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# MemCastle lives beside this file; make it importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from memcastle import MemCastle  # noqa: E402


@dataclass(frozen=True)
class Triplet:
    """(head, relation, tail) — compatible with titan/graph/knowledge_graph.Triplet."""

    head: str
    relation: str
    tail: str

    def __str__(self) -> str:
        return f"({self.head}) --[{self.relation}]--> ({self.tail})"


# Relation verbs Graphify recognizes as predicates (lemma-ish; both tenses).
_RELATION_VERBS = {
    "uses", "use", "used", "calls", "call", "called", "fixes", "fix", "fixed",
    "causes", "cause", "caused", "replaces", "replace", "replaced", "requires",
    "require", "required", "connects", "connect", "connected", "sends", "send",
    "receives", "receive", "stores", "store", "stored", "extracts", "extract",
    "exposes", "expose", "exposed", "wires", "wire", "wired", "runs", "run",
    "serves", "serve", "served", "supports", "support", "contains", "contain",
    "includes", "include", "produces", "produce", "generates", "generate",
    "manages", "manage", "monitors", "monitor", "powers", "power", "drives",
    "drive", "feeds", "feed", "routes", "route", "handles", "handle",
    "depends", "supersedes", "implements", "implement", "validates", "validate",
    "restart", "restarts", "restarted", "executes", "execute", "executed",
}


def _lemma(verb: str) -> str:
    """Best-effort verb lemma. Prefers a known base in the lexicon, else applies
    English orthographic de-inflection (uses->use, fixes->fix, restarts->restart)."""
    if verb.endswith("s") and not verb.endswith("ss"):
        if verb[:-1] in _RELATION_VERBS:          # uses->use, wires->wire
            return verb[:-1]
        if verb.endswith("es") and verb[:-2] in _RELATION_VERBS:  # fixes->fix
            return verb[:-2]
        if verb.endswith("es") and len(verb) > 3 and verb[-3] in "sxzo":
            return verb[:-2]                       # fixes->fix, goes->go
        return verb[:-1]                           # restarts->restart, runs->run
    return verb
_COPULA = {"is", "are", "was", "were", "be"}
_HAVE = {"has", "have", "had"}
_EDGE_STOP = {"a", "an", "the", "this", "that", "these", "those", "its", "their"}
_LEAD_PREP = {"on", "to", "with", "from", "of", "into", "for", "at", "as", "by"}


def _sentences(text: str) -> list[str]:
    # Split on sentence terminators and newlines/semicolons; drop empties.
    parts = re.split(r"(?<=[.!?])\s+|\n+|;\s*", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _clean_np(tokens: list[str], strip_lead_prep: bool = False) -> str:
    words = [w.strip(",.;:!?()[]\"'`") for w in tokens]
    words = [w for w in words if w]
    if strip_lead_prep:
        while words and words[0].lower() in _LEAD_PREP:
            words = words[1:]
    while words and words[0].lower() in _EDGE_STOP:
        words = words[1:]
    while words and words[-1].lower() in _EDGE_STOP | _LEAD_PREP:
        words = words[:-1]
    return " ".join(words)


def extract_triplets(text: str) -> list[Triplet]:
    """Deterministic SVO/relation triplet extraction. No models, no network."""
    triplets: list[Triplet] = []
    for sent in _sentences(text):
        toks = sent.split()
        if len(toks) < 3:
            continue
        # Find the first predicate token (copula > have > relation verb).
        verb_idx, fallback_idx = -1, -1
        for i in range(1, len(toks) - 1):  # need a subject before, object after
            low = toks[i].strip(",.;:!?").lower()
            if low in _COPULA or low in _HAVE or low in _RELATION_VERBS:
                verb_idx = i
                break
            # past-tense / gerund tokens are almost never plural nouns -> safe
            # generic-verb fallback for open-domain recall.
            if fallback_idx == -1 and re.fullmatch(r"[a-z]+(ed|ing)", low):
                fallback_idx = i
        if verb_idx == -1:
            verb_idx = fallback_idx
        if verb_idx == -1:
            continue
        verb = toks[verb_idx].strip(",.;:!?").lower()
        head = _clean_np(toks[:verb_idx])
        tail = _clean_np(toks[verb_idx + 1 :], strip_lead_prep=True)
        if not head or not tail:
            continue
        if verb in _COPULA:
            relation = "is_a"
        elif verb in _HAVE:
            relation = "has"
        elif verb == "depends":
            relation = "depends_on"
        else:
            relation = _lemma(verb)
        triplets.append(Triplet(head=head, relation=relation, tail=tail))
    return triplets


class Graphify:
    """Pipeline: text -> triplets -> MemCastle vault."""

    def __init__(
        self,
        memcastle: Optional[MemCastle] = None,
        extractor: Callable[[str], list[Triplet]] = extract_triplets,
    ):
        self.mc = memcastle or MemCastle()
        self.extract = extractor

    def ingest(self, text: str, source: Optional[str] = None, knight: Optional[str] = None) -> list[Triplet]:
        triplets = self.extract(text)
        for t in triplets:
            # Store the triplet as a searchable sentence; metadata keeps the parts.
            repr_text = f"{t.head} {t.relation} {t.tail}"
            self.mc.store(repr_text, source=source or "graphify", knight=knight)
        return triplets

    def query(self, question: str, k: int = 5) -> list[dict]:
        return self.mc.search(question, k=k)

    def close(self) -> None:
        self.mc.close()


def _cli() -> None:
    p = argparse.ArgumentParser(description="Graphify — text -> triplets -> MemCastle")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="extract triplets (no storage)")
    e.add_argument("text")
    g = sub.add_parser("ingest", help="extract + store into MemCastle")
    g.add_argument("text")
    g.add_argument("--source")
    q = sub.add_parser("query", help="semantic search stored triplets")
    q.add_argument("question")
    q.add_argument("-k", type=int, default=5)
    args = p.parse_args()

    if args.cmd == "extract":
        for t in extract_triplets(args.text):
            print(" ", t)
        return

    gf = Graphify()
    if args.cmd == "ingest":
        ts = gf.ingest(args.text, source=args.source)
        print(f"ingested {len(ts)} triplets (vault total={gf.mc.count()})")
        for t in ts:
            print("  ", t)
    elif args.cmd == "query":
        for r in gf.query(args.question, k=args.k):
            print(f"  [{r['distance']:.4f}] {r['text']}  ({r['source'] or '-'})")
    gf.close()


if __name__ == "__main__":
    _cli()
