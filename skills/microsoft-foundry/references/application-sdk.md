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

## Minimal Managed Identity Examples

Set `AZURE_OPENAI_ENDPOINT` to the v1 base URL above and
`AZURE_OPENAI_DEPLOYMENT` to your deployment name. These examples use a
system-assigned managed identity with inference access. For a user-assigned
identity or local development, select the credential using the authentication
guidance above.

### .NET

NuGet packages: `OpenAI` 2.12.0 and `Azure.Identity` 1.21.0 (.NET 8+).

```csharp
using Azure.Identity;
using OpenAI;
using OpenAI.Chat;
using System.ClientModel.Primitives;

#pragma warning disable OPENAI001
var credential = new ManagedIdentityCredential(ManagedIdentityId.SystemAssigned);
var client = new ChatClient(
    model: Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT")!,
    authenticationPolicy: new BearerTokenPolicy(
        credential, "https://ai.azure.com/.default"),
    options: new OpenAIClientOptions {
        Endpoint = new Uri(Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!)
    });
var completion = await client.CompleteChatAsync(
    new UserChatMessage("Explain an API in one sentence."));
Console.WriteLine(completion.Value.Content[0].Text);
```

### Java

Maven dependencies: `com.openai:openai-java:4.43.0` and
`com.azure:azure-identity:1.18.4` (Java 11+).

```java
import com.azure.identity.AuthenticationUtil;
import com.azure.identity.ManagedIdentityCredentialBuilder;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.credential.BearerTokenCredential;
import com.openai.models.chat.completions.ChatCompletionCreateParams;

public class Example {
    public static void main(String[] args) {
        var client = OpenAIOkHttpClient.builder()
                .baseUrl(System.getenv("AZURE_OPENAI_ENDPOINT"))
                .credential(BearerTokenCredential.create(
                        AuthenticationUtil.getBearerTokenSupplier(
                                new ManagedIdentityCredentialBuilder().build(),
                                "https://ai.azure.com/.default")))
                .build();
        var request = ChatCompletionCreateParams.builder()
                .model(System.getenv("AZURE_OPENAI_DEPLOYMENT"))
                .addUserMessage("Explain an API in one sentence.")
                .build();
        client.chat().completions().create(request).choices().stream()
                .flatMap(choice -> choice.message().content().stream())
                .forEach(System.out::println);
    }
}
```

## Further Reading

- [Language and SDK guide](https://learn.microsoft.com/azure/foundry/openai/supported-languages)
- [Endpoint guidance](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/endpoints)
