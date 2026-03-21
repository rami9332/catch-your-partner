from fastapi import APIRouter, Depends, Request

from app.dependencies import require_admin
from app.models.schemas import RuntimeFlagRequest

router = APIRouter(tags=["modules"])


@router.get("/capabilities")
def capabilities(request: Request):
    return request.app.state.module_service.capabilities()


@router.post("/admin/runtime-flags")
def set_runtime_flag(payload: RuntimeFlagRequest, request: Request, admin=Depends(require_admin)):
    return request.app.state.module_service.set_runtime_flag(payload.module_key, payload.enabled)

@router.get("/mind/profile")
def mind_status(request: Request):
    request.app.state.module_service.require_enabled("mind")
    return {"module": "mind", "status": "placeholder", "message": "Mind stub remains non-blocking in phase 2."}


@router.get("/astro/profile")
def astro_status(request: Request):
    request.app.state.module_service.require_enabled("astro")
    return {"module": "astro", "status": "placeholder", "message": "Astro stub remains non-blocking in phase 2."}
