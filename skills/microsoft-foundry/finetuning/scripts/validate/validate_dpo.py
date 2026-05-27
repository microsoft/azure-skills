#!/usr/bin/env python3
"""Validate DPO (Direct Preference Optimization) JSONL files for Azure AI Foundry.

Adapted from foundry-ft agent with additional checks:
- Identical preferred/non_preferred detection
- DPO overtraining risk (small dataset warning)
"""
import json
import sys



try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
def validate_dpo(filepath: str) -> None:
    errors = []
    warnings = []
    total = 0

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

            for field in ["input", "preferred_output", "non_preferred_output"]:
                if field not in record:
                    errors.append(f"Line {line_num}: Missing '{field}' field")

            if "input" not in record:
                continue

            inp = record["input"]
            if "messages" not in inp:
                errors.append(f"Line {line_num}: 'input' missing 'messages' field")
            else:
                msgs = inp["messages"]
                if not any(m.get("role") == "user" for m in msgs):
                    errors.append(f"Line {line_num}: 'input.messages' has no 'user' message")

            for output_field in ["preferred_output", "non_preferred_output"]:
                if output_field in record:
                    out = record[output_field]
                    if not isinstance(out, list) or len(out) == 0:
                        errors.append(f"Line {line_num}: '{output_field}' must be a non-empty array")
                    elif not any(m.get("role") == "assistant" for m in out):
                        errors.append(f"Line {line_num}: '{output_field}' has no 'assistant' message")

            if "preferred_output" in record and "non_preferred_output" in record:
                pref = json.dumps(record["preferred_output"], sort_keys=True)
                non_pref = json.dumps(record["non_preferred_output"], sort_keys=True)
                if pref == non_pref:
                    warnings.append(f"Line {line_num}: preferred and non_preferred outputs are identical")

    print(f"\n{'='*60}")
    print(f"DPO Validation Report: {filepath}")
    print(f"{'='*60}")
    print(f"Total records: {total}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    # DPO-specific guidance from our experiments
    if total < 500 and total > 0:
        print(f"\n⚠️  DPO tip: With {total} pairs, use n_epochs=1-2 max (Azure defaults to 3, which causes overtraining on small datasets).")
    if total > 0:
        print(f"\n💡 DPO tip: If your base model already scores >9/10 on this task, DPO may hurt more than help.")

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
        print(f"\n✅ Data is valid for DPO fine-tuning!")
    else:
        print(f"\n❌ Fix {len(errors)} error(s) before submitting.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_dpo.py <path-to-jsonl>")
        sys.exit(1)
    validate_dpo(sys.argv[1])
