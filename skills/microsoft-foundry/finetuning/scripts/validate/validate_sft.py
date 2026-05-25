#!/usr/bin/env python3
"""Validate SFT (Supervised Fine-Tuning) JSONL files for Azure AI Foundry.

Adapted from foundry-ft agent with additional checks from our platform gotchas:
- Token length warnings (4096 limit varies by model)
- System prompt consistency check
"""
import json
import sys


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
VALID_ROLES = {"system", "user", "assistant", "tool"}


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def validate_sft(filepath: str) -> None:
    errors = []
    warnings = []
    total = 0
    token_counts = []
    system_prompts = set()

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON — {e}")
                continue

            if "messages" not in record:
                errors.append(f"Line {line_num}: Missing 'messages' field")
                continue

            messages = record["messages"]
            if not isinstance(messages, list) or len(messages) == 0:
                errors.append(f"Line {line_num}: 'messages' must be a non-empty array")
                continue

            roles_found = set()
            total_text = ""
            for i, msg in enumerate(messages):
                if "role" not in msg:
                    errors.append(f"Line {line_num}, message {i}: Missing 'role'")
                elif msg["role"] not in VALID_ROLES:
                    errors.append(f"Line {line_num}, message {i}: Invalid role '{msg['role']}' (expected: {VALID_ROLES})")
                else:
                    roles_found.add(msg["role"])

                if "content" not in msg and "tool_calls" not in msg:
                    errors.append(f"Line {line_num}, message {i}: Missing 'content' (and no 'tool_calls')")
                elif "content" in msg and msg["content"] is not None:
                    content = str(msg["content"])
                    if not content.strip():
                        warnings.append(f"Line {line_num}, message {i}: Empty content string")
                    total_text += content

                    if msg.get("role") == "system":
                        system_prompts.add(content.strip()[:100])

            if "user" not in roles_found:
                errors.append(f"Line {line_num}: No 'user' message found")
            if "assistant" not in roles_found:
                errors.append(f"Line {line_num}: No 'assistant' message found")

            tokens = estimate_tokens(total_text)
            token_counts.append(tokens)
            if tokens > 4096:
                warnings.append(f"Line {line_num}: ~{tokens} tokens (exceeds 4096 limit for most models)")

    # Report
    print(f"\n{'='*60}")
    print(f"SFT Validation Report: {filepath}")
    print(f"{'='*60}")
    print(f"Total records: {total}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if token_counts:
        avg_tok = sum(token_counts) / len(token_counts)
        print(f"\nToken stats (approx):")
        print(f"  Avg: {avg_tok:.0f}  Min: {min(token_counts)}  Max: {max(token_counts)}")
        print(f"  Total: {sum(token_counts):,}")

    if len(system_prompts) > 1:
        warnings.append(f"Found {len(system_prompts)} different system prompts — ensure this is intentional")
    if system_prompts:
        print(f"\nSystem prompts: {len(system_prompts)} unique")

    if errors:
        print(f"\n❌ ERRORS (must fix):")
        for e in errors[:20]:
            print(f"  • {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")

    if warnings:
        print(f"\n⚠️  WARNINGS:")
        for w in warnings[:10]:
            print(f"  • {w}")

    if not errors:
        print(f"\n✅ Data is valid for SFT fine-tuning!")
    else:
        print(f"\n❌ Fix {len(errors)} error(s) before submitting.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_sft.py <path-to-jsonl>")
        sys.exit(1)
    validate_sft(sys.argv[1])
