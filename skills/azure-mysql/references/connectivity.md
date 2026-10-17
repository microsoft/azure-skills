# Connectivity and Authentication

## Separate the Access Layers

| Layer | What it permits | What it does not prove |
| --- | --- | --- |
| Azure identity and RBAC | Inspect/manage the server through ARM | SQL login, database grants, or network access |
| Network and DNS | Reach the correct server endpoint | Successful TLS or authentication |
| MySQL/Entra authentication | Establish a database identity | Access to every schema/table |
| SQL grants | Perform specific database operations | Permission to change Azure resources |

Use the server-reported FQDN and configured port from the confirmed cloud. Do not assume a successful management query means a data-plane tool can connect.

## Select the Connection Path

Before using MCP for database/table discovery, schema inspection, or SQL execution, apply the [data-plane preflight](tools.md#data-plane-preflight). The inspected `@azure/mcp` 3.0.0 implementation uses the current Azure credential's Entra token and does not validate TLS certificates or hostnames, so use a verified native client for those operations. Keep MCP for management-plane inspection. A native-only server does not need its authentication configuration changed to support a read-only investigation.

## Passwordless Connection Checklist

1. Check the server's actual authentication configuration and the application's driver/version. Prefer Microsoft Entra authentication with managed identity for Azure-hosted applications when supported.
2. Configure the server's **user-assigned managed identity** for Entra principal resolution and an Entra administrator. Follow the [documented Graph permission requirements](https://learn.microsoft.com/azure/mysql/security/security-entra-authentication#permissions). Obtain tenant-administrator approval for the required consent; do not grant broad directory roles or change administrators silently.
3. Identify the **application's** managed identity, separately from the server identity. As an authorized Entra administrator, create its mapped database principal using the current [MySQL-specific setup procedure](https://learn.microsoft.com/azure/mysql/security/security-how-to-entra) and grant only necessary database operations. Do not use PostgreSQL or SQL Server principal-creation syntax.
4. Acquire a short-lived token for the documented OSS RDBMS audience in the selected cloud. Pass it directly through the driver's supported auth/token mechanism over verified TLS. Refresh tokens for new pooled connections; do not obtain one token at process startup and reuse it indefinitely.
5. Test with the mapped identity and exact database user name, not the server administrator. Inspect issuer/tenant, audience, expiration, and principal mapping on an authentication failure without printing the token.
6. Consider Entra-only authentication only after all clients, maintenance jobs, and recovery access have been verified. Disabling native auth is a separate approved change with a recovery plan, not a prerequisite to diagnose a login.

Never echo tokens or passwords, request them in chat, put them in command-line arguments, or persist them in skill artifacts. If native authentication remains necessary, use the project's secret store/Key Vault and a dedicated nonadmin database account. Unsupported MCP authentication is a tool limitation, not a reason to weaken the server's authentication.

## Choose the Correct Network Model

| Model | Required configuration | Important distinction |
| --- | --- | --- |
| Private access / VNet integration | Dedicated subnet delegated to `Microsoft.DBforMySQL/flexibleServers`, adequate IP space, private DNS and network links | Place app resources in a different subnet; establish peering/routing and DNS for remote clients |
| Public-access-mode server with Private Link | Private endpoint, approved endpoint connection, appropriate private DNS zone/links, application route | Private Link is supported for servers created in public-access mode; disable public network access after verifying the private path |
| Deliberate restricted public access | Narrow firewall rules for known application/client egress | Not the production default; do not enable all-IP or broad Azure-service access as a shortcut |

For custom DNS, verify forwarding to the correct Azure resolver and private DNS links. A VNet peering alone does not configure name resolution. Check the current supported migration path before changing an existing server's networking mode. Do not create a private endpoint on a VNet-integrated server by assumption.

Sources: [VNet integration](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-networking-vnet), [Private Link](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-networking-private-link).

## TLS and Client Verification

Keep `require_secure_transport` enabled. Use TLS 1.2 or newer; prefer TLS 1.3 where the engine and all client versions support it. A change to `tls_version` can require a restart and must not be bundled into a connectivity fix silently.

Require CA **and hostname** validation using a maintained bundle of the roots documented for the selected cloud. Do not pin a rotating leaf/intermediate certificate or copy an old single-root file indefinitely. Private connectivity does not remove the TLS requirement.

For an existing native-authentication account, an installed MySQL client can prompt securely instead of embedding a password:

```console
mysql --host MYSQL_FQDN --port MYSQL_PORT --user DATABASE_USER --ssl-mode=VERIFY_IDENTITY --ssl-ca=TRUSTED_CA_BUNDLE.pem --password
```

Use the driver's documented equivalent settings in applications. For Entra connections, follow its token/cleartext-plugin requirements **only over verified TLS**; do not place the token after `--password` in a command line.

**Verify long-token support before using a password prompt or stdin reader.** A synthetic 2,527-character input test against MySQL Shell 8.4.10 retained only 127 characters through `--passwords-from-stdin`; the [inspected reader](https://github.com/mysql/mysql-shell/blob/f6391a40bde0b4be1fdfb970ea0b1f3ca278ad21/mysqlshdk/libs/utils/utils_general.cc#L166-L182) uses a 128-byte buffer. Do not use that input path for Entra JWTs. Use a maintained driver that accepts the entire token in memory with CA and hostname validation; do not move the token into command arguments or files to work around truncation. A truncated token can produce a validation error even when its original tenant, audience, and lifetime are correct.

Test in order from the actual application runtime: FQDN resolution, TCP reachability to the configured port, verified TLS handshake, database login, then a minimal read under the app's grants. Record the failing layer and exact error; do not disable TLS, widen a firewall, or reset credentials to skip this investigation.

Sources: [Entra authentication](https://learn.microsoft.com/azure/mysql/security/security-entra-authentication), [TLS and trusted roots](https://learn.microsoft.com/azure/mysql/security/security-tls-how-to-connect).
