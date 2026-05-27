# Deployment Formats

## Model Format and SKU Mapping

| Base model family | `model.format` | `sku.name` | Endpoint type |
|-------------------|---------------|------------|---------------|
| gpt-4.1-mini | `"OpenAI"` | `"Standard"` | Project |
| gpt-4.1-nano | `"OpenAI"` | `"Standard"` | Project |
| o4-mini (RFT) | `"OpenAI"` | `"Standard"` | Project |
| gpt-oss-20b | `"Microsoft"` | `"GlobalStandard"` | Cognitive Services |
| Ministral-3B | `"Mistral AI"` | `"GlobalStandard"` | Cognitive Services |
| Llama-3.3-70B | `"Meta"` | `"GlobalStandard"` | Cognitive Services |
| Qwen-3-32B | `"Alibaba"` | `"GlobalStandard"` | Cognitive Services |

**Format strings are case-sensitive.** `"Mistral AI"` works; `"mistral"` does not.

## Two Endpoint Types

**Project Endpoint** (OpenAI models): `https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/`
- Use `openai.OpenAI(base_url=..., api_key=...)` — NOT `AzureOpenAI`

**Cognitive Services Endpoint** (OSS models): `https://<resource>.cognitiveservices.azure.com/openai/deployments/<name>/chat/completions?api-version=2025-04-01-preview`
- Use `openai.AzureOpenAI(azure_endpoint=..., api_key=..., api_version=...)`

## CLI Deployment (`az cognitiveservices`)

The CLI uses **different** format strings than the ARM REST API for OSS models:

```bash
az cognitiveservices account deployment create \
  --name <resource> \
  --resource-group <rg> \
  --deployment-name <name> \
  --model-name <model> \
  --model-version "1" \
  --model-format "OpenAI-OSS" \
  --sku-capacity 100 \
  --sku-name "GlobalStandard"
```

| Base model family | ARM REST `model.format` | CLI `--model-format` |
|-------------------|------------------------|----------------------|
| gpt-4.1-mini/nano | `"OpenAI"` | `"OpenAI"` |
| gpt-oss-20b | `"Microsoft"` | `"OpenAI-OSS"` |
| Ministral-3B | `"Mistral AI"` | `"OpenAI-OSS"` |
| Llama-3.3-70B | `"Meta"` | `"OpenAI-OSS"` |
| Qwen-3-32B | `"Alibaba"` | `"OpenAI-OSS"` |

> ⚠️ Using `"OpenAI-OSS"` in ARM REST or `"Microsoft"` in CLI will fail with HTTP 500.

## ARM REST API Deployment

```
PUT https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/deployments/{deploy_name}?api-version=2024-10-01
```

```json
{
  "sku": { "name": "GlobalStandard", "capacity": 100 },
  "properties": {
    "model": {
      "format": "Microsoft",
      "name": "gpt-oss-20b.ft-{jobid}-suffix",
      "version": "1"
    }
  }
}
```

**ARM token:** `az account get-access-token --query accessToken -o tsv` (expires ~60min).

## Capacity Notes

- Capacity = tokens-per-minute in thousands. `100` = 100K TPM.
- Set capacity ≥ 100 for eval workloads. At capacity=1, OSS FT models hit "Failed to load LoRA" errors.
- Quota is per-resource. After deleting a deployment, wait 15–20s before creating a new one.
- Deployment names: max 64 chars, alphanumeric + hyphens, unique within resource.

## Common Deployment Errors

| Error | Cause | Fix |
|-------|-------|-----|
| HTTP 500, no message | Wrong `model.format` | Check format table above |
| HTTP 409, deployment exists | Name collision | Use unique deployment name |
| HTTP 403 | ARM token expired | Refresh token |
| HTTP 400, "api-version not allowed" | `AzureOpenAI` client on `/v1/` endpoint | Switch to `openai.OpenAI` |
| HTTP 429, quota exceeded | Too many deployments | Delete unused, wait 20s |
| ProvisioningState: Failed | Model not available in region | Try different region |
