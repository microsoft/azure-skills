# Foundry Application SDKs

Prefer a supported SDK for calling Foundry models from an application.

## OpenAI-compatible Model Inference

| Language | Package | Client | Example Chat Completions call |
|----------|---------|--------|-------------------------------|
| Python | [`openai`](https://github.com/openai/openai-python) | `OpenAI(...)` | `client.chat.completions.create(...)` |
| TypeScript / JavaScript | [`openai`](https://github.com/openai/openai-node) | `new OpenAI(...)` | `await client.chat.completions.create(...)` |
| .NET | [`OpenAI`](https://github.com/openai/openai-dotnet) | `new OpenAIClient(...).GetChatClient(deployment)` | `await chatClient.CompleteChatAsync(...)` |
| Java | [`com.openai:openai-java`](https://github.com/openai/openai-java) | `OpenAIOkHttpClient.builder()...build()` | `client.chat().completions().create(...)` |

For Azure OpenAI v1, configure the base URL as
`https://<resource>.openai.azure.com/openai/v1/` and use the Azure deployment
name as `model`. In .NET, supply the deployment name to `GetChatClient`.

Choose Responses or Chat Completions according to the application's needs
and deployed model's support; the table illustrates Chat Completions.

## Authentication

Use Microsoft Entra ID with Azure Identity. See
[authentication guidance](auth-best-practices.md) for credential selection
and managed identity patterns.

## Further Reading

- [Language and SDK guide](https://learn.microsoft.com/azure/foundry/openai/supported-languages)
- [Endpoint guidance](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/endpoints)
