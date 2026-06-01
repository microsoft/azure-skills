# com.microsoft.azure.management.\*\*

## Code Checklist

- Keep Azure resources, operations, and property values identical. The goal is functional equivalence, not feature expansion.
- Do not change the method sequence when creating or updating an Azure resource unless the new SDK requires it.
- Preserve the existing async pattern. For example, a delayed provisioning pattern that uses `Creatable<Resource>` should not be replaced by a direct `.create()` call. Similarly, when provisioning a resource, do not swap `.withNewDependencyResource` for `.withExistingDependencyResource` unless mandated by the new API surface.
- Keep the text emitted by logging and stdout/stderr unchanged to avoid breaking downstream consumers of those streams.
- Do not replace `resource.region()` with `resource.regionName()`; doing so changes the type from `Region` to `String` and can introduce subtle regressions.

## Code Samples

### Authentication with File

File-based authentication (e.g., `Azure.configure().authenticate(credentialFile)`) is **discouraged** under Azure's security-by-default posture: it relies on long-lived secrets stored on disk, which conflicts with the modern guidance to prefer managed identities, workload identity, or other credential types exposed by `DefaultAzureCredential`.

#### Detect: legacy file-based authentication patterns

Treat **any** of the following shapes in the legacy code as file-based authentication that must be replaced (not migrated). Triggers include `AZURE_AUTH_LOCATION`, `.authenticate(File)`, `ApplicationTokenCredentials.fromFile`, or any code path that reads `clientId` / `clientSecret` / `tenant` from disk and feeds them into a credential builder.

> **Important:** Reading `clientId`, `clientSecret`, or `tenantId` from **environment variables** (e.g., `System.getenv("AZURE_CLIENT_ID")`) does **not** constitute file-based authentication and should **not** be flagged by this rule. Only flag patterns that source credentials from files on disk.

```java
// Shape A: direct File overload
Azure azure = Azure.authenticate(new File(System.getenv("AZURE_AUTH_LOCATION")))
                   .withDefaultSubscription();

// Shape B: configure() chain with a File
File credFile = new File(authFilePath);
Azure azure = Azure.configure()
    .withLogLevel(LogLevel.BASIC)
    .authenticate(credFile)
    .withDefaultSubscription();

// Shape C: ApplicationTokenCredentials.fromFile(...)
ApplicationTokenCredentials creds =
    ApplicationTokenCredentials.fromFile(new File(authFile));
Azure azure = Azure.authenticate(creds).withSubscription(subscriptionId);
```

Do **not** emit a code sample that reproduces any of the above during the upgrade — including a "modernized" variant that parses the same file with Jackson and feeds it into `ClientSecretCredentialBuilder`. Instead, replace the authentication block in the migrated code with a `DefaultAzureCredential` (or another appropriate `TokenCredential`) and prepend a `TODO` comment that explains the change. For example:

```java
// TODO: The original code authenticated using a credential file (AZURE_AUTH_LOCATION),
// which is discouraged because it relies on long-lived secrets on disk and conflicts
// with Azure's security-by-default guidance. It has been replaced with
// DefaultAzureCredential. This change alters the authentication mechanism, so the
// resulting code path requires extra testing (local dev, CI, and target runtime
// identities) before it is considered production-ready.
TokenCredential credential = new DefaultAzureCredentialBuilder().build();
AzureProfile profile = new AzureProfile(AzureEnvironment.AZURE);
AzureResourceManager azure = AzureResourceManager.configure()
    .authenticate(credential, profile)
    .withDefaultSubscription();
```

Keep the `TODO` comment in the migrated source so reviewers and downstream maintainers are aware that the authentication mechanism changed and that the new code path has not been exercised by the original tests.

#### Rewrite obsolete authentication diagnostics

If legacy code mentions `AZURE_AUTH_LOCATION` only in a validation guard or exception message, do not carry that option into migrated runtime-visible text. Keep the guard, but rewrite the message around the credentials the migrated code actually supports, e.g. `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_SUBSCRIPTION_ID`. Do not scrub intentional `AZURE_AUTH_LOCATION` mentions from this guide's examples or TODO comments that explain why file-based auth was replaced.

### OKHttp Interceptors

Legacy OKHttp `Interceptor` implementation classes should be migrated to `HttpPipelinePolicy` implementation classes. This is a two-step migration — both steps are required:

**Step 1: Convert each `Interceptor` subclass to an `HttpPipelinePolicy` subclass.** Rename the class from `XxxInterceptor` to `XxxPolicy` and reimplement its logic against the `HttpPipelinePolicy` interface (i.e. `process(HttpPipelineCallContext, HttpPipelineNextPolicy)`) instead of the OKHttp `Interceptor.intercept(Chain)` API.

