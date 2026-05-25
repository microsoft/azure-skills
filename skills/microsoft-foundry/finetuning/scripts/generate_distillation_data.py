# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
# ]
# ///
"""
generate_distillation_data.py — Generate training data from a teacher model for distillation.

Creates a synthetic SFT dataset by:
1. Generating diverse prompts from combinatorial axes (topics × formats × contexts)
2. Having the teacher model produce responses
3. Quality-grading each response with an LLM judge
4. Filtering low-quality examples
5. Splitting into train/val/test JSONL files

Usage:
  python generate_distillation_data.py \
      --teacher gpt-4.1-mini \
      --system-prompt "You are a formal business writer." \
      --topics "earnings,risk,compliance" \
      --num-prompts 300 \
      --min-score 7.0 \
      --output-dir ./my_dataset

  # Or with a prompts file (one prompt per line):
  python generate_distillation_data.py \
      --teacher gpt-4.1-mini \
      --prompts-file my_prompts.txt \
      --output-dir ./my_dataset
"""

import json
import os
import random
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients, _clamp_score

import openai


def verify_deployment(client, model):
    """Verify a model deployment exists by sending a trivial request."""
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_completion_tokens=1,
        )
        return True
    except openai.NotFoundError:
        return False
    except Exception:
        return True  # other errors (rate limit, etc.) mean the deployment exists


def generate_combinatorial_prompts(topics, formats, contexts, n):
    """Generate diverse prompts from combinatorial axes."""
    prompts = []
    for _ in range(n):
        t = random.choice(topics)
        f = random.choice(formats)
        c = random.choice(contexts)
        prompts.append(f"Context: {c}\n\nWrite {f} about: {t}.")
    return prompts


