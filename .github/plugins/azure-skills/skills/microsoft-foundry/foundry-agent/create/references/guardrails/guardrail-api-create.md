# Create a Guardrail via the REST API (`az rest`)

> Use this path only when the user explicitly asks for programmatic/CLI/CI/CD creation. Otherwise, guide them to the [portal](guardrail-manage.md#default-path-portal).

## Prerequisites

- Azure CLI installed and logged in (`az login`)
- **Foundry Account Owner** role (or higher) on the Azure AI resource
- The Azure AI Services account name, resource group, and subscription ID

## Step 1: Set Variables

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="<your-resource-group>"
ACCOUNT_NAME="<your-ai-services-account>"
POLICY_NAME="my-custom-guardrail"
```

## Step 2: List Existing Guardrails

```bash
az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/raiPolicies?api-version=2024-10-01"
```


## Step 3: Create a Guardrail

Minimal example — `guardrail-policy.json`:

```json
{
  "properties": {
    "basePolicyName": "Microsoft.Default",
    "mode": "Asynchronous_filter",
    "contentFilters": [
      { "name": "Hate", "enabled": true, "blocking": true, "severityThreshold": "Medium", "source": "Prompt" },
      { "name": "Hate", "enabled": true, "blocking": true, "severityThreshold": "Medium", "source": "Completion" },
      { "name": "Violence", "enabled": true, "blocking": true, "severityThreshold": "Low", "source": "Prompt" },
      { "name": "Violence", "enabled": true, "blocking": true, "severityThreshold": "Low", "source": "Completion" },
      { "name": "Jailbreak", "enabled": true, "blocking": true, "source": "Prompt" }
    ]
  }
}
```

```bash
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/raiPolicies/${POLICY_NAME}?api-version=2024-10-01" \
  --body @guardrail-policy.json
```

- `200 OK` — policy updated
- `201 Created` — policy created for the first time

For the full request body schema (`contentFilters[]`, `basePolicyName`, `mode`, `customBlocklists`), see the [RAI Policies - Create Or Update API reference](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/rai-policies/create-or-update).

## Step 4: Verify via CLI

```bash
az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/raiPolicies/${POLICY_NAME}?api-version=2024-10-01"
```

Confirm `contentFilters[]` matches your intended configuration.

## Step 5: Assign to Targets

After creating a guardrail, assign it to a hosted agent, model deployment, or toolbox → [guardrail-attach.md](guardrail-attach.md)

## Delete a Guardrail

> Remove all model/agent assignments before deleting (portal: edit guardrail → deselect all targets → save).

```bash
az rest --method DELETE \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/raiPolicies/${POLICY_NAME}?api-version=2024-10-01"
```

## References

- [RAI Policies - Create Or Update (REST API)](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/rai-policies/create-or-update) — full schema, parameters, response codes
- [RAI Policies - List](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/rai-policies/list) — list all policies on an account
- [Blocklists API](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/rai-blocklists) — custom blocklists (created separately)
- [How to configure guardrails (Microsoft Learn)](https://learn.microsoft.com/azure/foundry/guardrails/how-to-create-guardrails) — portal walkthrough
