# /// script
# dependencies = [
#   "openai>=1.0",
#   "azure-identity",
#   "azure-ai-projects",
# ]
# ///
"""
cleanup.py — Clean up fine-tuning resources to avoid quota exhaustion.

Lists and optionally deletes uploaded files and cancels pending jobs.
Useful after experimentation to reclaim quota (max 100 files per resource,
deployment slots are limited).

Usage:
  python cleanup.py --list                            # List all resources
  python cleanup.py --list --type files               # List only files
  python cleanup.py --delete-files --older-than 7     # Delete files older than 7 days
  python cleanup.py --delete-files --dry-run          # Preview what would be deleted
  python cleanup.py --cancel-pending                  # Cancel queued jobs
"""

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser, get_clients


def list_deployments(client):
    """List fine-tuned model deployments. Returns deployment info from jobs."""
    deployments = []
    for job in _iter_all_jobs(client):
        if job.fine_tuned_model and job.status == "succeeded":
            deployments.append({
                "job_id": job.id,
                "model": job.fine_tuned_model,
                "base_model": job.model,
                "created": datetime.fromtimestamp(job.created_at, tz=timezone.utc),
                "tokens": job.trained_tokens,
            })
    return deployments


def _iter_all_jobs(client, page_size=100):
    """Yield every fine-tuning job, paginating through the API.

    The OpenAI/Azure SDK's `jobs.list(limit=N)` returns at most N jobs with no
    auto-paging. Users with >100 jobs would otherwise miss older jobs entirely.
    """
    after = None
    while True:
        kwargs = {"limit": page_size}
        if after:
            kwargs["after"] = after
        page = client.fine_tuning.jobs.list(**kwargs)
        items = list(page)
        if not items:
            break
        for job in items:
            yield job
        if len(items) < page_size:
            break
        # Cursor-based paging: use last job's id as `after`
        after = items[-1].id


def list_files(client):
    """List uploaded files."""
    files = client.files.list()
    result = []
    for f in files:
        result.append({
            "id": f.id,
            "filename": f.filename,
            "purpose": f.purpose,
            "bytes": f.bytes,
            "created": datetime.fromtimestamp(f.created_at, tz=timezone.utc),
            "status": f.status,
        })
    return result


def list_jobs(client):
    """List fine-tuning jobs."""
    result = []
    for job in _iter_all_jobs(client):
        result.append({
            "id": job.id,
            "status": job.status,
            "model": job.model,
            "fine_tuned_model": job.fine_tuned_model or "—",
            "created": datetime.fromtimestamp(job.created_at, tz=timezone.utc),
        })
    return result


def format_age(dt):
    """Format a datetime as a human-readable age."""
    delta = datetime.now(timezone.utc) - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    return f"{hours}h ago"


def format_bytes(b):
    """Format bytes as human-readable size."""
    if not b:
        return "—"
    if b > 1_000_000:
        return f"{b/1_000_000:.1f} MB"
    if b > 1_000:
        return f"{b/1_000:.0f} KB"
    return f"{b} B"


def show_list(client, resource_type="all"):
    """Display current resources."""
    if resource_type in ("all", "jobs"):
        jobs = list_jobs(client)
        print(f"\n📋 Fine-tuning jobs ({len(jobs)}):")
        if jobs:
            print(f"  {'ID':<25} {'Status':<12} {'Model':<20} {'Age':<10}")
            print(f"  {'-'*25} {'-'*12} {'-'*20} {'-'*10}")
            for j in jobs:
                print(f"  {j['id'][:24]:<25} {j['status']:<12} {j['model']:<20} {format_age(j['created'])}")
        else:
            print("  (none)")

    if resource_type in ("all", "deployments"):
        deps = list_deployments(client)
        print(f"\n🚀 Fine-tuned models ({len(deps)}):")
        if deps:
            print(f"  {'Model':<60} {'Age':<10}")
            print(f"  {'-'*60} {'-'*10}")
            for d in deps:
                name = d['model'][:59]
                print(f"  {name:<60} {format_age(d['created'])}")
        else:
            print("  (none)")

    if resource_type in ("all", "files"):
        files = list_files(client)
        print(f"\n📁 Uploaded files ({len(files)}):")
        if files:
            print(f"  {'ID':<40} {'Size':>8} {'Purpose':<12} {'Age':<10} {'Status':<10}")
            print(f"  {'-'*40} {'-'*8} {'-'*12} {'-'*10} {'-'*10}")
            for f in files:
                print(f"  {f['id']:<40} {format_bytes(f['bytes']):>8} {f['purpose']:<12} {format_age(f['created']):<10} {f['status']}")
        else:
            print("  (none)")

        # Quota warning
        if len(files) >= 80:
            print(f"\n  ⚠️ {len(files)}/100 file slots used — approaching quota limit!")


