from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import ping_db
from app.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    ping_db(db)
    return {
        "status": "ok",
        "app": request.app.state.settings.app_name,
        "environment": request.app.state.settings.environment,
        "database": "ok",
    }

