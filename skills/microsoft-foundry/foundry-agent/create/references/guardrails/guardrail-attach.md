# Attach a Guardrail

After creating a guardrail (via [portal](guardrail-manage.md) or [REST API](guardrail-api-create.md)), attach it to one of three targets:

- [Hosted Agent](#hosted-agent) — `agent.yaml` `policies` block
- [Model Deployment](#model-deployment) — REST API or request-time header
- [Toolbox](#toolbox) — `policies.rai_config.rai_policy_name` in toolbox definition

---

## Hosted Agent

A guardrail assigned to an agent **fully overrides** the underlying model deployment's guardrail. If no guardrail is assigned, the agent inherits the model deployment's guardrail.

Add a `policies` block to `agent.yaml` with the guardrail's full ARM resource ID:

```yaml
policies:
  - type: rai_policy
    rai_policy_name: /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/raiPolicies/<policy-name>
```

See the [`16-content-safety-guardrail` sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/16-content-safety-guardrail) for a complete working example.

> `rai_policy_name` must be the **full ARM resource ID**, not just the policy name. This differs from the toolbox and model deployment paths which use just the name.

---

## Model Deployment

### Assign via REST API

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="<your-resource-group>"
ACCOUNT_NAME="<your-ai-services-account>"
DEPLOYMENT_NAME="<your-model-deployment>"

az rest --method PATCH \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/deployments/${DEPLOYMENT_NAME}?api-version=2024-10-01" \
  --body '{"properties": {"raiPolicyName": "my-custom-guardrail"}}'
```

> `raiPolicyName` is the guardrail name (not the full ARM resource ID). It must match a guardrail that exists on the AI Services account.

### Request-Time Override

Override the deployment-level guardrail per request using the `x-policy-id` header:

```bash
ENDPOINT="https://<your-resource-name>.openai.azure.com"
DEPLOYMENT_NAME="<your-model-deployment>"
API_KEY="<your-api-key>"

curl --request POST \
  --url "${ENDPOINT}/openai/deployments/${DEPLOYMENT_NAME}/chat/completions?api-version=2024-10-21" \
  --header "Content-Type: application/json" \
  --header "api-key: ${API_KEY}" \
  --header "x-policy-id: my-custom-guardrail" \
  --data '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

> Request-time override is not available for image input scenarios.

---

## Toolbox

Add `policies.rai_config.rai_policy_name` to the toolbox definition file, then create the toolbox with `azd ai toolbox create`.

```yaml
description: My toolbox
connections:
  - name: my-mcp-server
tools:
  - type: web_search
    name: web
policies:
  rai_config:
    rai_policy_name: my-custom-guardrail
```

> `rai_policy_name` must match a guardrail that exists on the AI Services account. Use `Microsoft.Default`, `Microsoft.DefaultV2`, or a custom name created via [portal or API](guardrail-api-create.md).

```bash
azd ai toolbox create my-toolbox --from-file ./toolbox.yaml
```

There is no command to change the guardrail on an existing toolbox version. To update, delete and recreate the toolbox.

---

## References

- [Guardrails overview](guardrail-manage.md) — create guardrails, default policies, intervention points
- [API create](guardrail-api-create.md) — create guardrails via REST API
- [Guardrails overview (Microsoft Learn)](https://learn.microsoft.com/azure/foundry/guardrails/guardrails-overview)
- [How to configure guardrails (Microsoft Learn)](https://learn.microsoft.com/azure/foundry/guardrails/how-to-create-guardrails)
