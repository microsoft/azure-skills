# Foundry Application SDK Integration

## Select

1. Identify the application's language, framework, required API, and endpoint.
   Verify SDK/package support using the current [language guide](https://learn.microsoft.com/azure/foundry/openai/supported-languages)
   and [endpoint guidance](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/endpoints).
2. Prefer a supported SDK over handwritten HTTP; keep suitable existing SDK/framework integrations.
   Use REST only when explicitly requested or no suitable SDK supports the capability; explain why.
3. Distinguish direct model inference from [project/agent operations](../foundry-agent/create/references/sdk-operations.md).
   Do not interchange their clients or endpoints.

For OpenAI v1 inference, use the documented `/openai/v1/` base URL and deployment
name as `model`. Let the SDK handle request serialization and HTTP retries.
Select Responses or Chat Completions according to model support and task requirements.

## SDK Patterns

Abbreviated Chat Completions patterns, not complete programs or an SDK/language allow-list.

| Language | Package | Client construction or factory | Inference call |
|----------|---------|--------------------------------|----------------|
| Python | [`openai`](https://github.com/openai/openai-python) | `OpenAI(...)` | `client.chat.completions.create(...)` |
| TypeScript / JavaScript | [`openai`](https://github.com/openai/openai-node) | `new OpenAI(...)` | `await client.chat.completions.create(...)` |
| .NET | [`OpenAI`](https://github.com/openai/openai-dotnet) | `new OpenAIClient(...).GetChatClient(deployment)` | `await client.CompleteChatAsync(...)` |
| Java | [`com.openai:openai-java`](https://github.com/openai/openai-java) | `OpenAIOkHttpClient.builder()...build()` | `client.chat().completions().create(...)` |

## Implement and Verify

- Add the runtime dependency, construct the SDK client, and route actual application
  model requests/responses through it. A dependency, import, or mock alone is insufficient.
- Follow [authentication guidance](auth-best-practices.md) and the language guide
  for credential setup and token audience. Do not replace required token authentication with API keys.
- Build and test. Without live access, exercise the production integration using an
  SDK-supported transport or client test double, not a separate REST implementation.

Code-only tasks do not require provisioning, hosted-agent deployment, or live inference.
