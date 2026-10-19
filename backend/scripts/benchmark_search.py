"""Bounded synthetic search benchmark. Never touches an investigator database."""
import argparse
import json
import platform
import random
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.services.event_search_service import EventSearchService, SearchError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--output", type=Path, default=Path("../docs/validation/search-benchmark.json"))
    args = parser.parse_args()
    rng = random.Random(18026)
    with tempfile.TemporaryDirectory() as folder:
        engine = create_engine(f"sqlite:///{folder}/benchmark.sqlite")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Case(id=1, title="Generated synthetic load case"))
            db.add(Evidence(id=1, case_id=1, filename="synthetic.csv", sha256="a"*64, md5="b"*32, size_bytes=0, storage_path="synthetic-only"))
            db.flush()
            for start in range(0, args.rows, 5000):
                db.execute(Event.__table__.insert(), [{"case_id": 1, "evidence_id": 1, "source_type": "generated", "event_type": "transaction" if i % 10 == 0 else "message", "content": f"{'refund' if i % 1000 == 0 else 'payment'} synthetic case {rng.randrange(240)} record {i}", "raw_ref": f"row:{i+1}", "timestamp_utc": datetime(2026, 9, 1, tzinfo=UTC) + timedelta(seconds=i)} for i in range(start, min(start+5000, args.rows))])
            db.commit()
            index_started = time.perf_counter()
            EventSearchService(db)._ensure_index(1, budget=60)
            db.commit()
            index_ms = round((time.perf_counter()-index_started)*1000, 2)
            results = []
            for spec in [{"q": "refund"}, {"facets": {"type": "payment"}}, {}]:
                started = time.perf_counter()
                try:
                    result = EventSearchService(db).search(1, {**spec, "page": {"limit": 100}})
                    outcome = {"matching": result["total_matching"], "histogram_buckets": len(result["histogram"]), "status": "completed"}
                except SearchError as exc:
                    outcome = {"status": "time_limit", "reason": str(exc)}
                results.append({"query": spec, "milliseconds": round((time.perf_counter()-started)*1000, 2), **outcome})
            explain = db.execute(text("EXPLAIN QUERY PLAN SELECT id FROM events WHERE case_id=1 AND event_type='transaction' ORDER BY timestamp_utc")).all()
            report = {"label": "on synthetic data", "rows": args.rows, "seed": 18026, "version": "2.0", "index_build_milliseconds": index_ms, "python": platform.python_version(), "platform": platform.platform(), "time_limit_seconds": 60, "assumptions": "Single process, local SQLite, separately measured index build; warm SQL aggregates; no production latency claim", "results": results, "explain": [str(row) for row in explain], "fallback": "Narrow filters if the time guard triggers; no invented results"}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
