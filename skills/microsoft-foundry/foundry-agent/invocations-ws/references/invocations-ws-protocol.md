# Invocations WebSocket Protocol Guide

The `invocations_ws` protocol is a **duplex WebSocket pass-through**. After the platform authenticates the upgrade request and routes it to your container, every frame in both directions is forwarded as-is. The agent developer defines the wire format, the framing model, and the streaming semantics. Unlike `responses` (OpenAI-compatible, platform-managed history) and `invocations` (single HTTP request/response, bytes in / bytes out), `invocations_ws` is a long-lived bidirectional channel under full container control.

## Input/Output Contract

| Aspect | `responses` | `invocations` | `invocations_ws` |
|--------|-------------|---------------|------------------|
| **Transport** | HTTPS request/response | HTTPS request/response | WebSocket (`wss://`) |
| **Lifetime** | Per request | Per request | Long-lived duplex connection |
| **Input** | Natural language `inputText` | Raw HTTP request body | Sequence of WS frames in either direction |
| **Output** | Structured OpenAI JSON | Raw response bytes | Sequence of WS frames in either direction |
| **Framing** | n/a (single body) | n/a (single body) | Developer-defined: binary (PCM, protobuf), text (JSON), or mixed |
| **Streaming** | `stream: true` (SSE) | Agent-controlled (SSE-over-HTTP, etc.) | Native — duplex by definition |
| **History** | Platform via `conversationId` | Agent-managed | Agent-managed; keyed by `agent_session_id` |

## URL and Headers

```
wss://{account}.services.ai.azure.com
   /api/projects/agents/endpoint/protocols/invocations_ws
   ?project-name={project}
   &agent-name={agentName}
   &api-version=v1
   &agent_session_id={sessionId}
```

| Query parameter | Required | Notes |
|-----------------|----------|-------|
| `project-name` | ✅ | Foundry project name (the segment after `/api/projects/` in the project endpoint) |
| `agent-name` | ✅ | Hosted agent name as declared in `agent.yaml` |
| `api-version` | ❌ | Defaults to `v1` |
| `agent_session_id` | ✅ | Per-connection identifier — see [Session Management](session-management.md) |

| Header | Required | Notes |
|--------|----------|-------|
| `Authorization: Bearer <token>` | ✅ | Entra token for audience `https://ai.azure.com` — `az account get-access-token --resource https://ai.azure.com` |

The container receives the upgrade on path `/invocations_ws`. The `agent_session_id` query string is preserved and visible to the container so it can route, log, and persist state per connection.

> ⚠️ **Browsers cannot set the `Authorization` header on a `WebSocket`.** Browser clients must connect through a thin server-side proxy that adds the header before forwarding. This is a browser API limitation, not a Foundry requirement.

## Connection Limits

The service enforces two hard limits on every `invocations_ws` connection:

| Limit | Value | Behaviour |
|-------|-------|-----------|
| **Idle timeout** | **5 minutes** | If no frame is sent **or** received in either direction for 5 minutes, the service closes the WebSocket. |
| **Max connection duration** | **30 minutes** | Every WebSocket is forcibly closed 30 minutes after the upgrade completes, regardless of how active it has been. |

Both limits apply to the WebSocket itself; the container and the client cannot extend them by configuration. To stay connected longer:

- **Defeat the idle timeout** with application-level keep-alives (any frame counts — a no-op JSON ping, an empty binary frame, a heartbeat event). Send them more often than the 5-minute window; 60–120 seconds is a safe interval.
- **Handle the 30-minute cap** by reconnecting. Reuse the same `agent_session_id` so the container can resume per-session state on the new connection (see [Session Management](session-management.md)). For voice or other media workloads, drain in-flight audio and open the new WebSocket before the old one is closed to avoid a perceptible gap.

Standard WebSocket protocol-level pings (RFC 6455 control frames) do not necessarily reset the idle timer — emit an application-layer frame to be safe.

## Pass-Through Semantics

The platform is a transparent relay:

