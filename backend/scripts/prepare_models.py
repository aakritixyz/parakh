"""Train synthetic aliases and register provisioned local cards (no network)."""
import json

from app.core.database import SessionLocal, engine
from app.core.migrations import require_current_schema
from app.services.alias_model_service import train_alias
from app.services.ml_foundation_service import register_model
from app.services.offline_models import ROOT, local_model


def main():
    require_current_schema(engine)
    cards = [train_alias()]
    for kind in ("embeddings", "entailment"):
        model = local_model(kind)
        card = dict(model.card, seed=51026, evaluation_label=model.card["metrics"].get("label", "Not evaluated"),
                    artifact_path=str(ROOT / kind / "onnx/model_quantized.onnx"), explanations={"tree": {"method": "Pretrained model; conservative validation or cosine relevance", "values": {}}, "top_words": []})
        cards.append(card)
    with SessionLocal() as db:
        for card in cards:
            register_model(db, card)
    print(json.dumps([{key: card[key] for key in ("name", "version", "metrics")} for card in cards], indent=2))


if __name__ == "__main__":
    main()
