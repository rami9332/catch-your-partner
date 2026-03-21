from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    name: str
    release: str
    description: str
    routes: list[str]
    events: list[str]
    features: list[str]
    blocking: bool = False


MODULES: dict[str, ModuleDefinition] = {
    "core": ModuleDefinition(
        key="core",
        name="Core",
        release="v1.0",
        description="Radar, meeting, navigation, check-in, OK, chat unlock and safety.",
        routes=[
            "/core/radar/start",
            "/core/radar/stop",
            "/core/radar",
            "/core/meeting/start",
            "/core/navigation/start",
            "/core/check-in",
            "/core/ok",
            "/core/chat/unlock",
            "/core/chat/send",
            "/core/chat/history/{meeting_id}",
            "/core/safety/panic",
            "/core/safety/abort",
        ],
        events=[
            "core.radar.started",
            "core.meeting.created",
            "core.navigation.started",
            "core.checkin.completed",
            "core.ok.completed",
            "core.chat.unlocked",
            "core.safety.triggered",
        ],
        features=["radar", "meeting", "navigation", "safety"],
    ),
    "identity": ModuleDefinition(
        key="identity",
        name="Identity",
        release="v1.1",
        description="Face enrollment, verification and anti-fake checks.",
        routes=["/identity/status", "/identity/enroll", "/identity/verify", "/identity/profile", "/identity/lookalike/status", "/identity/lookalike/search"],
        events=["identity.enrolled", "identity.verified", "identity.lookalike.searched"],
        features=["verification", "anti_fake", "lookalike"],
    ),
    "companion": ModuleDefinition(
        key="companion",
        name="Companion",
        release="v1.2",
        description="3D Tamagotchi, rewards and levels.",
        routes=["/companion/state", "/companion/event", "/companion/say", "/companion/tamagotchi"],
        events=["companion.event.recorded"],
        features=["rewards", "levels", "coach"],
    ),
    "mind": ModuleDefinition(
        key="mind",
        name="Mind",
        release="v1.3",
        description="Psychology layer and behavior insights.",
        routes=["/mind/profile"],
        events=["mind.profile.viewed"],
        features=["psychology"],
    ),
    "astro": ModuleDefinition(
        key="astro",
        name="Astro",
        release="v1.3",
        description="Astrology compatibility overlay.",
        routes=["/astro/profile"],
        events=["astro.profile.viewed"],
        features=["astrology"],
    ),
}