**Step 2: Register every converted policy on the new manager builder via `.withPolicy(new XxxPolicy())`.** Each `withNetworkInterceptor(new XxxInterceptor())` call on the legacy `RestClient.Builder` must have a corresponding `.withPolicy(new XxxPolicy())` call on `AzureResourceManager.configure()` (or the equivalent `XxxManager.configure()`). Preserve the original ordering of the interceptors when registering the policies.

Do not skip Step 2: converting the class without wiring it into the manager builder silently drops the behavior.

1. Legacy code:
```java
RestClient.Builder builder = new RestClient.Builder()
    ...
    .withNetworkInterceptor(new ResourceGroupTaggingInterceptor())
    ...;

Azure.Authenticated azureAuthed = Azure.authenticate(builder.build(), subscriptionId, credentials.domain());
Azure azure = azureAuthed.withSubscription(subscriptionId);
```

2. Migrated code (note: `ResourceGroupTaggingPolicy` is the Step 1 conversion of `ResourceGroupTaggingInterceptor`, and it must be registered via `.withPolicy(...)` in Step 2):
```java
AzureResourceManager azureResourceManager = AzureResourceManager.configure()
    .withPolicy(new ResourceGroupTaggingPolicy())
    .authenticate(credential, profile)
    .withDefaultSubscription();
```

### ProviderRegistrationInterceptor

If legacy client(XXManager) initializes with `ProviderRegistrationInterceptor`, check whether this client is one of the premium ones:
- Azure
- AuthorizationManager
- CdnManager
- ComputeManager
- ContainerInstanceManager
- ContainerRegistryManager
- ContainerServiceManager
- CosmosDBManager
- DnsZoneManager
- EventHubManager
- KeyVaultManager
- MonitorManager
- MSIManager
- NetworkManager
- RedisManager
- ResourceManager
- SearchServiceManager
- ServiceBusManager
- SqlServerManager
- StorageManager
- TrafficManager

If not, add `ProviderRegistrationPolicy` when initializing the client. Otherwise, don't.

For each legacy client, add along with whether to initialize with `ProviderRegistrationPolicy`, to the generated plan guideline, and migrate accordingly.

1. Legacy client(not premium client):
```java
BatchManager batchManager = BatchManager.configure()
    .withLogLevel(LogLevel.BASIC)
    .withInterceptor(new ProviderRegistrationInterceptor(credentials))
    .authenticate(credentials, subscriptionId);
```
should be migrated to:
```java
BatchManager batchManager = BatchManager.configure()
    .withPolicy(new ProviderRegistrationPolicy())
    .withLogOptions(new HttpLogOptions().setLogLevel(HttpLogDetailLevel.BASIC))
    .authenticate(credential, profile);
```

2. Legacy client(premium clients):
```java
Azure azure = Azure.configure()
    .withInterceptor(new ProviderRegistrationInterceptor(credentials))
    .withLogLevel(LogLevel.BASIC)
    .authenticate(credentials)
    .withSubscription(subscriptionId);
```
should be migrated to:
```java
AzureResourceManager.configure()
    .withLogLevel(HttpLogDetailLevel.BASIC)
    .authenticate(credential, profile);
```

### BatchAccount

azure-resourcemanager-batch is no longer a premium/handwritten library. In BatchAccount, `withNewStorageAccount` should be replaced by `.withAutoStorage(new AutoStorageBaseProperties().withStorageAccountId(storageAccount.id()))`, while the `storageAccount` needs to be created separately.

Legacy code:
```java
BatchAccount batchAccount = azure.batchAccounts().define(batchAccountName)
    .withRegion(region)
    .withNewResourceGroup(rgName)
    .defineNewApplication(applicationName)
        .defineNewApplicationPackage(applicationPackageName)
        .withAllowUpdates(true)
        .withDisplayName(applicationDisplayName)
        .attach()
    .withNewStorageAccount(storageAccountName)
    .create();
```

Migrated:
```java
StorageAccount storageAccount = storageManager.storageAccounts()
    .define(storageAccountName)
    .withRegion(REGION)
    .withExistingResourceGroup(resourceGroup)
    .create();
BatchAccount account = batchManager.batchAccounts()
    .define(batchAccountName)
    .withRegion(REGION)
    .withExistingResourceGroup(resourceGroup)
    .withAutoStorage(new AutoStorageBaseProperties().withStorageAccountId(storageAccount.id()))
    .create();
// create application with batch account
application = batchManager.applications()
    .define(applicationName)
    .withExistingBatchAccount(resourceGroup, account.name())
    .withDisplayName(applicationDisplayName)
    .withAllowUpdates(true)
    .create();
applicationPackage = batchManager.applicationPackages()
    .define(applicationPackageName)
    .withExistingApplication(resourceGroup, batchAccountName, applicationName)
    .create();
```
