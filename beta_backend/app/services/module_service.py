from fastapi import HTTPException

from app.feature_flags import FeatureFlagStore
from app.module_registry import MODULES


class ModuleService:
    def __init__(self, flag_store: FeatureFlagStore) -> None:
        self.flag_store = flag_store

    def capabilities(self) -> dict:
        flags = self.flag_store.all()
        return {
            "modules": [
                {
                    "key": module.key,
                    "name": module.name,
                    "version": module.release,
                    "release": module.release,
                    "description": module.description,
                    "enabled": flags[module.key],
                    "routes": module.routes,
                    "events": module.events,
                    "features": module.features,
                    "blocking": module.blocking,
                    "lookalike": module.key == "identity" and flags[module.key],
                }
                for module in MODULES.values()
            ],
            "runtime_overrides": self.flag_store.runtime_overrides(),
            "core_flow": {
                "non_blocking_modules": ["identity", "companion", "mind", "astro"],
                "required_steps": [
                    "radar-start",
                    "meeting-start",
                    "navigation-start",
                    "checkin-a-b",
                    "ok-a-b",
                    "chat-unlock",
                    "chat-send",
                    "panic-abort",
                ],
            },
        }

    def set_runtime_flag(self, module_key: str, enabled: bool) -> dict:
        try:
            flags = self.flag_store.set_runtime(module_key, enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown module") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "flags": flags}

    def require_enabled(self, module_key: str) -> None:
        if not self.flag_store.get(module_key):
            raise HTTPException(status_code=403, detail=f"Module '{module_key}' is disabled")
