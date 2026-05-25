#!/usr/bin/env python3
"""Validate RFT (Reinforcement Fine-Tuning) JSONL files for Azure AI Foundry.

Adapted from foundry-ft agent with critical additions from our platform gotchas:
- Grader escaping warnings for newlines (\\n must be \\\\n in JSON strings)
- Content moderation risk detection ("chain of thought" triggers RAI filter)
- Reference answer diversity check
"""
import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
from collections import Counter


RISKY_PHRASES = [
    "chain of thought", "step by step reasoning", "let me think",
    "think carefully", "reason through",
]


def validate_rft(filepath, expected_field=None):
    errors = []
    warnings = []
    total = 0
    extra_fields_per_line: list[set[str]] = []
    all_extra_field_counts: Counter = Counter()
    grader_values: list[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw_line = line
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
            else:
                msgs = record["messages"]
                if not isinstance(msgs, list) or len(msgs) == 0:
                    errors.append(f"Line {line_num}: 'messages' must be a non-empty array")
                elif not any(m.get("role") == "user" for m in msgs):
                    errors.append(f"Line {line_num}: 'messages' has no 'user' message")
                elif msgs[-1].get("role") != "user":
                    errors.append(
                        f"Line {line_num}: Last message must be 'user' role for RFT "
                        f"(found '{msgs[-1].get('role')}') — unlike SFT, the model generates its own response"
                    )

            # Detect extra fields (grader fields) beyond 'messages'
            extra_fields = set(record.keys()) - {"messages"}
            extra_fields_per_line.append(extra_fields)
            all_extra_field_counts.update(extra_fields)

            if expected_field:
                if expected_field not in record:
                    errors.append(f"Line {line_num}: Missing expected field '{expected_field}'")
                else:
                    val = str(record[expected_field]).strip()
                    if not val:
                        errors.append(f"Line {line_num}: '{expected_field}' is empty")
                    else:
                        grader_values.append(val)
            else:
                if not extra_fields:
                    errors.append(
                        f"Line {line_num}: No grader fields found — RFT requires at least "
                        "one field beyond 'messages' (e.g. 'answer', 'reference_code')"
                    )
                else:
                    # Collect values from extra fields for diversity check
                    for field in sorted(extra_fields):
                        val = str(record[field]).strip()
                        if val:
                            grader_values.append(val)

                    # Check for unescaped newlines in extra fields (CRITICAL platform gotcha)
                    # Instead of regex-parsing the raw JSON line (which risks catastrophic
                    # backtracking), we compare the parsed value against the raw line to
                    # detect single-escaped \n that should be double-escaped \\n.
                    for field in extra_fields:
                        parsed_val = str(record.get(field, ""))
                        if "\n" in parsed_val:
                            # The parsed value contains actual newlines — check if the raw
                            # JSON has them properly double-escaped
                            field_needle = f'"{field}"'
                            if field_needle in raw_line:
                                field_start = raw_line.index(field_needle)
                                field_region = raw_line[field_start:field_start + 500]
                                # Single-escaped \n in raw JSON (not \\n) means the source
                                # code newlines aren't properly escaped for the platform
                                if "\\n" in field_region and "\\\\n" not in field_region:
                                    warnings.append(
                                        f"Line {line_num}: '{field}' contains \\n sequences — "
                                        "if this is grader source code embedded in JSON, "
                                        "ensure newlines are escaped as \\\\n."
                                    )

            # Content moderation risk
            all_text = json.dumps(record).lower()
            for phrase in RISKY_PHRASES:
                if phrase in all_text:
                    warnings.append(
                        f"Line {line_num}: Contains '{phrase}' — may trigger Azure content moderation filter."
                    )
                    break

    # Check for inconsistent extra-field schemas across examples
    field_sets = [fs for fs in extra_fields_per_line if fs]
    if len(field_sets) > 1:
        first_schema = field_sets[0]
        inconsistent_lines = [
            i + 1 for i, fs in enumerate(extra_fields_per_line)
            if fs and fs != first_schema
        ]
        if inconsistent_lines:
            warnings.append(
                f"Inconsistent grader fields across examples — "
                f"line 1 has {sorted(first_schema)}, but {len(inconsistent_lines)} "
                f"line(s) differ (e.g. line {inconsistent_lines[0]}). "
                "Ensure your grader handles all field variants."
            )

    # Diversity check
    if grader_values:
        unique_values = set(grader_values)
        if len(unique_values) == 1:
            warnings.append(
                f"All grader field values are identical ('{list(unique_values)[0][:50]}...') — "
                "grader may not learn effectively"
            )
        avg_len = sum(len(v) for v in grader_values) / len(grader_values)
        if avg_len > 500:
            warnings.append(
                f"Average grader field value length is {avg_len:.0f} chars — "
                "consider using a model_grader instead of string_check"
            )

    print(f"\n{'='*60}")
    print(f"RFT Validation Report: {filepath}")
    print(f"{'='*60}")
    print(f"Total records: {total}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if all_extra_field_counts:
        print(f"\nGrader fields found:")
        for field, count in all_extra_field_counts.most_common():
            print(f"  • '{field}' — in {count}/{total} records")

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
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more warnings")

    # RFT-specific guidance
    if total > 0:
        print(f"\n💡 RFT tips:")
        print(f"  • Ensure your training grader matches your eval grader (alignment gotcha)")
        print(f"  • Start with reasoning_effort='medium', pass_threshold=0.5")
        print(f"  • RFT is primarily for o-series models (o4-mini). Check Azure docs for the latest supported model list.")

    if not errors:
        print(f"\n✅ Data is valid for RFT fine-tuning!")
    else:
        print(f"\n❌ Fix {len(errors)} error(s) before submitting.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate RFT (Reinforcement Fine-Tuning) JSONL files for Azure AI Foundry."
    )
    parser.add_argument("filepath", help="Path to the JSONL file to validate")
    parser.add_argument(
        "--expected-field",
        default=None,
        help="Specific grader field name to require (e.g. 'answer'). "
             "If omitted, any extra field beyond 'messages' is accepted.",
    )
    args = parser.parse_args()
    validate_rft(args.filepath, expected_field=args.expected_field)