def teacher_generate(client, model, system_prompt, prompt, retries=3):
    """Generate a single response from the teacher."""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_completion_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt >= retries - 1:
                print(f"  Failed after {retries} attempts: {e}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


QUALITY_PROMPT = """Rate this AI-generated text on quality dimensions (1-10 each).

## Text to evaluate
{output}

## Dimensions
**Accuracy** (1-10): Is the content factually sound and coherent?
**Quality** (1-10): Is it well-written, clear, and professional?
**Task-fit** (1-10): Does it match the requested format and purpose?

Return ONLY JSON: {{"accuracy": <int>, "quality": <int>, "task_fit": <int>}}"""


def grade_output(client, judge_model, output, retries=3):
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=judge_model,
                messages=[{"role": "user", "content": QUALITY_PROMPT.format(output=output)}],
                temperature=0.0,
                max_completion_tokens=100,
            )
            text = (resp.choices[0].message.content or "").strip()
            match = re.search(r'\{[^}]+\}', text)
            if match:
                scores = json.loads(match.group())
                return {k: _clamp_score(v) for k, v in scores.items()}
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def main():
    parser = HelpOnErrorParser(description="Generate distillation training data from a teacher model")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="Project /v1/ URL (preferred)")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint (Foundry SDK)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--teacher", required=True, help="Teacher model deployment name")
    parser.add_argument("--judge", default=None, help="Judge model (default: same as teacher)")
    parser.add_argument("--system-prompt", default="You are a helpful assistant.", help="System prompt for teacher")

    # Prompt generation (either combinatorial or from file)
    parser.add_argument("--prompts-file", help="File with one prompt per line (skips combinatorial generation)")
    parser.add_argument("--topics", help="Comma-separated topics for combinatorial prompts")
    parser.add_argument("--formats", default="a concise response,a brief summary,a detailed explanation",
                        help="Comma-separated output formats")
    parser.add_argument("--contexts", default="", help="Comma-separated context sentences")
    parser.add_argument("--num-prompts", type=int, default=300, help="Number of prompts to generate")

    # Quality
    parser.add_argument("--min-score", type=float, default=7.0, help="Minimum average quality score to keep")
    parser.add_argument("--skip-grading", action="store_true", help="Skip quality grading (keep all)")

    # Output
    parser.add_argument("--output-dir", default="./distillation_data", help="Output directory")
    parser.add_argument("--train-split", type=float, default=0.8)
    parser.add_argument("--val-split", type=float, default=0.1)

    args = parser.parse_args()

    client, method = get_clients(
        base_url=args.base_url, azure_endpoint=args.endpoint,
        project_endpoint=args.project_endpoint, api_key=args.api_key
    )
    judge = args.judge or args.teacher

    # Step 0: Verify deployments exist
    print(f"Verifying deployment '{args.teacher}'...")
    if not verify_deployment(client, args.teacher):
        print(f"  ERROR: Deployment '{args.teacher}' not found. Available deployments can be listed in Azure Portal.")
        sys.exit(1)
    print(f"  ✅ Teacher deployment verified.")

    if judge != args.teacher:
        print(f"Verifying judge deployment '{judge}'...")
        if not verify_deployment(client, judge):
            print(f"  ERROR: Judge deployment '{judge}' not found.")
            sys.exit(1)
        print(f"  ✅ Judge deployment verified.")

    # Step 1: Generate or load prompts
    if args.prompts_file:
        with open(args.prompts_file, encoding="utf-8") as pf:
            prompts = [line.strip() for line in pf if line.strip()]
        print(f"Loaded {len(prompts)} prompts from {args.prompts_file}")
    else:
        topics = [t.strip() for t in (args.topics or "general knowledge").split(",")]
        formats = [f.strip() for f in args.formats.split(",")]
        contexts = [c.strip() for c in args.contexts.split(",") if c.strip()] or [""]
        prompts = generate_combinatorial_prompts(topics, formats, contexts, args.num_prompts)
        print(f"Generated {len(prompts)} prompts ({len(topics)} topics × {len(formats)} formats × {len(contexts)} contexts)")

    # Step 2: Teacher generates responses
    print(f"\nTeacher ({args.teacher}) generating responses...")
    examples = []
    for i, prompt in enumerate(prompts):
        response = teacher_generate(client, args.teacher, args.system_prompt, prompt)
        if response:
            examples.append({"prompt": prompt, "response": response})
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(prompts)} ({len(examples)} successful)")
    print(f"  Teacher produced {len(examples)}/{len(prompts)} responses")

    # Step 3: Quality grade and filter
    if not args.skip_grading:
        print(f"\nGrading with {judge}...")
        for i, ex in enumerate(examples):
            scores = grade_output(client, judge, ex["response"])
            if scores:
                ex["scores"] = scores
                ex["avg_score"] = sum(scores.values()) / len(scores)
            else:
                ex["avg_score"] = 0
            if (i + 1) % 25 == 0:
                print(f"  Graded {i+1}/{len(examples)}")

        filtered = [ex for ex in examples if ex["avg_score"] >= args.min_score]
        avgs = [ex["avg_score"] for ex in examples if ex["avg_score"] > 0]
        print(f"  Passed filter (>= {args.min_score}): {len(filtered)}/{len(examples)}")
        if avgs:
            print(f"  Scores: min={min(avgs):.1f}, max={max(avgs):.1f}, mean={sum(avgs)/len(avgs):.1f}")
    else:
        filtered = examples
        print(f"Skipping grading — keeping all {len(filtered)} examples")

    # Step 4: Convert to SFT format and split
    sft_data = [{"messages": [
        {"role": "system", "content": args.system_prompt},
        {"role": "user", "content": ex["prompt"]},
        {"role": "assistant", "content": ex["response"]},
    ]} for ex in filtered]

    random.shuffle(sft_data)
    n = len(sft_data)
    t_end = int(n * args.train_split)
    v_end = int(n * (args.train_split + args.val_split))
    splits = {"train": sft_data[:t_end], "validation": sft_data[t_end:v_end], "test": sft_data[v_end:]}

    os.makedirs(args.output_dir, exist_ok=True)
    for name, data in splits.items():
        path = os.path.join(args.output_dir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for ex in data:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(data)} examples → {path}")

    print(f"\n✅ Done! Dataset ready in {args.output_dir}/")


if __name__ == "__main__":
    main()
