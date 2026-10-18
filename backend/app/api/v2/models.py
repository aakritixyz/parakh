from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ml import ModelRecord
from app.models.user import User

router = APIRouter(tags=["v2 model registry"])


@router.get("/models")
def model_cards(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return [
        {
            "id": item.id,
            "name": item.name,
            "version": item.version,
            "licence": item.licence,
            "training_data": item.training_data,
            "known_limits": item.known_limits,
            "metrics": item.metrics,
            "explanations": item.explanations,
            "artifact_sha256": item.artifact_sha256,
            "evaluation_label": item.evaluation_label,
            "seed": item.seed,
            "offline_only": item.offline_only,
        }
        for item in db.scalars(select(ModelRecord).order_by(ModelRecord.name, ModelRecord.version))
    ]
