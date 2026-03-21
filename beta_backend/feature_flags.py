from __future__ import annotations

import os
from typing import Dict


MODULE_KEYS = ("core", "identity", "companion", "mind", "astro")


def _env_name(module_key: str) -> str:
    return f"FEATURE_{module_key.upper()}_ENABLED"


def _env_flag(module_key: str, default: bool) -> bool:
    raw = os.getenv(_env_name(module_key))
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class FeatureFlagStore:
    def __init__(self) -> None:
        self._runtime_overrides: Dict[str, bool] = {}
        self._defaults: Dict[str, bool] = {
            "core": True,
            "identity": False,
            "companion": False,
            "mind": False,
            "astro": False,
        }

    def get(self, module_key: str) -> bool:
        if module_key in self._runtime_overrides:
            return self._runtime_overrides[module_key]
        return _env_flag(module_key, self._defaults[module_key])

    def all(self) -> Dict[str, bool]:
        return {module_key: self.get(module_key) for module_key in MODULE_KEYS}

    def set_runtime(self, module_key: str, enabled: bool) -> Dict[str, bool]:
        if module_key not in MODULE_KEYS:
            raise KeyError(module_key)
        if module_key == "core" and not enabled:
            raise ValueError("core module cannot be disabled")
        self._runtime_overrides[module_key] = enabled
        return self.all()

    def runtime_overrides(self) -> Dict[str, bool]:
        return dict(self._runtime_overrides)
