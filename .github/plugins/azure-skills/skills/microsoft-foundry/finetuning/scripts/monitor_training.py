# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
#   "azure-ai-projects",
# ]
# ///
"""
monitor_training.py — Monitor a fine-tuning job until completion.

Polls the job status and streams training events (reward, loss, errors)
in real time. Exits when the job reaches a terminal state.

Usage:
  python monitor_training.py --job-id ftjob-abc123
  python monitor_training.py --base-url https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/ --api-key KEY --job-id ftjob-abc123
  python monitor_training.py --job-id ftjob-abc123 --poll-interval 30
"""

import argparse
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

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def monitor_job(client, job_id, poll_interval=15):
    """Poll a fine-tuning job until it reaches a terminal state."""
    # Cap memory for long-running jobs (RFT can run hours/days, accumulating thousands of events)
    seen_events = set()
    MAX_SEEN_EVENTS = 5000

    print(f"Monitoring job: {job_id}")
    print(f"Polling every {poll_interval}s. Ctrl+C to stop.\n")

    while True:
        try:
            job = client.fine_tuning.jobs.retrieve(job_id)
        except Exception as e:
            print(f"⚠️ Error retrieving job: {e}")
            time.sleep(poll_interval)
            continue

        status = (job.status or "").lower()

        # Fetch and display new events
        try:
            events = list(client.fine_tuning.jobs.list_events(job_id, limit=20))
            for event in reversed(events):
                event_key = (event.created_at, event.message)
                if event_key not in seen_events:
                    if len(seen_events) >= MAX_SEEN_EVENTS:
                        # Keep only the most recent half — a fully-flushed dedup window
                        # would risk re-printing old events on transient API hiccups, but
                        # without trimming this set grows unbounded for long RFT runs.
                        seen_events = set(list(seen_events)[-(MAX_SEEN_EVENTS // 2):])
                    seen_events.add(event_key)
                    ts = time.strftime("%H:%M:%S", time.localtime(event.created_at))
                    level = event.level or "info"

                    # Highlight step events
                    if "Step" in event.message and "reward" in event.message:
                        print(f"  📈 [{ts}] {event.message}")
                    elif "Step" in event.message and "loss" in event.message:
                        print(f"  📉 [{ts}] {event.message}")
                    elif "error" in event.message.lower() or level == "error":
                        print(f"  ❌ [{ts}] {event.message}")
                    elif "started" in event.message.lower() or "completed" in event.message.lower():
                        print(f"  🔔 [{ts}] {event.message}")
                    else:
                        print(f"  ℹ️ [{ts}] {event.message}")
        except Exception:
            pass  # Events API may not be available for all job states

        # Check terminal state
        if status in TERMINAL_STATUSES:
            print(f"\n{'='*50}")
            if status == "succeeded":
                model = job.fine_tuned_model or "unknown"
                print(f"  ✅ Job succeeded!")
                print(f"  Fine-tuned model: {model}")
                if job.trained_tokens:
                    print(f"  Trained tokens: {job.trained_tokens:,}")
            elif status == "failed":
                print(f"  ❌ Job failed.")
                if hasattr(job, "error") and job.error:
                    print(f"  Error: {job.error}")
            elif status == "cancelled":
                print(f"  ⚠️ Job was cancelled.")
            print(f"{'='*50}")
            return status

        time.sleep(poll_interval)


def build_parser():
    parser = HelpOnErrorParser(
        description="Monitor a fine-tuning job until completion",
        epilog=(
            "Example:\n"
            "  python monitor_training.py --job-id ftjob-abc123\n"
            "  python monitor_training.py --base-url https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/ --api-key KEY --job-id ftjob-abc123"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"), help="Project /v1/ endpoint URL")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"), help="API key")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint (alternative to --base-url)")
    parser.add_argument("--job-id", required=True, help="Fine-tuning job ID (e.g., ftjob-abc123)")
    parser.add_argument("--poll-interval", type=int, default=15, help="Seconds between status checks (default: 15)")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    client, method = get_clients(base_url=args.base_url, azure_endpoint=args.endpoint, project_endpoint=args.project_endpoint, api_key=args.api_key)
    status = monitor_job(client, args.job_id, args.poll_interval)
    sys.exit(0 if status == "succeeded" else 1)
