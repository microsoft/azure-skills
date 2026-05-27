"""
common.py — Shared Azure AI Foundry authentication and client setup.

Supports three connection methods in order of preference:
1. /v1/ project endpoint (simplest, preferred)
2. Foundry SDK with DefaultAzureCredential (no API key needed, cloud-native)
3. Azure OpenAI endpoint (classic)

AAD tokens are auto-refreshed via azure.identity for long-running scripts
(monitor_training.py, generate_distillation_data.py, etc.).

Usage:
    from common import get_clients, upload_file

    # Method 1: Project /v1/ endpoint (preferred)
    clients = get_clients(base_url="https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/",
                          api_key="KEY")

    # Method 2: Foundry SDK (DefaultAzureCredential — no API key needed)
    clients = get_clients(project_endpoint="https://<resource>.services.ai.azure.com/api/projects/<project>")

    # Method 3: Azure OpenAI endpoint
    clients = get_clients(azure_endpoint="https://<resource>.openai.azure.com",
                          api_key="KEY")
"""
import argparse
import os
import sys



try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass  # Stream not reconfigurable (older Python or non-tty); default encoding is fine
_AZURE_COGSERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def _clamp_score(v, default=0):
    """Clamp a judge score to [1, 10]. Returns `default` for missing/non-numeric values.

    LLM judges occasionally return out-of-range integers (e.g., 15) or non-numeric
    strings ("high"). Without clamping, these distort aggregate scores or crash
    `int()`. We use 0 as a sentinel for "missing/failed" so callers can filter via
    `score > 0`.
    """
    if v is None:
        return default
    try:
        return max(1, min(10, int(v)))
    except (ValueError, TypeError):
        return default


class HelpOnErrorParser(argparse.ArgumentParser):
    """ArgumentParser that prints full help when arguments are invalid.
    
    Standard ArgumentParser only prints a one-line usage summary on error,
    which isn't helpful for first-time users. This prints the full --help.
    """

    def error(self, message):
        self.print_help(sys.stderr)
        self.exit(2, f"\nerror: {message}\n")


def _make_token_provider():
    """Create an auto-refreshing AAD token provider for long-running scripts.
    
    Returns a callable that the OpenAI SDK calls before each request to get
    a fresh token. Tokens are cached and refreshed ~5 min before expiry.
    """
    from azure.identity import DefaultAzureCredential
    credential = DefaultAzureCredential()

    def get_token():
        try:
            token = credential.get_token(_AZURE_COGSERVICES_SCOPE)
            return token.token
        except Exception as e:
            raise RuntimeError(
                f"Azure AD authentication failed: {e}\n"
                "Ensure you're logged in (az login) or have valid "
                "AZURE_CLIENT_ID/AZURE_TENANT_ID/AZURE_CLIENT_SECRET set."
            ) from e

    return get_token


def get_clients(base_url=None, azure_endpoint=None, project_endpoint=None, api_key=None):
    """Initialize and return OpenAI-compatible client.

    Tries in order:
    1. Project /v1/ endpoint with openai.OpenAI() (simplest, preferred)
    2. Foundry SDK with AIProjectClient.get_openai_client() (no API key needed)
    3. Azure OpenAI endpoint with openai.AzureOpenAI() (classic)

    When using DefaultAzureCredential (no API key), tokens are auto-refreshed
    so long-running scripts won't fail with 401 after ~60 min.

    Returns: (openai_client, method_name)
    """
    # Method 1: /v1/ project endpoint
    base_url = base_url or os.environ.get("OPENAI_BASE_URL")
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")

    if base_url:
        import openai
        if not api_key:
            try:
                token_provider = _make_token_provider()
                token_provider()  # verify it works
                # Use a custom httpx auth class that refreshes the token on each request
                import httpx

                class _AzureADAuth(httpx.Auth):
                    def __init__(self, provider):
                        self._provider = provider

                    def auth_flow(self, request):
                        request.headers["Authorization"] = f"Bearer {self._provider()}"
                        yield request

                client = openai.OpenAI(
                    base_url=base_url,
                    api_key="aad",  # required by SDK but overridden by auth
                    http_client=httpx.Client(auth=_AzureADAuth(token_provider)),
                )
                print(f"✅ Connected via /v1/ project endpoint (DefaultAzureCredential, auto-refresh)")
                return client, "project-v1-aad"
            except Exception as e:
                print(f"⚠️ No API key and DefaultAzureCredential failed: {e}")
        else:
            client = openai.OpenAI(base_url=base_url, api_key=api_key)
            print(f"✅ Connected via /v1/ project endpoint")
            return client, "project-v1"

    # Method 2: Foundry SDK
    project_endpoint = project_endpoint or os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if project_endpoint:
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)
            openai_client = project_client.get_openai_client()
            print(f"✅ Connected via Foundry SDK")
            return openai_client, "foundry-sdk"
        except Exception as e:
            print(f"⚠️ Foundry SDK failed: {e}")

    # Method 3: Azure OpenAI endpoint
    azure_endpoint = azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
    if azure_endpoint:
        import openai
        if api_key:
            client = openai.AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version="2025-04-01-preview",
            )
            print(f"✅ Connected via Azure OpenAI endpoint")
            return client, "azure-openai"
        else:
            # No API key — use DefaultAzureCredential with auto-refresh
            try:
                token_provider = _make_token_provider()
                token_provider()  # verify it works
                client = openai.AzureOpenAI(
                    azure_endpoint=azure_endpoint,
                    azure_ad_token_provider=token_provider,
                    api_version="2025-04-01-preview",
                )
                print(f"✅ Connected via Azure OpenAI endpoint (DefaultAzureCredential, auto-refresh)")
                return client, "azure-openai-aad"
            except Exception as e:
                print(f"⚠️ DefaultAzureCredential failed for Azure endpoint: {e}")

    print("❌ No valid connection method. Set one of:")
    print("   OPENAI_BASE_URL (preferred)")
    print("   AZURE_AI_PROJECT_ENDPOINT (Foundry SDK)")
    print("   AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY")
    raise SystemExit(1)


def upload_file(openai_client, filepath: str, purpose: str = "fine-tune") -> str:
    """Upload a file to Azure AI Foundry and wait for processing."""
    print(f"📤 Uploading {filepath}...")
    with open(filepath, "rb") as f:
        file_obj = openai_client.files.create(file=f, purpose=purpose)
    print(f"   File ID: {file_obj.id}")
    print(f"   Waiting for processing...")
    openai_client.files.wait_for_processing(file_obj.id)
    print(f"   ✅ File ready")
    return file_obj.id
