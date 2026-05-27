# /// script
# dependencies = [
#   "openai>=1.0",
#   "requests",
#   "azure-identity",
# ]
# ///
"""
deploy_model.py — Deploy fine-tuned models on Azure AI Foundry via ARM REST API.

Supports all model families with correct format/SKU mapping.

Usage:
  python deploy_model.py --model-id "ft:gpt-4.1-mini-2025-04-14:..." --name "my-ft-eval" --capacity 100
  python deploy_model.py --model-id "ft:gpt-oss-20b:..." --name "oss-eval" --format Microsoft --sku GlobalStandard
  python deploy_model.py --delete --name "my-ft-eval"
  python deploy_model.py --list
"""

import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HelpOnErrorParser

import requests


def _safe_error_msg(resp):
    """Extract error message from response, handling non-JSON bodies (HTML 502/503)."""
    try:
        return resp.json().get("error", {}).get("message", resp.text[:200])
    except (ValueError, KeyError):
        return resp.text[:200] if resp.text else "Unknown error"

# Default Azure resource coordinates — override with env vars or args
DEFAULT_SUB = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
DEFAULT_RG = os.environ.get("AZURE_RESOURCE_GROUP", "")
DEFAULT_ACCOUNT = os.environ.get("AZURE_COGSERVICES_ACCOUNT", "")
AZ_CLI = os.environ.get("AZ_CLI_PATH")
if not AZ_CLI:
    import shutil
    AZ_CLI = shutil.which("az")
    if not AZ_CLI:
        # Common Windows paths
        for candidate in [
            r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        ]:
            if os.path.exists(candidate):
                AZ_CLI = candidate
                break
    if not AZ_CLI:
        AZ_CLI = "az"  # last resort, hope it's on PATH

# Model format auto-detection rules
FORMAT_RULES = [
    (lambda m: "oss-20b" in m.lower() or "oss20b" in m.lower(), "Microsoft", "GlobalStandard"),
    (lambda m: "ministral" in m.lower() or "mistral" in m.lower(), "Mistral AI", "GlobalStandard"),
    (lambda m: "llama" in m.lower() or "meta" in m.lower(), "Meta", "GlobalStandard"),
    (lambda m: "qwen" in m.lower() or "alibaba" in m.lower(), "Alibaba", "GlobalStandard"),
    (lambda m: True, "OpenAI", "Standard"),  # Default fallback
]


def get_arm_token():
    """Get a fresh ARM token from Azure CLI."""
    result = subprocess.run(
        [AZ_CLI, "account", "get-access-token", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(f"Failed to get ARM token: {result.stderr}")
    return token


def arm_url(sub, rg, account, deploy_name=None):
    """Build the ARM REST API URL."""
    base = (f"https://management.azure.com/subscriptions/{sub}"
            f"/resourceGroups/{rg}"
            f"/providers/Microsoft.CognitiveServices/accounts/{account}"
            f"/deployments")
    if deploy_name:
        base += f"/{deploy_name}"
    return base + "?api-version=2024-10-01"


def detect_format(model_id):
    """Auto-detect model format and SKU from model ID."""
    for check, fmt, sku in FORMAT_RULES:
        if check(model_id):
            return fmt, sku
    return "OpenAI", "Standard"


def create_deployment(sub, rg, account, name, model_id, model_format, sku, capacity):
    """Create a deployment via ARM REST API."""
    token = get_arm_token()
    url = arm_url(sub, rg, account, name)

    body = {
        "sku": {"name": sku, "capacity": capacity},
        "properties": {
            "model": {
                "format": model_format,
                "name": model_id,
                "version": "1",
            }
        },
    }

    resp = requests.put(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }, json=body, timeout=(10, 120))

    if resp.status_code in (200, 201):
        print(f"✅ Deployment '{name}' created (format={model_format}, sku={sku}, capacity={capacity})")
        return True
    else:
        print(f"❌ Deployment failed ({resp.status_code}): {_safe_error_msg(resp)}")
        return False


def wait_for_deployment(sub, rg, account, name, timeout=600, poll_interval=15):
    """Wait for deployment to reach 'Succeeded' state."""
    url = arm_url(sub, rg, account, name)
    start = time.time()

    while time.time() - start < timeout:
        token = get_arm_token()
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=(10, 60))
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️ Polling error: {e} — retrying in {poll_interval}s")
            time.sleep(poll_interval)
            continue
        if resp.status_code == 200:
            try:
                state = resp.json().get("properties", {}).get("provisioningState", "Unknown")
            except (ValueError, KeyError):
                state = "Unknown"
            print(f"  Status: {state}")
            if state == "Succeeded":
                return True
            if state in ("Failed", "Canceled"):
                print(f"  Deployment {state}.")
                return False
        time.sleep(poll_interval)

    print(f"  Timed out after {timeout}s")
    return False


