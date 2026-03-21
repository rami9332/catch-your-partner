from app.config import Settings
from app.module_registry import MODULES


class FeatureFlagStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._runtime_overrides: dict[str, bool] = {}
        self._defaults = {
            "core": settings.feature_core_enabled,
            "identity": settings.feature_identity_enabled,
            "companion": settings.feature_companion_enabled,
            "mind": settings.feature_mind_enabled,
            "astro": settings.feature_astro_enabled,
        }

    def get(self, module_key: str) -> bool:
        if module_key in self._runtime_overrides:
            return self._runtime_overrides[module_key]
        return self._defaults[module_key]

    def all(self) -> dict[str, bool]:
        return {key: self.get(key) for key in MODULES}

    def set_runtime(self, module_key: str, enabled: bool) -> dict[str, bool]:
        if module_key not in MODULES:
            raise KeyError(module_key)
        if module_key == "core" and not enabled:
            raise ValueError("core module cannot be disabled")
        self._runtime_overrides[module_key] = enabled
        return self.all()

    def runtime_overrides(self) -> dict[str, bool]:
        return dict(self._runtime_overrides)

