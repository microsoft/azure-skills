# Azure Workload Identity for AKS

> **Last updated:** 2026-04-02

## What Is Workload Identity?

Workload Identity lets pods in AKS authenticate to Azure services (Key Vault, Storage,
PostgreSQL, etc.) without storing any secrets. Instead of injecting connection strings or
passwords, your pod proves its identity through a short-lived token issued by the
cluster's OIDC provider, which Microsoft Entra ID trusts because you've set up a federation
between the cluster and a Managed Identity. The pod gets a token automatically — your
app code just uses the standard Azure SDK credential chain.

---

## Three Components

### 1. User-Assigned Managed Identity

A Managed Identity in Azure that has RBAC role assignments on the target resources
(e.g., `Key Vault Secrets User`, `Storage Blob Data Contributor`).

```
Managed Identity
  ├── Client ID: <AZURE_CLIENT_ID>
  ├── Tenant ID: <AZURE_TENANT_ID>
  └── Role assignments:
       ├── Key Vault Secrets User  → /subscriptions/.../vaults/my-kv
       ├── Storage Blob Data Contributor → /subscriptions/.../storageAccounts/my-sa
       └── ...
```

### 2. Federated Identity Credential

A trust relationship that says: "When the AKS cluster's OIDC issuer presents a token
for ServiceAccount `<namespace>/<sa-name>`, treat it as this Managed Identity."

```
Federated Credential
  ├── Issuer:  https://oidc.prod-aks.azure.com/<tenant-id>/<cluster-id>
  ├── Subject: system:serviceaccount:<namespace>:<sa-name>
  └── Audience: api://AzureADTokenExchange
```

### 3. Kubernetes ServiceAccount

A standard K8s ServiceAccount annotated with the Managed Identity's client ID.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: <app-name>
  namespace: <namespace>
  annotations:
    azure.workload.identity/client-id: "<AZURE_CLIENT_ID>"
```

---

## How They Link Together

```
Pod (with label azure.workload.identity/use: "true")
  │
  ├── References ServiceAccount (annotated with client-id)
  │
  ▼
AKS OIDC Issuer issues a projected service account token
  │
  ├── Issuer URL matches the Federated Credential's issuer
  ├── Subject (system:serviceaccount:ns:sa) matches the Federated Credential's subject
  │
  ▼
Microsoft Entra ID validates the federation and issues a token
  │
  ▼
Azure SDK (DefaultAzureCredential) uses the token to access Azure resources
```

The Workload Identity webhook in AKS automatically:
- Projects the service account token into the pod at a well-known path
- Sets the `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_FEDERATED_TOKEN_FILE`
  environment variables in the container

Your app code does **not** need to know about any of this — `DefaultAzureCredential`
picks it up automatically.

---

## Per-Service Patterns

### PostgreSQL (Flexible Server with Microsoft Entra ID Auth)

The Managed Identity needs the `<db-name> Admin` or a custom PostgreSQL role.

```python
# Python — psycopg2 + DefaultAzureCredential
import psycopg2
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")

conn = psycopg2.connect(
    host="<server>.postgres.database.azure.com",
    dbname="<database>",
    user="<managed-identity-name>",
    password=token.token,
    sslmode="require",
)
```

```csharp
// C# — Npgsql + Azure.Identity
var credential = new DefaultAzureCredential();
var token = await credential.GetTokenAsync(
    new TokenRequestContext(new[] { "https://ossrdbms-aad.database.windows.net/.default" }));

var connString = $"Host=<server>.postgres.database.azure.com;Database=<database>;"
               + $"Username=<managed-identity-name>;Password={token.Token};SSL Mode=Require";
await using var conn = new NpgsqlConnection(connString);
```

**Required env vars** (injected by Workload Identity webhook):
- `AZURE_CLIENT_ID` — used by `DefaultAzureCredential`

### Key Vault

Role assignment: `Key Vault Secrets User` (or `Key Vault Crypto User` for keys).

```python
# Python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://<vault-name>.vault.azure.net", credential=credential)
secret = client.get_secret("my-secret")
```

```csharp
// C#
var credential = new DefaultAzureCredential();
var client = new SecretClient(new Uri("https://<vault-name>.vault.azure.net"), credential);
KeyVaultSecret secret = await client.GetSecretAsync("my-secret");
```

### Azure Blob Storage

Role assignment: `Storage Blob Data Contributor` (or `Reader` for read-only).

```python
# Python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()
client = BlobServiceClient(
    account_url="https://<account>.blob.core.windows.net",
    credential=credential,
)
```

```csharp
// C#
var credential = new DefaultAzureCredential();
var client = new BlobServiceClient(
    new Uri("https://<account>.blob.core.windows.net"), credential);
```

### Azure Cache for Redis (Microsoft Entra ID Token Auth)

Role assignment: `Redis Cache Contributor` or custom data-plane role.

```python
# Python — redis-py with Microsoft Entra ID token
import os
from azure.identity import DefaultAzureCredential
import redis

credential = DefaultAzureCredential()
token = credential.get_token("https://redis.azure.com/.default")

r = redis.Redis(
    host="<cache-name>.redis.cache.windows.net",
    port=6380,
    ssl=True,
    username=os.environ["AZURE_CLIENT_ID"],
    password=token.token,
)
```

```csharp
// C#
var credential = new DefaultAzureCredential();
var token = await credential.GetTokenAsync(
    new TokenRequestContext(new[] { "https://redis.azure.com/.default" }));

var muxer = await ConnectionMultiplexer.ConnectAsync(new ConfigurationOptions
{
    EndPoints = { "<cache-name>.redis.cache.windows.net:6380" },
    Ssl = true,
    User = Environment.GetEnvironmentVariable("AZURE_CLIENT_ID"),
    Password = token.Token,
});
```

---

## Required Pod Labels and ServiceAccount Annotations

### Pod Label (on the Deployment's `spec.template.metadata.labels`)

```yaml
labels:
  azure.workload.identity/use: "true"
```

This label tells the Workload Identity webhook to inject the projected token volume
and environment variables into the pod.

### ServiceAccount Annotation

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: <app-name>
  annotations:
    azure.workload.identity/client-id: "<AZURE_CLIENT_ID>"
```

This annotation tells the webhook which Managed Identity to federate with.

### Complete Deployment Snippet

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
spec:
  template:
    metadata:
      labels:
        app: <app-name>
        azure.workload.identity/use: "true"     # ← required label
    spec:
      serviceAccountName: <app-name>            # ← references annotated SA
      automountServiceAccountToken: false        # ← DS013 (Workload Identity uses projected volume, not SA token)
      containers:
        - name: <app-name>
          # AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_FEDERATED_TOKEN_FILE
          # are injected automatically by the webhook
```

> **Note:** `automountServiceAccountToken: false` disables the *default* SA token mount.
> Workload Identity uses a separate projected volume that the webhook manages independently,
> so both can coexist without conflict.
