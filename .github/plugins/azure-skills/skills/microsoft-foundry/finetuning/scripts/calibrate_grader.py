# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
#   "azure-ai-projects",
# ]
# ///
"""
calibrate_grader.py — Calibrate RFT grader pass_threshold before submitting a job.

Runs the base model on your training/validation data, scores each output
with your Python grader, and recommends the optimal pass_threshold.

Usage:
  python calibrate_grader.py --base-url <url> --api-key KEY \
      --model o4-mini --data train.jsonl --grader grader.py --n 30

  python calibrate_grader.py --model gpt-4.1-mini --data val.jsonl \
      --grader grader.py --n 20 --tools '[{"name": "search", "server_url": "https://..."}]'
"""

import argparse
import json
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients


def load_grader(grader_path):
    """Load and compile a Python grader file. Returns the grade() function.

    SECURITY: This executes the grader file as Python code. Only load grader
    files that you wrote or reviewed — never load untrusted files from the
    internet or unknown sources. The grader runs with the same permissions as
    this script.
    """
    grader_path = os.path.abspath(grader_path)
    if not os.path.isfile(grader_path):
        print(f"❌ Grader file not found: {grader_path}")
        sys.exit(1)
    with open(grader_path, encoding="utf-8") as f:
        source = f.read()
    namespace = {}
    exec(compile(source, grader_path, "exec"), namespace)
    if "grade" not in namespace:
        print(f"❌ Grader file must define a grade(sample, item) function")
        sys.exit(1)
    return namespace["grade"]


def run_model(client, model, messages, tools_schema=None, max_retries=3):
    """Run the model and return (output_text, output_tools)."""
    kwargs = {"model": model, "messages": messages, "max_completion_tokens": 4096}
    if tools_schema:
        kwargs["tools"] = tools_schema

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            output_text = msg.content or ""
            output_tools = []
            if msg.tool_calls:
                output_tools = [
                    {"type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            return output_text, output_tools
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                return f"ERROR: {e}", []
    return "ERROR: max retries", []


def calibrate(client, model, data, grade_fn, tools_schema=None, n=30):
    """Run base model on data, score with grader, output threshold analysis."""
    if not data:
        print("No examples to evaluate. Check your data file.")
        return

    # Sample if dataset is larger than n
    if len(data) > n:
        data = random.sample(data, n)

    print(f"Running {model} on {len(data)} examples...\n")

    scores = []
    for i, ex in enumerate(data):
        messages = ex["messages"]
        user_msg = messages[-1]["content"] if messages else ""

        output_text, output_tools = run_model(client, model, messages, tools_schema)

        if output_text.startswith("ERROR:"):
            print(f"  [{i+1:3d}] ❌ {output_text[:60]}")
            scores.append(0.0)
            continue

        # Build sample dict matching what the grader expects
        sample = {"output_text": output_text, "output_tools": output_tools}

        # Build item dict from all fields in the training example
        item = {k: v for k, v in ex.items() if k != "messages"}

        try:
            score = grade_fn(sample, item)
        except Exception as e:
            print(f"  [{i+1:3d}] ❌ Grader error: {e}")
            scores.append(0.0)
            continue

        status = "✅" if score >= 0.9 else ("⚠️" if score >= 0.5 else "❌")
        print(f"  [{i+1:3d}] {score:.3f} {status}  {user_msg[:55]}")
        scores.append(score)

        time.sleep(0.5)  # Rate limiting

    # Analysis
    scored = [s for s in scores if s is not None]
    if not scored:
        print("\n❌ No examples were scored successfully. Check model access and data format.")
        return
    avg = sum(scored) / len(scored)
    print(f"\n{'='*60}")
    print(f"  BASE MODEL GRADER CALIBRATION ({len(scores)} examples)")
    print(f"  Average score: {avg:.1%}")
    print(f"{'='*60}")

    print(f"\n  {'Threshold':>10} {'Pass Rate':>10} {'Fail Rate':>10} {'Signal':>20}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*20}")

    best_threshold = None
    best_distance = float("inf")

    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]:
        pass_rate = sum(1 for s in scored if s >= threshold) / len(scored)
        fail_rate = 1 - pass_rate

        if 0.25 <= fail_rate <= 0.50:
            signal = "✅ Good (25-50%)"
            distance = abs(fail_rate - 0.35)  # Ideal is ~35%
            if distance < best_distance:
                best_distance = distance
                best_threshold = threshold
        elif fail_rate < 0.10:
            signal = "❌ Too easy"
        elif fail_rate < 0.25:
            signal = "⚠️ Weak signal"
        elif fail_rate <= 0.70:
            signal = "⚠️ Harsh"
        else:
            signal = "❌ Too hard"

        print(f"  {threshold:>10.2f} {pass_rate:>9.0%} {fail_rate:>9.0%} {signal:>20}")

    if best_threshold:
        print(f"\n  ✅ Recommended pass_threshold: {best_threshold}")
        print(f"     (~{sum(1 for s in scores if s < best_threshold)/len(scores):.0%} failure rate)")
    else:
        print(f"\n  ⚠️ No threshold in the ideal 25-50% failure range.")
        print(f"     Consider adjusting your grader scoring dimensions.")

    # Score distribution
    print(f"\n  Score distribution:")
    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
    for s in scores:
        if s < 0.2: buckets["0.0-0.2"] += 1
        elif s < 0.4: buckets["0.2-0.4"] += 1
        elif s < 0.6: buckets["0.4-0.6"] += 1
        elif s < 0.8: buckets["0.6-0.8"] += 1
        elif s < 0.9: buckets["0.8-0.9"] += 1
        else: buckets["0.9-1.0"] += 1
    for bucket, count in buckets.items():
        bar = "█" * count
        print(f"    {bucket}: {count:3d} {bar}")


def build_parser():
    parser = HelpOnErrorParser(
        description="Calibrate RFT grader pass_threshold on base model outputs",
        epilog=(
            "Example:\n"
            "  python calibrate_grader.py --model o4-mini --data train.jsonl --grader grader.py\n"
            "  python calibrate_grader.py --model o4-mini --data val.jsonl --grader grader.py --n 20"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"), help="Project /v1/ endpoint URL")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"), help="API key")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint")
    parser.add_argument("--model", required=True, help="Base model deployment name to calibrate against")
    parser.add_argument("--data", required=True, help="Path to training or validation JSONL file")
    parser.add_argument("--grader", required=True, help="Path to Python grader file (must define grade(sample, item))")
    parser.add_argument("--n", type=int, default=30, help="Number of examples to evaluate (default: 30)")
    parser.add_argument("--tools", default=None,
                        help="Tool schemas as JSON array (for tool-calling models). Pass as a JSON string.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling (default: 42)")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    random.seed(args.seed)

    client, method = get_clients(base_url=args.base_url, azure_endpoint=args.endpoint, project_endpoint=args.project_endpoint, api_key=args.api_key)

    # Load data
    with open(args.data, encoding="utf-8") as f:
        data = []
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️ Skipping malformed JSON on line {ln}: {e}")
    print(f"Loaded {len(data)} examples from {args.data}")

    # Load grader
    grade_fn = load_grader(args.grader)
    print(f"Loaded grader from {args.grader}")

    # Parse tools if provided
    tools_schema = None
    if args.tools:
        tools_schema = json.loads(args.tools)

    calibrate(client, args.model, data, grade_fn, tools_schema, args.n)