def delete_files(client, older_than_days=None, dry_run=False):
    """Delete uploaded files, optionally filtering by age."""
    files = list_files(client)
    now = datetime.now(timezone.utc)

    to_delete = []
    for f in files:
        if older_than_days:
            age_days = (now - f["created"]).days
            if age_days < older_than_days:
                continue
        to_delete.append(f)

    if not to_delete:
        print("No files to delete.")
        return

    label = f"older than {older_than_days} days" if older_than_days else "all"
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deleting {len(to_delete)} files ({label}):")

    deleted = 0
    for f in to_delete:
        print(f"  {'Would delete' if dry_run else 'Deleting'}: {f['id']} ({f['filename']}, {format_age(f['created'])})")
        if not dry_run:
            try:
                client.files.delete(f["id"])
                deleted += 1
            except Exception as e:
                print(f"    ❌ Failed: {e}")

    if not dry_run:
        print(f"\n✅ Deleted {deleted}/{len(to_delete)} files")


def cancel_pending_jobs(client, dry_run=False):
    """Cancel any pending or queued jobs."""
    jobs = list_jobs(client)
    pending = [j for j in jobs if j["status"] in ("pending", "queued", "validating_files")]

    if not pending:
        print("No pending jobs to cancel.")
        return

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cancelling {len(pending)} pending jobs:")
    for j in pending:
        print(f"  {'Would cancel' if dry_run else 'Cancelling'}: {j['id']} ({j['status']})")
        if not dry_run:
            try:
                client.fine_tuning.jobs.cancel(j["id"])
            except Exception as e:
                print(f"    ❌ Failed: {e}")


def build_parser():
    parser = HelpOnErrorParser(
        description="Clean up fine-tuning resources (deployments, files, jobs)",
        epilog=(
            "Examples:\n"
            "  python cleanup.py --list                         # Show all resources\n"
            "  python cleanup.py --list --type files             # Show files only\n"
            "  python cleanup.py --delete-files --older-than 7   # Delete files older than 7 days\n"
            "  python cleanup.py --delete-files --dry-run        # Preview what would be deleted\n"
            "  python cleanup.py --cancel-pending                # Cancel queued jobs"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"), help="Project /v1/ endpoint URL")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                        help="Azure OpenAI endpoint (fallback)")
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_API_KEY"), help="API key")
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
                        help="Azure AI project endpoint")

    parser.add_argument("--list", action="store_true", help="List resources")
    parser.add_argument("--type", choices=["all", "jobs", "deployments", "files"], default="all",
                        help="Resource type to list (default: all)")

    parser.add_argument("--delete-files", action="store_true", help="Delete uploaded files")
    parser.add_argument("--older-than", type=int, default=None,
                        help="Only delete files older than N days (use with --delete-files)")
    parser.add_argument("--cancel-pending", action="store_true", help="Cancel pending/queued jobs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    client, method = get_clients(base_url=args.base_url, azure_endpoint=args.endpoint, project_endpoint=args.project_endpoint, api_key=args.api_key)

    if args.list:
        show_list(client, args.type)

    if args.delete_files:
        delete_files(client, older_than_days=args.older_than, dry_run=args.dry_run)

    if args.cancel_pending:
        cancel_pending_jobs(client, dry_run=args.dry_run)
