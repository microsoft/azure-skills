# /// script
# dependencies = [
#   "openai>=1.0",
# ]
# ///
"""
convert_dataset.py — Convert between SFT, DPO, and RFT dataset formats.

Usage:
  # Parquet/CSV to SFT JSONL
  python convert_dataset.py --input data.parquet --output train.jsonl --format sft \
      --user-column prompt --assistant-column response --system-prompt "You are helpful."

  # SFT JSONL to DPO (generates rejected via base model)
  python convert_dataset.py --input train.jsonl --output dpo.jsonl --format dpo \
      --base-model gpt-4.1-mini --endpoint $ENDPOINT --api-key $KEY

  # SFT JSONL to RFT JSONL (passthrough — same format, different intent)
  python convert_dataset.py --input train.jsonl --output rft.jsonl --format rft

  # DPO JSONL to SFT (extract chosen responses)
  python convert_dataset.py --input dpo.jsonl --output sft.jsonl --format sft-from-dpo
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients


def parquet_to_sft(input_path, output_path, user_col, assistant_col, system_prompt=None):
    """Convert a parquet or CSV file to SFT JSONL."""
    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas required. Install with: pip install pandas pyarrow")
        sys.exit(1)

    if input_path.endswith(".parquet"):
        df = pd.read_parquet(input_path)
    elif input_path.endswith(".csv"):
        df = pd.read_csv(input_path)
    elif input_path.endswith(".json"):
        df = pd.read_json(input_path)
    else:
        print(f"Unsupported format: {input_path}. Use .parquet, .csv, or .json")
        sys.exit(1)

    if user_col not in df.columns or assistant_col not in df.columns:
        print(f"Error: Columns '{user_col}' and/or '{assistant_col}' not found.")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            user_content = str(row[user_col]).strip()
            asst_content = str(row[assistant_col]).strip()
            if not user_content or not asst_content:
                continue

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": asst_content})

            f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
            count += 1

    print(f"Converted {count} examples to SFT JSONL → {output_path}")


def sft_to_dpo(input_path, output_path, client, base_model):
    """Convert SFT to DPO by generating non-preferred responses from a base model.

    DPO format uses: input (system+user messages), preferred_output, non_preferred_output.
    """
    with open(input_path, encoding="utf-8") as inf:
        examples = []
        for ln, raw in enumerate(inf, 1):
            if not raw.strip():
                continue
            try:
                examples.append(json.loads(raw))
            except json.JSONDecodeError as e:
                print(f"  ⚠️ Skipping malformed JSON on line {ln}: {e}")
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for i, ex in enumerate(examples):
            msgs = ex["messages"]
            system_msgs = [m for m in msgs if m["role"] == "system"]
            user_msg = next((m for m in msgs if m["role"] == "user"), None)
            asst_msg = next((m for m in msgs if m["role"] == "assistant"), None)
            if not user_msg or not asst_msg:
                continue

            # Generate a non-preferred response from the base model
            try:
                gen_msgs = system_msgs + [user_msg]
                resp = client.chat.completions.create(
                    model=base_model,
                    messages=gen_msgs,
                    temperature=1.0,  # High temp for diversity
                    max_completion_tokens=2048,
                )
                rejected_content = resp.choices[0].message.content
            except Exception as e:
                print(f"  Skipping example {i}: {e}")
                continue

            if not rejected_content:
                # None or empty — content filter, finish=length with no text, etc.
                # Skip rather than emit a DPO entry with null content (trainer rejects).
                print(f"  Skipping example {i}: base model returned no content")
                continue

            # Build DPO entry with correct format
            input_messages = system_msgs + [user_msg]
            dpo_entry = {
                "input": {"messages": input_messages},
                "preferred_output": [asst_msg],
                "non_preferred_output": [{"role": "assistant", "content": rejected_content}],
            }
            f.write(json.dumps(dpo_entry, ensure_ascii=False) + "\n")
            count += 1

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(examples)}")
                time.sleep(1)

    print(f"Converted {count} examples to DPO JSONL → {output_path}")


def sft_to_rft(input_path, output_path):
    """Convert SFT to RFT format.

    Strips assistant messages (RFT last message must be user) and adds a
    placeholder grader field. The user must populate grader reference fields
    (e.g., expected_answer) before training.
    """
    count = 0
    skipped = 0
    with open(output_path, "w", encoding="utf-8") as out:
        with open(input_path, encoding="utf-8") as inf:
            for ln, line in enumerate(inf, 1):
                if not line.strip():
                    continue
                try:
                    ex = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ⚠️ Skipping malformed JSON on line {ln}: {e}")
                    skipped += 1
                    continue
                msgs = ex.get("messages", [])
                # Keep only system + user messages; RFT last message must be user
                rft_msgs = [m for m in msgs if m["role"] in ("system", "user")]
                if not rft_msgs or rft_msgs[-1]["role"] != "user":
                    skipped += 1
                    continue
                # Extract assistant content as a reference answer placeholder
                asst_msgs = [m for m in msgs if m["role"] == "assistant"]
                expected = asst_msgs[-1]["content"] if asst_msgs else ""
                rft_entry = {"messages": rft_msgs, "expected_answer": expected}
                out.write(json.dumps(rft_entry, ensure_ascii=False) + "\n")
                count += 1
    print(f"Converted {count} examples to RFT JSONL → {output_path}")
    if skipped:
        print(f"  Skipped {skipped} examples (no user message)")
    print("Note: Review 'expected_answer' fields and update your grader to use item.expected_answer.")


def dpo_to_sft(input_path, output_path, system_prompt=None):
    """Extract chosen responses from DPO format to SFT format."""
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        with open(input_path, encoding="utf-8") as inf:
            for ln, line in enumerate(inf, 1):
                if not line.strip():
                    continue
                try:
                    ex = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ⚠️ Skipping malformed JSON on line {ln}: {e}")
                    continue
                input_messages = ex["input"]["messages"]
                chosen_messages = ex["preferred_output"]

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                    messages.extend(m for m in input_messages if m["role"] != "system")
                else:
                    messages.extend(input_messages)
                messages.extend(chosen_messages)
                f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
                count += 1
    print(f"Extracted {count} chosen examples to SFT JSONL → {output_path}")


def main():
    parser = HelpOnErrorParser(description="Convert between fine-tuning dataset formats")
    parser.add_argument("--input", required=True, help="Input file path")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--format", required=True,
                        choices=["sft", "dpo", "rft", "sft-from-dpo"],
                        help="Target format")

    # SFT from raw data
    parser.add_argument("--user-column", default="prompt", help="Column name for user input")
    parser.add_argument("--assistant-column", default="response", help="Column name for assistant output")
    parser.add_argument("--system-prompt", default=None, help="System prompt to prepend")

    # DPO generation (needs API connection)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="Project /v1/ URL (preferred)")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint (Foundry SDK)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--base-model", default="gpt-4.1-mini", help="Base model for generating rejections")

    args = parser.parse_args()

    if args.format == "sft":
        if args.input.endswith(".jsonl"):
            print("Input is already JSONL — assuming SFT format. Nothing to convert.")
            if args.input != args.output:
                import shutil
                shutil.copy2(args.input, args.output)
        else:
            parquet_to_sft(args.input, args.output, args.user_column,
                           args.assistant_column, args.system_prompt)

    elif args.format == "dpo":
        client, method = get_clients(
            base_url=args.base_url, azure_endpoint=args.endpoint,
            project_endpoint=args.project_endpoint, api_key=args.api_key
        )
        sft_to_dpo(args.input, args.output, client, args.base_model)

    elif args.format == "rft":
        sft_to_rft(args.input, args.output)

    elif args.format == "sft-from-dpo":
        dpo_to_sft(args.input, args.output, args.system_prompt)


if __name__ == "__main__":
    main()
