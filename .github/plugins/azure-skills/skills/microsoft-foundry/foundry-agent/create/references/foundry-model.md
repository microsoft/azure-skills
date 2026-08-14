# Foundry Model Reference

Use this reference to query Microsoft Foundry model-related data.

## Model information

Query the regional model catalog to obtain the model version, format, capabilities, lifecycle status, and supported SKUs:

**PowerShell:**

```pwsh
$region = "<REGION>"
$subscription = "<SUBSCRIPTION_ID_OR_NAME>"

az cognitiveservices model list `
  --location $region `
  --subscription $subscription `
  -o json
```

**Bash:**

```bash
REGION="<REGION>"
SUBSCRIPTION="<SUBSCRIPTION_ID_OR_NAME>"

az cognitiveservices model list \
  --location "$REGION" \
  --subscription "$SUBSCRIPTION" \
  -o json
```

The result provides:

- Model name, version, format, default-version status, and lifecycle status.
- Capabilities such as Responses, chat completions, and agents support.
- Supported SKUs, capacity ranges, and usage names.

## Model quota

Query the regional usage record for the exact model and SKU, then calculate the currently available quota:

**PowerShell:**

```pwsh
$region = "<REGION>"
$subscription = "<SUBSCRIPTION_ID_OR_NAME>"

az cognitiveservices usage list `
  --location $region `
  --subscription $subscription `
  -o json
```

**Bash:**

```bash
REGION="<REGION>"
SUBSCRIPTION="<SUBSCRIPTION_ID_OR_NAME>"

az cognitiveservices usage list \
  --location "$REGION" \
  --subscription "$SUBSCRIPTION" \
  -o json
```

The result provides quota usage names, current usage, limits, and units for the subscription and region.