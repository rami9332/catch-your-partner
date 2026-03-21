from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    name: str
    release: str
    description: str
    depends_on: List[str]
    routes: List[str]
    events: List[str]
    blocking: bool = False


MODULES: Dict[str, ModuleDefinition] = {
    "core": ModuleDefinition(
        key="core",
        name="Core",
        release="v1.0",
        description="Radar, meeting, navigation, check-in, OK flow, chat unlock and safety.",
        depends_on=[],
        routes=[
            "/capabilities",
            "/core/radar",
            "/core/meeting/start",
            "/core/navigation/start",
            "/core/check-in",
            "/core/ok",
            "/core/chat/unlock",
            "/core/chat/send",
            "/core/chat/history",
            "/core/safety/panic",
        ],
        events=[
            "core.user.ready",
            "core.radar.pulled",
            "core.meeting.created",
            "core.navigation.started",
            "core.checkin.completed",
            "core.ok.completed",
            "core.chat.unlocked",
            "core.safety.triggered",
        ],
    ),
    "identity": ModuleDefinition(
        key="identity",
        name="Identity",
        release="v1.1",
        description="Face verification and paid doppelgaenger checks.",
        depends_on=["core"],
        routes=["/identity/face/verify", "/identity/doppelgaenger/checkout"],
        events=["identity.face.requested", "identity.doppelgaenger.checkout.requested"],
    ),
    "companion": ModuleDefinition(
        key="companion",
        name="Companion",
        release="v1.2",
        description="3D companion, rewards and levels.",
        depends_on=["core"],
        routes=["/companion/tamagotchi", "/companion/rewards"],
        events=["companion.companion.viewed", "companion.rewards.viewed"],
    ),
    "mind": ModuleDefinition(
        key="mind",
        name="Mind",
        release="v1.3",
        description="Psychology layer and behavior insights.",
        depends_on=["core"],
        routes=["/mind/profile", "/mind/insights"],
        events=["mind.profile.viewed", "mind.insights.viewed"],
    ),
    "astro": ModuleDefinition(
        key="astro",
        name="Astro",
        release="v1.3",
        description="Astrology compatibility layer.",
        depends_on=["core"],
        routes=["/astro/profile", "/astro/compatibility"],
        events=["astro.profile.viewed", "astro.compatibility.viewed"],
    ),
}


def module_capability_payload(key: str, enabled: bool) -> dict:
    module = MODULES[key]
    return {
        "key": module.key,
        "name": module.name,
        "release": module.release,
        "description": module.description,
        "enabled": enabled,
        "depends_on": module.depends_on,
        "routes": module.routes,
        "events": module.events,
        "blocking": module.blocking,
    }