- **No schema validation.** Binary opcodes, text JSON, protobuf, raw PCM — anything ends up at the container untouched.
- **No transcoding.** Sample rate, codec, byte order are entirely between caller and container.
- **No history.** Nothing is persisted by Foundry between connections. Use the container filesystem or an external store, keyed by `agent_session_id`, if you need continuity.
- **No platform-managed turn taking.** There is no concept of "request" vs "response" — both sides may send frames at any time. Implement your own request/reply correlation if you need it (e.g. include an `id` field in each JSON frame).

## Common Framing Patterns

These are protocols developers build **on top of** the raw WebSocket. The platform does not require, parse, or validate any of them; they are listed for orientation only.

| Pattern | Typical use | Notes |
|---------|-------------|-------|
| **Raw binary media frames** | Voice agents (PCM, Opus) | Binary opcode; agree on sample rate, channels, bit depth out-of-band |
| **Length-prefixed protobuf** | Real-time pipeline frameworks | Each WS frame is one serialized message; control + audio multiplexed |
| **JSON control + binary media** | Mixed signaling | Text frames carry control (e.g. start/stop, RTVI events), binary frames carry media |
| **Pure JSON signaling** | Out-of-band media transports (WebRTC offer/answer/ICE, SFU join tokens) | One JSON object per frame; FIFO request/reply if the protocol is purely turn-based |
| **SSE-style event stream** | One-way server push of events | Text frames; the WS is effectively used as a richer SSE |

## Discovering the Expected Wire Format

> ⚠️ **Do not guess.** The platform exposes no OpenAPI / AsyncAPI surface for `invocations_ws` agents. The contract lives in the container code.

### 1. Inspect the WebSocket Handler

Look at the function decorated with `@app.websocket("/invocations_ws")` (FastAPI) or the equivalent ASGI / framework hook. The handler determines:

- Whether frames are binary, text, or mixed
- The expected first frame (handshake, capabilities, auth challenge)
- The control vocabulary (start, stop, mute, hangup, etc.)
- The response cadence (turn-based vs free-running)

### 2. Inspect the Sample Client

Hosted-agent samples ship with a client portal (often under `chat_client/`) that connects to the same WebSocket. The client is the executable specification of the protocol — read its serializer/deserializer.

### 3. Ask the User or Author

If neither the handler nor a sample client is available, ask the agent author for the framing spec before connecting.

## Examples

**Connect from a Python client (no browser proxy):**

```python
import os, uuid, websockets

token = os.popen("az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv").read().strip()
url = (
    "wss://{account}.services.ai.azure.com/api/projects/agents/endpoint/protocols/invocations_ws"
    "?project-name={project}&agent-name={name}&api-version=v1"
    f"&agent_session_id={uuid.uuid4().hex}"
)

async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token}"}) as ws:
    await ws.send(b"<first frame in your wire format>")
    async for frame in ws:
        ...  # frame is bytes (binary) or str (text) depending on what the container sends
```

**Connect from a browser** — terminate a local WebSocket in a server-side proxy that injects the token, then forward frames pass-through to the upstream `wss://`.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| 401 / 403 on upgrade | Missing or expired Entra token | Re-mint with `az account get-access-token --resource https://ai.azure.com` |
| 404 on upgrade | Wrong `project-name`, `agent-name`, or `api-version` | Verify with `agent_get`; check that the deployed version uses `protocol: invocations_ws` |
| WS closes after accept | Container raised in the handler | Tail logs with `azd ai agent monitor --session-id <agent_session_id> --follow` |
| Frames silently dropped | Wire-format mismatch (binary vs text, wrong schema) | Confirm both ends agree on framing — the platform performs no transcoding |
| State lost on reconnect | Different `agent_session_id` used | Reuse the same `agent_session_id` to land on the same logical state inside the container |
| Connection closed after ~5 min of silence | **5-minute idle timeout** — no frames in either direction | Emit application-level keep-alive frames more often than every 5 minutes |
| Connection closed at ~30 min mark | **30-minute max connection duration** (hard cap) | Reconnect with the same `agent_session_id`; drain in-flight work before the cap |
| Browser fails with `1006 abnormal closure` | Browser tried to connect directly with no `Authorization` | Route through a server-side proxy that adds the header |
