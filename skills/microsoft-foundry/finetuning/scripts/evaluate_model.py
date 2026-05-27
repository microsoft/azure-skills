# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
# ]
# ///
"""
evaluate_model.py — Custom 2-dimension LLM judge evaluator for fine-tuned models.

This is a lightweight evaluation script using the OpenAI API directly.
For production evaluation, prefer the Azure AI Evaluation SDK which provides
built-in graders, batch evaluation, and guardrail metrics. See
references/evaluation.md for SDK patterns.

Uses the OpenAI API directly to:
1. Generate responses from a deployed fine-tuned model
2. Grade each response on correctness and conciseness using an LLM judge
3. Produce aggregate quality scores (weighted 70% correctness, 30% conciseness)

By default, system prompts from each test example's messages array are used
during generation. The --system-prompt flag overrides this for all examples.

Usage:
  python evaluate_model.py \
      --deployment-name my-ft-eval \
      --test-file test.jsonl \
      --judge-model gpt-4o \
      --output results.json

  python evaluate_model.py \
      --base-url "$BASE_URL" --api-key "$API_KEY" \
      --deployment-name my-ft-eval \
      --test-file test.jsonl \
      --concurrency 4
"""

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients, _clamp_score


JUDGE_PROMPT = """You are evaluating the quality of a model's output for a given task.

## Task prompt
{prompt}

## Reference answer
{reference}

## Model output
{output}

## Scoring

Rate the output on two dimensions, each on a scale of 1-10:

**Correctness** (1-10): Does the output correctly accomplish the task?
- 1-3: Fundamentally wrong or broken
- 4-6: Partially correct with significant issues
- 7-8: Mostly correct with minor issues
- 9-10: Fully correct

**Conciseness** (1-10): Is the output appropriately concise?
- 1-3: Extremely verbose or padded
- 4-6: Contains unnecessary content
- 7-8: Mostly concise with minor excess
- 9-10: Clean and focused

Return ONLY a JSON object: {{"correctness": <int>, "conciseness": <int>}}"""


