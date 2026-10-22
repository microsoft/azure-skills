# Voice Agent Common Invariants

Rules shared by Prompt Voice and Hosted Voice services in `azure.yaml`.

## Classification

- Author and maintain Voice Agent services with canonical `kind: voice`.
- Silently recognize existing `kind: prompt-voice` manifests as Voice Agents for compatibility, and normalize them to `kind: voice` when editing.
- **Prompt Voice** declares `model` with `modelType: managed` or `self_deployed`.
- **Hosted Voice** uses a managed Voice wrapper whose `conversationEngine` names a distinct hosted target.
- A standalone `kind: hosted` service using raw `invocations_ws` is not a managed Voice Agent.

## Required Rules

1. Place Voice fields directly under `services.<service-key>`; never use a nested `config:` block.
2. Declare exactly one engine:
   - Prompt Voice: `modelType` plus `model.id`.
   - Voice wrapper: `conversationEngine`.
3. Stop when both engines or neither engine are declared.
4. Never use obsolete `modelType: hosted_agent` or `targetAgent`.
5. Keep hosted target and Voice wrapper service keys and `name` values distinct.
6. Preserve existing optional settings and omit optional fields the user did not request.

## Lifecycle Boundaries

- Deploy Voice services with azd.
- Do not invoke a Voice service with `azd ai agent invoke`.
- Prompt Voice has no local container.
- Hosted target testing validates only its Voice Live Bridge handler; the Voice wrapper still requires end-to-end testing over the managed `voice` WebSocket.

Load only the selected subtype reference:

- [Prompt Voice YAML](voice-agent-prompt-yaml.md)
- [Hosted Voice YAML](hosted-voice-yaml.md)