def delete_deployment(sub, rg, account, name):
    """Delete a deployment."""
    token = get_arm_token()
    url = arm_url(sub, rg, account, name)
    resp = requests.delete(url, headers={"Authorization": f"Bearer {token}"}, timeout=(10, 60))
    if resp.status_code in (200, 202, 204):
        print(f"✅ Deployment '{name}' deleted.")
    else:
        print(f"❌ Delete failed ({resp.status_code}): {_safe_error_msg(resp)}")


def list_deployments(sub, rg, account):
    """List all deployments."""
    token = get_arm_token()
    url = arm_url(sub, rg, account)
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=(10, 60))
    if resp.status_code != 200:
        print(f"❌ Failed to list deployments ({resp.status_code}): {_safe_error_msg(resp)}")
        return

    try:
        deployments = resp.json().get("value", [])
    except (ValueError, KeyError):
        print(f"❌ Failed to parse deployment list: {resp.text[:200]}")
        return
    if not deployments:
        print("No deployments found.")
        return

    print(f"{'Name':<40} {'Model':<40} {'SKU':<15} {'State':<15}")
    print("─" * 110)
    for d in deployments:
        name = d.get("name", "?")
        model = d.get("properties", {}).get("model", {}).get("name", "?")
        sku = d.get("sku", {}).get("name", "?")
        state = d.get("properties", {}).get("provisioningState", "?")
        print(f"{name:<40} {model:<40} {sku:<15} {state:<15}")


def main():
    parser = HelpOnErrorParser(description="Deploy fine-tuned models on Azure AI Foundry")
    parser.add_argument("--sub", default=DEFAULT_SUB, help="Azure subscription ID")
    parser.add_argument("--rg", default=DEFAULT_RG, help="Resource group")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT, help="Cognitive Services account")

    # Actions
    parser.add_argument("--list", action="store_true", help="List all deployments")
    parser.add_argument("--delete", action="store_true", help="Delete a deployment")
    parser.add_argument("--wait", action="store_true", help="Wait for deployment to succeed")

    # Deployment config
    parser.add_argument("--name", help="Deployment name (max 64 chars, alphanumeric + hyphens)")
    parser.add_argument("--model-id", help="Fine-tuned model ID (e.g., ft:gpt-4.1-mini:...)")
    parser.add_argument("--format", help="Model format (auto-detected if not specified)")
    parser.add_argument("--sku", help="SKU name (auto-detected if not specified)")
    parser.add_argument("--capacity", type=int, default=100, help="TPM capacity in thousands")

    args = parser.parse_args()

    if not all([args.sub, args.rg, args.account]):
        print("Error: Set --sub/--rg/--account or AZURE_SUBSCRIPTION_ID/AZURE_RESOURCE_GROUP/AZURE_COGSERVICES_ACCOUNT")
        sys.exit(1)

    if args.list:
        list_deployments(args.sub, args.rg, args.account)
        return

    if not args.name:
        print("Error: --name required for create/delete/wait")
        sys.exit(1)

    if args.delete:
        delete_deployment(args.sub, args.rg, args.account, args.name)
        return

    if args.wait and not args.model_id:
        # Wait-only mode: poll an existing deployment
        success = wait_for_deployment(args.sub, args.rg, args.account, args.name)
        sys.exit(0 if success else 1)

    if not args.model_id:
        print("Error: --model-id required for create")
        sys.exit(1)

    # Auto-detect format/SKU if not specified
    model_format = args.format
    sku = args.sku
    if not model_format or not sku:
        auto_fmt, auto_sku = detect_format(args.model_id)
        model_format = model_format or auto_fmt
        sku = sku or auto_sku
        print(f"Auto-detected: format={model_format}, sku={sku}")

    created = create_deployment(args.sub, args.rg, args.account, args.name,
                      args.model_id, model_format, sku, args.capacity)

    if args.wait and created:
        wait_for_deployment(args.sub, args.rg, args.account, args.name)


if __name__ == "__main__":
    main()
