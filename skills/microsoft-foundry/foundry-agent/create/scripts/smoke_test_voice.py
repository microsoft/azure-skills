"""Smoke-test a deployed Microsoft Foundry Voice Agent.

Exit codes:
  0: passed, help, or dry-run
  1: runtime, authentication, dependency, protocol, or response failure
  2: usage or argument validation error
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

GREETING_GRACE_SECONDS = 1.0
DEFAULT_PROMPT = "In one short sentence, introduce yourself."
REQUEST_METADATA_KEY = "foundry_voice_smoke_test_request"


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test a deployed Microsoft Foundry Voice Agent."
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="Foundry project endpoint or full managed Voice WebSocket URL",
    )
    parser.add_argument("--agent-name", required=True, help="Deployed Voice Agent name")
    parser.add_argument("--text", default=DEFAULT_PROMPT, help="Prompt text to send")
    parser.add_argument(
        "--expected-marker",
        default="",
        help="Substring that must appear in the requested turn transcript",
    )
    parser.add_argument(
        "--timeout",
        type=positive_integer,
        default=180,
        help="Positive timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--output-audio",
        default="",
        help="Optional path for decoded PCM audio bytes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved execution plan without connecting",
    )
    args = parser.parse_args()

    if not args.endpoint.strip():
        parser.error("--endpoint must not be empty")
    if not args.agent_name.strip():
        parser.error("--agent-name must not be empty")
    if not args.text.strip():
        parser.error("--text must not be empty")
    if args.expected_marker is not None and not args.expected_marker.strip():
        args.expected_marker = ""

    return args


def build_ws_url(endpoint: str, agent_name: str) -> str:
    trimmed = endpoint.rstrip("/")
    if trimmed.startswith("https://"):
        ws_base = f"wss://{trimmed[len('https://'):]}"
    elif trimmed.startswith("wss://"):
        ws_base = trimmed
    else:
        raise ValueError("--endpoint must start with https:// or wss://")

    if "/protocols/voice" in ws_base:
        return ws_base
    return (
        f"{ws_base}/agents/{agent_name}/endpoint/protocols/voice"
        "?api-version=v1"
    )


def acquire_token() -> str:
    errors: list[str] = []
    az_bin = shutil.which("az.cmd" if os.name == "nt" else "az")
    if az_bin:
        try:
            token = subprocess.check_output(
                [
                    az_bin,
                    "account",
                    "get-access-token",
                    "--resource",
                    "https://ai.azure.com",
                    "--query",
                    "accessToken",
                    "-o",
                    "tsv",
                ],
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()
            if token:
                return token
            errors.append("Azure CLI returned an empty token")
        except (OSError, subprocess.CalledProcessError) as exc:
            output = getattr(exc, "output", "")
            errors.append(f"Azure CLI token acquisition failed: {str(output).strip() or exc}")
    else:
        errors.append("Azure CLI executable was not found")

    try:
        from azure.identity import DefaultAzureCredential

        return DefaultAzureCredential().get_token(
            "https://ai.azure.com/.default"
        ).token
    except Exception as exc:
        errors.append(f"DefaultAzureCredential failed: {exc}")

    raise RuntimeError("; ".join(errors))


async def send_user_turn(ws: object, text: str, request_marker: str) -> None:
    await ws.send(
        json.dumps(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
    )
    await ws.send(
        json.dumps(
            {
                "type": "response.create",
                "response": {
                    "metadata": {REQUEST_METADATA_KEY: request_marker},
                },
            }
        )
    )


def response_id(event: dict[str, object]) -> str:
    direct_id = event.get("response_id")
    if isinstance(direct_id, str):
        return direct_id
    response = event.get("response")
    if isinstance(response, dict):
        nested_id = response.get("id")
        if isinstance(nested_id, str):
            return nested_id
    return ""


def response_has_request_marker(
    event: dict[str, object], request_marker: str
) -> bool:
    response = event.get("response")
    if not isinstance(response, dict):
        return False
    metadata = response.get("metadata")
    return (
        isinstance(metadata, dict)
        and metadata.get(REQUEST_METADATA_KEY) == request_marker
    )


async def run_smoke_test(args: argparse.Namespace, ws_url_base: str) -> int:
    try:
        import websockets
    except ImportError as exc:
        print(
            f"ERROR: Missing WebSocket client dependency ({exc}). "
            "Install with: python -m pip install websockets",
            file=sys.stderr,
        )
        return 1

    try:
        token = acquire_token()
    except Exception as exc:
        print(
            "ERROR: Failed to acquire an Entra token for https://ai.azure.com: "
            f"{exc}",
            file=sys.stderr,
        )
        return 1

    separator = "&" if "?" in ws_url_base else "?"
    uri = (
        ws_url_base
        if "agent_session_id=" in ws_url_base
        else f"{ws_url_base}{separator}agent_session_id={uuid.uuid4()}"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Foundry-Features": "VoiceAgents=V1Preview",
    }

    events: list[str] = []
    transcript: list[str] = []
    final_transcript = ""
    audio_base64_characters = 0
    decoded_audio = bytearray()
    session_updated = False
    greeting_in_progress = False
    grace_deadline: float | None = None
    sent_turn = False
    request_marker = uuid.uuid4().hex
    requested_response_id = ""
    completed_status: str | None = None

    try:
        try:
            ws_context = websockets.connect(
                uri,
                additional_headers=headers,
                open_timeout=60,
                close_timeout=10,
                max_size=16 * 1024 * 1024,
            )
        except TypeError:
            ws_context = websockets.connect(
                uri,
                extra_headers=headers,
                open_timeout=60,
                close_timeout=10,
                max_size=16 * 1024 * 1024,
            )

        async with ws_context as ws:
            while True:
                if not sent_turn:
                    if (
                        session_updated
                        and not greeting_in_progress
                        and grace_deadline is not None
                    ):
                        remaining_grace = grace_deadline - time.monotonic()
                        if remaining_grace <= 0:
                            await send_user_turn(ws, args.text, request_marker)
                            sent_turn = True
                            continue
                        receive_timeout = min(float(args.timeout), remaining_grace)
                    else:
                        receive_timeout = float(args.timeout)

                    try:
                        raw_message = await asyncio.wait_for(
                            ws.recv(), timeout=receive_timeout
                        )
                    except (TimeoutError, asyncio.TimeoutError):
                        if session_updated and not greeting_in_progress:
                            await send_user_turn(ws, args.text, request_marker)
                            sent_turn = True
                            continue
                        raise

                    event = json.loads(raw_message)
                    event_type = event.get("type", "")
                    events.append(event_type)

                    if event_type == "error":
                        print(
                            "ERROR: Voice session returned an error event: "
                            f"{json.dumps(event)}",
                            file=sys.stderr,
                        )
                        return 1
                    if event_type == "session.updated":
                        session_updated = True
                        if not greeting_in_progress:
                            grace_deadline = (
                                time.monotonic() + GREETING_GRACE_SECONDS
                            )
                    elif event_type == "response.created" or event_type.startswith(
                        "response.output_"
                    ):
                        greeting_in_progress = True
                        grace_deadline = None
                    elif event_type == "response.done" and greeting_in_progress:
                        greeting_in_progress = False
                        grace_deadline = None
                        await send_user_turn(ws, args.text, request_marker)
                        sent_turn = True
                    continue

                raw_message = await asyncio.wait_for(
                    ws.recv(), timeout=float(args.timeout)
                )
                event = json.loads(raw_message)
                event_type = event.get("type", "")
                events.append(event_type)

                if event_type == "error":
                    print(
                        "ERROR: Voice session returned an error event: "
                        f"{json.dumps(event)}",
                        file=sys.stderr,
                    )
                    return 1
                if event_type == "response.created":
                    if response_has_request_marker(event, request_marker):
                        requested_response_id = response_id(event)
                        if not requested_response_id:
                            print(
                                "ERROR: Requested Voice Agent response did not "
                                "include a response ID.",
                                file=sys.stderr,
                            )
                            return 1
                    continue
                if (
                    not requested_response_id
                    or response_id(event) != requested_response_id
                ):
                    continue

                if event_type == "response.output_audio_transcript.delta":
                    transcript.append(event.get("delta", ""))
                elif event_type == "response.output_audio_transcript.done":
                    final_transcript = event.get("transcript", "")
                elif event_type == "response.output_audio.delta":
                    encoded_delta = event.get("delta", "")
                    audio_base64_characters += len(encoded_delta)
                    if args.output_audio and encoded_delta:
                        decoded_audio.extend(base64.b64decode(encoded_delta))
                elif event_type == "response.done":
                    completed_status = event.get("response", {}).get("status")
                    break
    except (TimeoutError, asyncio.TimeoutError):
        print(
            f"ERROR: Timed out after {args.timeout}s waiting for Voice Agent "
            f"'{args.agent_name}'.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"ERROR: Voice WebSocket smoke test failed for "
            f"'{args.agent_name}': {exc}",
            file=sys.stderr,
        )
        return 1

    text = (final_transcript or "".join(transcript)).strip()
    result = {
        "agent": args.agent_name,
        "prompt_text": args.text,
        "response_id": requested_response_id,
        "status": completed_status,
        "transcript": text,
        "audio_base64_characters": audio_base64_characters,
        "event_types": events,
    }
    if args.expected_marker:
        result["expected_marker"] = args.expected_marker

    if completed_status != "completed" or not text or audio_base64_characters <= 0:
        print(
            f"ERROR: Incomplete Voice Agent response: {json.dumps(result)}",
            file=sys.stderr,
        )
        return 1

    if args.expected_marker and args.expected_marker not in text:
        print(
            "ERROR: Voice Agent transcript did not contain expected marker "
            f"{args.expected_marker!r}: {json.dumps(result)}",
            file=sys.stderr,
        )
        return 1

    if args.output_audio:
        try:
            Path(args.output_audio).write_bytes(decoded_audio)
        except OSError as exc:
            print(
                f"ERROR: Failed to write audio output '{args.output_audio}': {exc}",
                file=sys.stderr,
            )
            return 1

    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    try:
        ws_url = build_ws_url(args.endpoint, args.agent_name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        separator = "&" if "?" in ws_url else "?"
        print("DRY-RUN: Voice Agent WebSocket Smoke Test")
        print(f"  Project Endpoint : {args.endpoint}")
        print(f"  Agent Name       : {args.agent_name}")
        print(f"  WebSocket URL    : {ws_url}{separator}agent_session_id=<uuid>")
        print("  Headers          : Foundry-Features: VoiceAgents=V1Preview")
        print(f"  Prompt Text      : {args.text}")
        print(f"  Expected Marker  : {args.expected_marker or '(none)'}")
        print(f"  Timeout (s)      : {args.timeout}")
        print(f"  Output Audio     : {args.output_audio or '(none)'}")
        print("  Auth Resource    : https://ai.azure.com (Azure CLI or DefaultAzureCredential)")
        return 0

    return asyncio.run(run_smoke_test(args, ws_url))


if __name__ == "__main__":
    sys.exit(main())
