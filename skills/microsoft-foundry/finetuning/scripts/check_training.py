# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
#   "azure-ai-projects",
# ]
# ///
"""
check_training.py — Analyze training curves, detect overfitting, list checkpoints.

Usage:
  python check_training.py --job-id ftjob-abc123
  python check_training.py --job-id ftjob-abc123 --download-csv results.csv
  python check_training.py --base-url https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/ --api-key KEY --job-id ftjob-abc123
"""

import csv
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients


def analyze_job(client, job_id, download_csv=None):
    """Pull training results, analyze curves, detect overfitting."""
    job = client.fine_tuning.jobs.retrieve(job_id)

    print(f"Job: {job.id}")
    print(f"  Model: {job.model}")
    print(f"  Status: {job.status}")
    print(f"  Fine-tuned model: {job.fine_tuned_model}")

    if job.hyperparameters:
        hp = job.hyperparameters
        print(f"  Epochs: {getattr(hp, 'n_epochs', 'N/A')}")
        print(f"  LR multiplier: {getattr(hp, 'learning_rate_multiplier', 'N/A')}")
        print(f"  Batch size: {getattr(hp, 'batch_size', 'N/A')}")

    # Allow analysis while still running if result files exist
    if job.status not in ("succeeded", "running"):
        print(f"\n  Job status is '{job.status}'. Cannot analyze curves.")
        return

    if not job.result_files:
        if job.status == "running":
            print("\n  Job is still running and no result files available yet. Check back later.")
        else:
            print("\n  No result files available.")
        return

    # Download results CSV
    content = client.files.content(job.result_files[0])
    csv_data = content.read()

    if download_csv:
        with open(download_csv, "wb") as f:
            f.write(csv_data)
        print(f"\n  Results CSV saved to {download_csv}")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_data.decode("utf-8")))
    rows = list(reader)

    if job.status == "running":
        print(f"\n  ⚡ Job still running — showing partial results ({len(rows)} steps so far)")

    # Extract validation checkpoints
    val_points = []
    for row in rows:
        step = int(row.get("step", 0))
        train_loss = float(row["train_loss"]) if row.get("train_loss", "").strip() else None
        val_loss = None
        for col in ["valid_loss", "full_valid_loss", "eval_loss"]:
            if row.get(col, "").strip():
                val_loss = float(row[col])
                break

        if val_loss is not None:
            val_points.append((step, val_loss, train_loss))

    if not val_points:
        print("\n  No validation loss data found in results CSV.")
        return

    # Find best validation checkpoint
    best_step, best_val, best_train = min(val_points, key=lambda x: x[1])
    final_step, final_val, final_train = val_points[-1]

    print(f"\n  Training Curve Analysis:")
    print(f"  {'Step':>6} {'Val Loss':>10} {'Train Loss':>12} {'Ratio':>8}")
    print(f"  {'─'*6} {'─'*10} {'─'*12} {'─'*8}")
    for step, val, train in val_points:
        ratio = val / train if train and train > 0 else 0
        marker = " ← best" if step == best_step else ""
        train_str = f"{train:12.4f}" if train is not None else "         N/A"
        print(f"  {step:>6} {val:>10.4f} {train_str} {ratio:>8.2f}{marker}")

    print(f"\n  Best val_loss: {best_val:.4f} at step {best_step}")
    print(f"  Final val_loss: {final_val:.4f} at step {final_step}")

    # Overfitting detection
    if best_val > 0 and final_val > best_val * 1.2:
        pct = (final_val - best_val) / best_val * 100
        print(f"\n  ⚠️  OVERFITTING DETECTED: Final val_loss is {pct:.0f}% above best.")
    elif best_val == 0 and final_val > 0:
        print(f"\n  ⚠️  Best val_loss was 0.0; final val_loss is {final_val:.4f} — possible overfitting from a near-perfect early checkpoint.")
    elif final_train and final_val / final_train > 1.5:
        ratio = final_val / final_train
        print(f"\n  ⚠️  MODERATE OVERFITTING: val/train ratio = {ratio:.2f}")
    else:
        print(f"\n  ✅ Training looks healthy. No significant overfitting detected.")

    # List checkpoints and recommend best deployable one
    print(f"\n  Checkpoints:")
    available_checkpoints = []
    try:
        cps = client.fine_tuning.jobs.checkpoints.list(job_id)
        if cps.data:
            for cp in sorted(cps.data, key=lambda c: c.step_number):
                vl = cp.metrics.valid_loss if cp.metrics and cp.metrics.valid_loss is not None else None
                model_id = cp.fine_tuned_model_checkpoint or "N/A"
                vl_str = f"{vl:.4f}" if vl is not None else "N/A"
                available_checkpoints.append((cp.step_number, vl, model_id))
                print(f"    Step {cp.step_number}: val_loss={vl_str}, model={model_id}")
        else:
            print("    No checkpoints available.")
    except Exception as e:
        print(f"    Could not retrieve checkpoints: {e}")

    # Recommend the best deployable checkpoint
    if available_checkpoints and best_val > 0 and final_val > best_val * 1.2:
        # Find the checkpoint with the lowest val_loss, or nearest to best_step
        best_cp = None
        if any(vl is not None for _, vl, _ in available_checkpoints):
            # Use checkpoint with lowest val_loss
            scored_cps = [(s, vl, m) for s, vl, m in available_checkpoints if vl is not None]
            if scored_cps:
                best_cp = min(scored_cps, key=lambda x: x[1])
        else:
            # No val_loss on checkpoints — pick the one nearest to (but not exceeding) best_step
            earlier_cps = [(s, vl, m) for s, vl, m in available_checkpoints if s <= best_step]
            if earlier_cps:
                best_cp = max(earlier_cps, key=lambda x: x[0])
            elif available_checkpoints:
                best_cp = available_checkpoints[0]

        if best_cp:
            cp_step, cp_vl, cp_model = best_cp
            vl_info = f" (val_loss={cp_vl:.4f})" if cp_vl is not None else ""
            print(f"\n  🎯 Recommended checkpoint: step {cp_step}{vl_info}")
            print(f"     Model ID: {cp_model}")
            print(f"     (Best val_loss was at step {best_step}, nearest deployable checkpoint is step {cp_step})")
            print(f"     Alternatively, retrain with fewer epochs to avoid overfitting.")
        else:
            print(f"\n  Recommendation: Retrain with fewer epochs (best val_loss was at step {best_step}).")


def main():
    parser = HelpOnErrorParser(description="Analyze fine-tuning training curves")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="Project /v1/ URL (preferred)")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint (Foundry SDK)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--job-id", required=True, help="Fine-tuning job ID")
    parser.add_argument("--download-csv", help="Save results CSV to this path")
    args = parser.parse_args()

    client, method = get_clients(
        base_url=args.base_url, azure_endpoint=args.endpoint,
        project_endpoint=args.project_endpoint, api_key=args.api_key
    )
    analyze_job(client, args.job_id, args.download_csv)


if __name__ == "__main__":
    main()