def load_test_data(filepath):
    """Load held-out test set. Expects JSONL with 'messages' array.

    Extracts the system prompt (if present), user prompt, and assistant
    reference from each example so per-example system prompts are preserved.
    """
    data = []
    with open(filepath, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                ex = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️ Skipping malformed JSON on line {i+1}: {e}")
                continue
            msgs = ex.get("messages")
            if not isinstance(msgs, list):
                print(f"⚠️ Skipping example {i}: missing or invalid 'messages' list")
                continue
            prompt = next((m["content"] for m in msgs if m["role"] == "user"), None)
            reference = next((m["content"] for m in msgs if m["role"] == "assistant"), None)
            if not prompt:
                print(f"⚠️ Skipping example {i}: missing 'user' message")
                continue
            if not reference:
                print(f"⚠️ Skipping example {i}: missing 'assistant' message")
                continue
            system_msgs = [m["content"] for m in msgs if m["role"] == "system"]
            system_prompt = system_msgs[0] if system_msgs else None
            data.append({"prompt": prompt, "reference": reference, "system_prompt": system_prompt})
    return data


def generate_response(client, deployment, prompt, system_prompt=None, max_retries=3):
    """Generate a single response from the deployed model."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=0.0,
                max_completion_tokens=2048,
            )
            content = resp.choices[0].message.content
            if content is None:
                # Content filter or empty completion — surface as an error sentinel
                # so the aggregate filter at line ~`.startswith("ERROR:")` skips it.
                finish = getattr(resp.choices[0], "finish_reason", "unknown")
                return f"ERROR: empty content (finish_reason={finish})"
            return content
        except Exception as e:
            if attempt >= max_retries - 1:
                return f"ERROR: {e}"
            time.sleep(3 * (attempt + 1))
    return "ERROR: max retries exceeded"


def grade_response(judge_client, judge_model, prompt, reference, output, max_retries=3):
    """Grade a response using the LLM judge."""
    judge_input = JUDGE_PROMPT.format(prompt=prompt, reference=reference, output=output)

    for attempt in range(max_retries):
        try:
            resp = judge_client.chat.completions.create(
                model=judge_model,
                messages=[{"role": "user", "content": judge_input}],
                temperature=0.0,
                max_completion_tokens=200,
            )
            text = (resp.choices[0].message.content or "").strip()
            # Extract JSON from response
            match = re.search(r'\{[^}]+\}', text)
            if match:
                scores = json.loads(match.group())
                return {
                    "correctness": _clamp_score(scores.get("correctness")),
                    "conciseness": _clamp_score(scores.get("conciseness")),
                }
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return {"correctness": 0, "conciseness": 0, "error": str(e)}

    return {"correctness": 0, "conciseness": 0, "error": "All retries failed"}


def main():
    parser = HelpOnErrorParser(description="Evaluate a fine-tuned model with LLM judge")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="Project /v1/ URL (preferred)")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint (Foundry SDK)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--deployment-name", required=True, help="Deployed model name")
    parser.add_argument("--test-file", required=True, help="Held-out test set (JSONL)")
    parser.add_argument("--system-prompt", default=None,
                        help="Override system prompt for all examples (default: use per-example system prompt from test data)")

    # Judge config
    parser.add_argument("--judge-model", default="gpt-4o", help="Model for LLM judge")
    parser.add_argument("--judge-endpoint", help="Endpoint for judge (default: same as model)")
    parser.add_argument("--judge-api-key", help="API key for judge (default: same as model)")

    # Output
    parser.add_argument("--output", default="eval_results.json", help="Output file")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Parallel grading workers (generation is always sequential)")

    args = parser.parse_args()

    # Set up model client via shared auth (supports /v1/, Foundry SDK, AzureOpenAI)
    model_client, method = get_clients(
        base_url=args.base_url, azure_endpoint=args.endpoint,
        project_endpoint=args.project_endpoint, api_key=args.api_key
    )

    # Set up judge client (defaults to same connection as model)
    judge_key = args.judge_api_key or args.api_key
    if args.judge_endpoint:
        judge_client, _ = get_clients(azure_endpoint=args.judge_endpoint, api_key=judge_key)
    elif args.judge_api_key:
        # Different API key but same endpoint — create a new client with the judge key
        judge_client, _ = get_clients(
            base_url=args.base_url, azure_endpoint=args.endpoint,
            project_endpoint=args.project_endpoint, api_key=judge_key
        )
    else:
        judge_client = model_client

    # Load data
    test_data = load_test_data(args.test_file)
    print(f"Loaded {len(test_data)} test examples from {args.test_file}")

    # Phase 1: Generate responses (sequential to avoid rate limits)
    print(f"\nGenerating responses from {args.deployment_name}...")
    for i, ex in enumerate(test_data):
        # Use CLI override if provided, otherwise use per-example system prompt
        effective_system_prompt = args.system_prompt if args.system_prompt is not None else ex.get("system_prompt")
        ex["output"] = generate_response(
            model_client, args.deployment_name, ex["prompt"], effective_system_prompt
        )
        if (i + 1) % 10 == 0:
            print(f"  Generated {i+1}/{len(test_data)}")

    errors = sum(1 for ex in test_data if ex["output"].startswith("ERROR:"))
    print(f"  Done. {errors} errors out of {len(test_data)}.")

    # Phase 2: Grade responses (parallel)
    print(f"\nGrading with {args.judge_model} (concurrency={args.concurrency})...")

    def grade_one(ex):
        return grade_response(judge_client, args.judge_model,
                              ex["prompt"], ex["reference"], ex["output"])

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(grade_one, ex): i for i, ex in enumerate(test_data)}
        for future in as_completed(futures):
            idx = futures[future]
            test_data[idx]["scores"] = future.result()

    # Aggregate
    valid_scores = [ex["scores"] for ex in test_data
                    if ex["scores"]["correctness"] > 0]
    if not valid_scores:
        print("No valid scores — all grading failed.")
        sys.exit(1)

    avg_corr = sum(s["correctness"] for s in valid_scores) / len(valid_scores)
    avg_conc = sum(s["conciseness"] for s in valid_scores) / len(valid_scores)
    combined = 0.7 * avg_corr + 0.3 * avg_conc

    print(f"\n{'='*50}")
    print(f"Results for {args.deployment_name}")
    print(f"  Correctness:  {avg_corr:.2f}")
    print(f"  Conciseness:  {avg_conc:.2f}")
    print(f"  Combined:     {combined:.2f}")
    print(f"  (N={len(valid_scores)} scored, {len(test_data)-len(valid_scores)} failed)")
    print(f"{'='*50}")

    # Save
    results = {
        "deployment": args.deployment_name,
        "judge_model": args.judge_model,
        "n_examples": len(test_data),
        "n_scored": len(valid_scores),
        "correctness": round(avg_corr, 2),
        "conciseness": round(avg_conc, 2),
        "combined": round(combined, 2),
        "details": [
            {
                "prompt": ex["prompt"][:200],
                "scores": ex.get("scores", {}),
            }
            for ex in test_data
        ],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to {args.output}")


if __name__ == "__main__":
    main()
