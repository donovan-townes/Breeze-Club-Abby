# Platform State

Canonical, global timeline (seasons, events, eras, modes). Drives platform-wide effects.

## Source of truth

- Mongo `system_state` (definitions + active flags)
- Mongo `system_state_instances` (scoped instances with priorities)
- Templates in `abby_core/system/state_registry.py` (`APPROVED_EVENT_TEMPLATES`)

## Ownership and mutation

### State Activation (Atomic Guarantees):

All state transitions are orchestrated by `StateActivationService` with atomic guarantees:

- **Atomic Transactions:** Uses MongoDB transactions to ensure consistent state activation
- **Automatic Deactivation:** Deactivates other states of same type (e.g., deactivate "autumn" when activating "winter")
- **Operator Audit Trail:** Records operator_id, reason, activated_at timestamp
- **Effects Validation:** Validates effects before activation (checks persona overlays, type coercion)
- **Operation Recording:** Creates durable operation record in `system_operations` collection
- **Event Broadcasting:** Broadcasts state change events for downstream consumers

**Owner:** [abby_core/services/state_activation_service.py](../../abby_core/services/state_activation_service.py)

### API:

```python
## Activate a state (atomic with rollback on failure)
state_doc, error = state_activation_service.activate_state(
    state_id="winter-2026",
    operator_id="operator:alice",
    reason="Scheduled seasonal transition"
)

## Deactivate a state
state_doc, error = state_activation_service.deactivate_state(
    state_id="autumn-2025",
    operator_id="operator:alice",
    reason="Season ended"
)
```python

### Legacy Methods (Do Not Use):

- Do not mutate `system_state` documents directly via MongoDB
- Do not use `system_state.py` activate() without transaction wrapping
- Do not mutate via guild config or ad-hoc flags

## Effects

- `effects.xp_reset`: signals seasonal XP reset eligibility
- `effects.persona_overlay`: enables persona overlays for generation
- `effects.tone_shift` or other flags: inform tone/theming
- Gameplay toggles live on event effects (see Gameplay State)

### Effects Merge Precedence (Phase 1: Determinism)

### When multiple active states define the same effect, merge strategies determine the final value:

- **Override Strategy** (e.g., `persona_overlay`): Last processed value wins (states sorted by priority DESC, then start_at DESC)
- **Additive Strategy** (e.g., `affinity_modifier`): Sum all values, starting from identity 0.0
- **OR Strategy** (e.g., `crush_system_enabled`): Logical OR, starting from identity False
- **Max Strategy**: Highest value wins

### Deterministic Guarantees:

1. States are sorted by `priority DESC, start_at DESC` before merging
2. Identity values ensure consistent starting points (additive: 0.0, multiplier: 1.0, or: False)
3. MongoDB snapshot isolation prevents concurrent reads from seeing inconsistent states during transitions

### Example:
If Valentine Event (priority 100, affinity_modifier +0.5) and Summer Event (priority 50, affinity_modifier +0.3) are both active:

- Final `affinity_modifier` = 0.0 (identity) + 0.5 (Valentine) + 0.3 (Summer) = 0.8

**Implementation:** See [system_state_resolver.py](../../abby_core/llm/system_state_resolver.py) (snapshot isolation) and [effects_merger.py](../../abby_core/system/effects_merger.py) (merge strategies).

## Validation (Phase 2: Safety Gates)

### Persona Overlay Validation (Task 19)

### Before activating a state with `persona_overlay` effect, validation checks:

- Persona name exists in `PersonalityManager.get_available_personas()`
- If PersonalityManager unavailable, logs warning but allows (lenient failure mode)
- Prevents activation of states with non-existent personas

**Owner:** [abby_core/system/state_validation_service.py](../../abby_core/system/state_validation_service.py) `validate_persona_overlay()`  
**Invoked From:** [state_activation_service.py](../../abby_core/services/state_activation_service.py) during activation  
**Impact:** Prevents runtime errors from invalid persona references

### State Definition Validation

### Before a state can be activated, StateValidationService validates:

- Required fields present: `name`, `priority`, `effects`, `date_active`
- Scope validity: value in (guild, global, event)
- Priority is numeric and non-negative
- Date range valid: `date_start <= date_end`
- Effects have known keys and valid value types
- Cross-state consistency (no conflicting effect keys)
- **Persona overlays:** Validated against PersonalityManager

**Owner:** [abby_core/system/state_validation_service.py](../../abby_core/system/state_validation_service.py)  
**Invoked From:** [state_activation_service.py](../../abby_core/services/state_activation_service.py) before transaction  
**Impact:** Prevents malformed states from activating and corrupting effects merge

### Effects Merge Validation

### After effects merge, EffectsValidationService validates merged values:

- All effect values are the correct type (boolean flags are bool, numeric modifiers are float, etc.)
- Range checks (affinity_modifier must be 0.5-2.0)
- Boolean flags are True/False (not null or arbitrary strings)
- Identity values preserved for additive strategies

**Owner:** [abby_core/system/effects_validation_service.py](../../abby_core/system/effects_validation_service.py)  
**Invoked From:** [effects_merger.py](../../abby_core/system/effects_merger.py) merge completion  
**Impact:** Prevents invalid effects from injection into generation context

## Invariants

- Exactly one active state per `state_type` at a time.
- Activation deactivates other states of the same type.
- Changes are auditable (store operator id when possible).

## Key functions

- `get_active_state`, `get_active_season`, `activate_state` in `abby_core/system/system_state.py`
- `create_event_from_template` in `abby_core/system/state_registry.py`

## Observability

- Track active state doc, `activated_at`, `activated_by`
- Log every activation; emit events for downstream consumers

See also: [STATE_MAP.md](STATE_MAP.md) for full catalog and mutators.
