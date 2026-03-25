# State Map

State is any variable that changes Abby’s behavior over time or context. This map is the index for state domains; detailed semantics live in the per‑domain docs.

## Domains (authoritative docs)

- Platform state: [PLATFORM_STATE.md](PLATFORM_STATE.md)
- Lifecycle state: [LIFECYCLE_STATE.md](LIFECYCLE_STATE.md)
- Gameplay state: [GAMEPLAY_STATE.md](GAMEPLAY_STATE.md)
- Configuration state: [CONFIGURATION_STATE.md](CONFIGURATION_STATE.md)
- Generation state: [GENERATION_STATE.md](GENERATION_STATE.md)

## Source of truth by domain

| Domain        | Source of truth                                    | Primary services                               |
| ------------- | -------------------------------------------------- | ---------------------------------------------- |
| Platform      | `system_state`, `system_state_instances`           | StateActivationService, StateValidationService |
| Lifecycle     | `content_delivery_items`, `content_delivery_dlq`   | AnnouncementDispatcher, DLQService             |
| Gameplay      | `game_stats`, `guild_configuration`                | Job handlers, Economy/Leveling                 |
| Configuration | `guild_configuration`, environment, persona config | Guild config, Persona config                   |
| Generation    | In‑memory request context                          | ContextFactory, PromptBuilder                  |

## Guardrails

- Platform state must be activated via state services; do not mutate collections directly.
- Gameplay is event‑bound and must not alter persona directly.
- Configuration scopes behavior but never overrides platform state.
- Generation state is ephemeral; do not persist prompts outside lifecycle artifacts.

For operator actions see [operations/OPERATOR_GUIDE.md](../operations/OPERATOR_GUIDE.md). For architecture see [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md).
