# Catch Your Partner Roadmap

## Product Shape

This product should ship as a modular app with sequential releases. The architecture must support all modules from day one, while only `Core` carries production logic in the first release. Every optional module must degrade gracefully and must never block the core meeting flow.

## Release Plan

### v1.0 Core
- Scope: Radar -> Meeting -> Navigation -> Check-in -> OK -> Chat unlock -> Safety
- Backend: stable core endpoints, session state, chat unlock rules, panic flow, capabilities endpoint
- Frontend: core route, flow console, capabilities view
- Module rule: all non-core modules are optional and non-blocking

Definition of Done:
- `Core` can be enabled and used independently
- A user can complete the end-to-end core flow without Identity, Companion, Mind or Astro
- Capabilities endpoint reports active modules and routes correctly
- Runtime feature flags can enable or disable non-core modules without restart
- Safety panic flow works at any step and does not depend on other modules

### v1.1 Identity
- Scope: face verification, paid doppelgaenger check, Stripe integration
- Backend: replace placeholder verification and checkout with real providers
- Frontend: identity route with verification flow and purchase entry
- Module rule: failures fall back to optional status; core flow continues

Definition of Done:
- Face verification can be requested and persisted
- Stripe checkout or billing placeholder is replaced with a real payment session
- Identity module can be disabled without affecting core sessions
- Error handling is isolated so verification outages do not block meetings

### v1.2 Companion
- Scope: 3D Tamagotchi companion, rewards, levels, progression hooks
- Backend: progression state, reward grants from core milestones
- Frontend: companion route with 3D placeholder upgraded to interactive state
- Module rule: companion reads core events and reacts asynchronously

Definition of Done:
- Companion profile persists level, XP and reward inventory
- Core events can award rewards without delaying user actions
- Companion module can be fully disabled with no regression in core flow
- Placeholder screen is replaced by interactive companion UI

### v1.3 Mind
- Scope: psychology layer, meeting coaching, behavior insights
- Backend: profile traits, consent-safe insight generation, recommendation hooks
- Frontend: mind route with profile and insight screens
- Module rule: insights are additive and never gate chat or safety

Definition of Done:
- Psychology profile data is stored behind explicit opt-in
- Mind insights are generated without changing core success criteria
- Mind module can be turned off cleanly via flags
- Frontend exposes mind screens only when capability is active

### v1.3 Astro
- Scope: astrology layer, compatibility overlays, optional prompts
- Backend: sign storage, compatibility calculation, event hooks
- Frontend: astro route with compatibility placeholder upgraded to live data
- Module rule: astro scoring can enrich UI but cannot alter core availability

Definition of Done:
- Astro data is optional and editable
- Compatibility output is available through dedicated astro endpoints
- Astro flags can be toggled independently from Mind
- Core module behavior is identical whether Astro is enabled or disabled

## Architecture Rules

- `Core` is the only required module.
- Each module has its own routes, capability metadata and event contract.
- Optional modules subscribe to core events but must fail silently from the core perspective.
- Feature flags support both environment defaults and runtime overrides.
- The frontend must always ask the backend for capabilities before showing module entry points.

## Immediate Next Steps

- Replace legacy compatibility endpoints with explicit client usage of the new core routes
- Persist runtime flags and sessions beyond in-memory storage
- Add automated tests for capability combinations
- Move each module into its own router package when the codebase grows past prototype size
