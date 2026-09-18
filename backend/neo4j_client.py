"""
Neo4j client for the literature survey app.

Schema (kept deliberately simple):
  (:Paper {id, module, title, year, venue, dataset, model, objective,
           best_performance, strengths, weaknesses, research_gap,
           relevant, link, taxonomy, evaluation_metrics,
           hardware_constraint, created_at})
  (:Comment {id, author, text, created_at})-[:ON]->(:Paper)

There are no pre-materialized relationship edges between papers.
The relationship graph shown in the UI (same module / shared
taxonomy keywords) is computed at READ time in get_graph_data(),
so it is always in sync with the current data -- no stale edges to
maintain when a paper is edited or deleted.
"""

import os
import uuid
import time
from itertools import combinations
from neo4j import GraphDatabase

NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://9c83da30.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "9c83da30")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "aopry7LR5QJpEM5cyYr3wVGa3tLVovoZ5P5Yz5dxMqI")

_driver = None


def get_driver():
    """Lazily create a single shared driver instance."""
    global _driver
    if _driver is None:
        if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
            raise RuntimeError(
                "Neo4j credentials missing. Set NEO4J_URI, NEO4J_USER, "
                "NEO4J_PASSWORD (see .env.example)."
            )
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def verify_connectivity():
    get_driver().verify_connectivity()


PAPER_FIELDS = [
    "module", "title", "year", "venue", "dataset", "model", "objective",
    "best_performance", "strengths", "weaknesses", "research_gap",
    "relevant", "link", "taxonomy", "evaluation_metrics",
    "hardware_constraint",
]


def create_paper(fields: dict) -> dict:
    """Create a new Paper node. `fields` should contain keys from
    PAPER_FIELDS; missing keys default to an empty string / sensible type."""
    paper_id = "P-" + uuid.uuid4().hex[:8]
    data = {"id": paper_id, "created_at": time.time()}
    for f in PAPER_FIELDS:
        data[f] = fields.get(f, "")
    if not isinstance(data.get("year"), int):
        try:
            data["year"] = int(data["year"])
        except (TypeError, ValueError):
            data["year"] = 0
    if not isinstance(data.get("relevant"), bool):
        data["relevant"] = str(data.get("relevant", "")).strip().lower() in (
            "y", "yes", "true", "1",
        )

    query = """
    CREATE (p:Paper $data)
    RETURN p
    """
    with get_driver().session() as session:
        result = session.run(query, data=data)
        record = result.single()
        return dict(record["p"])


def update_paper(paper_id: str, fields: dict) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in PAPER_FIELDS}
    if not updates:
        return get_paper(paper_id)
    query = """
    MATCH (p:Paper {id: $id})
    SET p += $updates
    RETURN p
    """
    with get_driver().session() as session:
        result = session.run(query, id=paper_id, updates=updates)
        record = result.single()
        return dict(record["p"]) if record else None


def delete_paper(paper_id: str) -> bool:
    query = """
    MATCH (p:Paper {id: $id})
    OPTIONAL MATCH (c:Comment)-[:ON]->(p)
    DETACH DELETE p, c
    """
    with get_driver().session() as session:
        session.run(query, id=paper_id)
        return True


def get_paper(paper_id: str) -> dict | None:
    query = "MATCH (p:Paper {id: $id}) RETURN p"
    with get_driver().session() as session:
        result = session.run(query, id=paper_id)
        record = result.single()
        return dict(record["p"]) if record else None


def get_all_papers() -> list[dict]:
    query = "MATCH (p:Paper) RETURN p ORDER BY p.module ASC, p.year DESC"
    with get_driver().session() as session:
        result = session.run(query)
        return [dict(r["p"]) for r in result]


def _taxonomy_tokens(taxonomy: str) -> set[str]:
    if not taxonomy:
        return set()
    parts = taxonomy.replace(";", ",").split(",")
    return {p.strip().lower() for p in parts if p.strip()}


def get_graph_data() -> dict:
    """Compute nodes + edges fresh from the current papers every call,
    so the graph is always in sync with the table (no separate edge
    store to keep updated)."""
    papers = get_all_papers()
    nodes = [
        {
            "id": p["id"],
            "title": p.get("title", ""),
            "module": p.get("module", 0),
            "year": p.get("year", 0),
        }
        for p in papers
    ]

    edges = []
    for a, b in combinations(papers, 2):
        same_module = a.get("module") == b.get("module") and a.get("module")
        shared = _taxonomy_tokens(a.get("taxonomy", "")) & _taxonomy_tokens(
            b.get("taxonomy", "")
        )
        if shared:
            edges.append(
                {
                    "source": a["id"],
                    "target": b["id"],
                    "type": "topic",
                    "label": ", ".join(sorted(shared))[:60],
                }
            )
        elif same_module:
            edges.append({"source": a["id"], "target": b["id"], "type": "module"})

    return {"nodes": nodes, "edges": edges}


def add_comment(paper_id: str, author: str, text: str) -> dict | None:
    comment_id = "C-" + uuid.uuid4().hex[:8]
    query = """
    MATCH (p:Paper {id: $paper_id})
    CREATE (c:Comment {id: $id, author: $author, text: $text, created_at: $ts})
    CREATE (c)-[:ON]->(p)
    RETURN c
    """
    with get_driver().session() as session:
        result = session.run(
            query,
            paper_id=paper_id,
            id=comment_id,
            author=author or "Anonymous",
            text=text,
            ts=time.time(),
        )
        record = result.single()
        return dict(record["c"]) if record else None


def get_comments(paper_id: str) -> list[dict]:
    query = """
    MATCH (c:Comment)-[:ON]->(p:Paper {id: $paper_id})
    RETURN c ORDER BY c.created_at ASC
    """
    with get_driver().session() as session:
        result = session.run(query, paper_id=paper_id)
        return [dict(r["c"]) for r in result]
