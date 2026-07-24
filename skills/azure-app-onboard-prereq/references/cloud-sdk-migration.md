# Non-Azure Cloud Service Dependencies

> Detected during Step 2 manifest scan. The `ask_user` redirect gate is handled in SKILL.md Step 2 — this file defines the classification rules.

Functional cloud SDK deps are 🔶 `CLOUD_SDK_MIGRATION`. Populate `prereq-output.json.cloudSdkFindings[]`.

| Found Dependency | Azure Equivalent |
|-----------------|-----------------|
| AWS DynamoDB (`AWSSDK.DynamoDBv2`, `@aws-sdk/client-dynamodb`), GCP Firestore | Cosmos DB (NoSQL API) |
| AWS Cognito (`AWSSDK.CognitoIdentityProvider`, `amazon-cognito-identity-js`), Firebase auth (`firebase-admin`) | Entra ID / Entra External ID |
| AWS S3, GCP Cloud Storage (`@google-cloud/storage`), MinIO | Azure Blob Storage |
| AWS Lambda, GCP Cloud Functions (handler signatures) | Azure Functions (rewrite handlers) |
| AWS SQS (`@aws-sdk/client-sqs`, `AWSSDK.SQS`), GCP Cloud Tasks (`google-cloud-tasks`) | Queue Storage / Service Bus |
| AWS SNS (`@aws-sdk/client-sns`, `AWSSDK.SimpleNotificationService`), GCP Pub/Sub (`google-cloud-pubsub`) | Service Bus / Event Grid |
| Firebase (`firebase`, `firebase-admin`) full stack | Entra ID + Cosmos DB + Functions |

> **Observability carve-out:** Observability deps are ⚠️ WARN (app runs without them), NOT 🔶. Use this table to distinguish:
>
> | Package | Classification | Why |
> |---------|---------------|-----|
> | `@google-cloud/opentelemetry-*` | ⚠️ WARN | Telemetry — app works without it |
> | `@google-cloud/logging` | ⚠️ WARN | Logging — app works without it |
> | `@google-cloud/monitoring` | ⚠️ WARN | Monitoring — app works without it |
> | `aws-xray-sdk`, `aws-rum-web` | ⚠️ WARN | Tracing/RUM — app works without it |
> | `google-cloud-tasks` | 🔶 CLOUD_SDK_MIGRATION | Functional — app breaks without it |
> | `google-cloud-pubsub` | 🔶 CLOUD_SDK_MIGRATION | Functional — app breaks without it |
> | `google-cloud-storage` | 🔶 CLOUD_SDK_MIGRATION | Functional — app breaks without it |
> | `@aws-sdk/client-dynamodb`, `boto3` (DynamoDB) | 🔶 CLOUD_SDK_MIGRATION | Functional — app breaks without it |
> | `@aws-sdk/client-sqs`, `@aws-sdk/client-sns` | 🔶 CLOUD_SDK_MIGRATION | Functional — app breaks without it |
