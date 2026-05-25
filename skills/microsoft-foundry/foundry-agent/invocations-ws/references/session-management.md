# Session Management (`invocations_ws`)

Sessions on the `invocations_ws` protocol are **per-connection** and identified by the `agent_session_id` query parameter on the WebSocket upgrade URL. They are the unit of state continuity for real-time hosted agents.

> ℹ️ This document covers sessions for `invocations_ws`. For HTTP `responses` / `invocations` agents that use the MCP `session_*` tools, see [`invoke/references/session-management.md`](../../invoke/references/session-management.md).

## Overview

For HTTP-protocol hosted agents the MCP tools `session_create` / `session_get` / `session_delete` provision dedicated compute and a persistent `$HOME` filesystem keyed by a server-issued `sessionId`. For `invocations_ws` the model is different:

- The session is established by the **WebSocket upgrade itself**.
- The session id is **client-supplied** via the `agent_session_id` query string parameter.
- The container sees the id on connect and uses it to look up (or initialise) per-connection state.
- When the WebSocket closes, the connection ends. Whether any state survives is entirely up to the container implementation.

There is no separate "create session" step and no `session_create` MCP tool call for `invocations_ws`.

## Session Lifecycle

```text
client picks agent_session_id
  └─► WebSocket upgrade (with Authorization + agent_session_id query)
        └─► container accepts → handler bound to this agent_session_id
              └─► frames flow in both directions
                    └─► either side closes, OR service enforces a timeout
                          └─► container decides whether to persist state for next connect
```

## Service-Enforced Connection Limits

Every `invocations_ws` WebSocket is subject to two hard limits enforced by the service. They cap the **connection**, not the logical session — reconnecting with the same `agent_session_id` is the supported way to continue beyond them.

| Limit | Value | Trigger |
|-------|-------|---------|
| **Idle timeout** | **5 minutes** | No frames sent or received in either direction for 5 minutes |
| **Max connection duration** | **30 minutes** | 30 minutes after the upgrade, regardless of traffic |

Implications:

- **Always run an application-level keep-alive** on long-lived connections — any frame (no-op JSON heartbeat, empty binary frame, audio silence) more often than every 5 minutes. Do not rely on RFC 6455 WebSocket ping frames to keep the idle timer alive.
- **Plan for reconnect every ~30 minutes.** Before the cap, open a new WebSocket with the same `agent_session_id`, switch traffic to it, then close the old one. The container sees a fresh `accept()` and must re-hydrate per-connection state from your store.
- **Persist anything you want to survive the cap.** In-memory state in the connection handler is lost at the 30-minute mark; only state written to external storage (keyed by `agent_session_id`) carries over.

## `agent_session_id` Format

Treat `agent_session_id` as a URL-safe identifier you generate per logical session:

| Rule | Notes |
|------|-------|
| Must be URL-safe | Embedded in the query string; URL-encode if you stray outside `[A-Za-z0-9_-]` |
| Recommended pattern | `^[A-Za-z0-9_-]{8,128}$` — mirrors the HTTP-protocol `sessionId` rules for consistency |
| Uniqueness | Use a UUID, ULID, or random token per logical conversation/user; do not reuse across unrelated users |
| Stability | **Reuse the same id** on intentional reconnects to preserve agent-managed state |

A common pattern is one `agent_session_id` per browser tab (regenerated on hard reload) or one per user session in your backend.

## URL Placement

The id goes on the **Foundry-side** URL the client connects to, not on the container's internal `/invocations_ws` path:

```
wss://{account}.services.ai.azure.com
   /api/projects/agents/endpoint/protocols/invocations_ws
   ?project-name={project}
   &agent-name={agentName}
   &api-version=v1
   &agent_session_id={your-id}    ← here
```

The platform preserves the query string when routing to the container, so the container handler can read it from the request scope.

## Container-Side Handling

The container is responsible for everything past the upgrade. Typical patterns:

| Goal | Approach |
|------|----------|
| Per-connection scratch state | Hold a dict keyed by `agent_session_id` in the process; clear on disconnect |
| Cross-reconnect continuity | Persist state to an external store (Cosmos DB, Redis, Blob) before disconnect — **not** to local disk. The next connection can land on a different replica. |
| Per-user history | Map `agent_session_id` → user id in your handler; load prior conversation from your store on connect |
| Concurrent connections with same id | Decide upfront: reject the second, hijack the first, or fan out — Foundry does not enforce single-connection-per-id |

> ⚠️ **No `$HOME` lifecycle guarantee.** Unlike HTTP-protocol sessions (where the platform binds a dedicated compute instance to a `sessionId`), an `invocations_ws` connection can land on any healthy replica. If you need durable per-session state, write it to external storage rather than relying on local disk.

## Observing Sessions

Stream container stdout/stderr for a specific connection:

```bash
azd ai agent monitor <agent-name> --session-id <agent_session_id> --follow
```

The MCP `session_logstream` tool accepts the same `agent_session_id` for `invocations_ws` agents. Other `session_*` MCP tools (`session_create`, `session_get`, `session_delete`, `session_list`, file operations) do **not** apply to `invocations_ws` — there is no platform-side session object to manage.

## Session vs Conversation

| Concept | `invocations_ws` | `responses` (HTTP) | `invocations` (HTTP) |
|---------|------------------|--------------------|----------------------|
| Per-connection identifier | `agent_session_id` (client-supplied query param) | `sessionId` (server-issued via `session_create`) | `sessionId` (server-issued via `session_create`) |
| Conversation history | Agent-managed | Platform-managed via `conversationId` | Agent-managed |
| Persistent `$HOME` | Not guaranteed | ✅ (bound to `sessionId`) | ✅ (bound to `sessionId`) |
| Created by | Opening the WebSocket | `session_create` MCP tool | `session_create` MCP tool |

## Best Practices

1. **Generate `agent_session_id` once per logical session** — e.g. on first connect for a given user/tab; reuse it on reconnects so the container can resume state.
2. **Keep ids opaque and unguessable** — they appear in logs and may be visible to operators; do not encode PII into them.
3. **Externalise durable state** — assume the next connection can land on a different replica.
4. **Send application-level keep-alives** — emit a heartbeat frame more often than the **5-minute idle timeout** in both directions (60–120 s is safe). RFC 6455 ping frames are not guaranteed to reset the timer.
5. **Plan reconnects around the 30-minute cap** — every WebSocket is closed at the 30-minute mark. Open a fresh connection with the same `agent_session_id` before the deadline and drain in-flight work to the new socket so users see no gap.
6. **Persist what must survive a reconnect** — in-memory handler state is lost when the WebSocket closes (idle timeout, max-duration cap, network blip, or replica restart). Write durable state to external storage keyed by `agent_session_id`.
7. **Clean up on disconnect** — release per-session resources (audio pipelines, model contexts, file handles) when the WebSocket closes; otherwise replicas leak memory under churn.
8. **Use `azd ai agent monitor --session-id`** to scope logs when debugging a specific user report.
