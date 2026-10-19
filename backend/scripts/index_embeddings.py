"""Explicit bounded offline index build; resumes content-hashed batches."""
import argparse
import json

import numpy as np
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.evidence import Event
from app.services.embedding_service import CACHE, rank_documents
from app.services.event_search_service import EventSearchService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=300)
    args = parser.parse_args()
    with SessionLocal() as db:
        EventSearchService(db)._ensure_index(args.case_id, budget=60)
        documents = [(event.id, event.content + " " + " ".join(event.actor_entities or [])) for event in db.scalars(select(Event).where(Event.case_id == args.case_id).order_by(Event.id))]
        _, status = rank_documents(args.case_id, documents, "index", budget=args.seconds)
        if not status.get("complete"):
            print(json.dumps(status))
            db.commit()
            return
        model_hash = status["model_card"]["artifact_sha256"] + "-single-v2"
        root = CACHE / str(args.case_id) / model_hash
        import hashlib
        paths = [root / f"{identifier}-{hashlib.sha256(value.encode()).hexdigest()}.npy" for identifier, value in documents]
        matrix = np.stack([np.load(path, allow_pickle=False) for path in paths])
        np.save(root / "matrix.npy", matrix, allow_pickle=False)
        manifest = {"event_ids": [identifier for identifier, _ in documents], "matrix_file": "matrix.npy", "model_sha256": model_hash, "settings": status}
        (root / "index.json").write_text(json.dumps(manifest))
        db.commit()
        print(json.dumps({"status": "complete", "rows": len(documents), "seed": 51026, "model_sha256": model_hash}))


if __name__ == "__main__":
    main()
