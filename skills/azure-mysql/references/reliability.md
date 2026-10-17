# Reliability and Lifecycle

Define workload RPO/RTO and acceptable downtime before choosing a mechanism. Inspect current version, SKU, region, topology, authentication, networking, backup configuration, and actual recoverable points; do not infer them from a template or from a server name.

## Select the Right Mechanism

| Mechanism | Protects or enables | Does not provide |
| --- | --- | --- |
| Zone-redundant HA | Managed failover across availability zones within a region | Protection against logical deletion or a whole-region outage |
| Local/same-zone HA | Managed failover for server-level failure | Protection against an availability-zone outage |
| Read replica | Asynchronous read scaling; potential cross-region recovery option | Automatic HA, zero replication lag, or guaranteed zero-data-loss promotion |
| Point-in-time restore | Recovery from corruption/deletion within available backup history | An in-place undo or immediate application cutover |
| Geo-redundant backup/geo-restore | Regional disaster-recovery option where configured and supported | Zero RPO or a fixed restore duration |

The HA standby is **not readable**; use read replicas for read traffic. Verify tier/region eligibility and current limits before recommending replicas or HA. Zone-redundant HA is a creation-time choice under the current service guidance; an existing non-HA server can require a new server and migration.

HA failover can drop connections. Use FQDNs, bounded reconnect/backoff, and transaction-aware recovery. An application must not replay a potentially committed write blindly. Only run a forced failover test after approval and with an agreed observation window.

Sources: [High availability](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-high-availability), [read replicas](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-read-replicas).

## Backup and Restore Workflow

1. Read the actual retention, available restore timestamps, backup redundancy, and encryption-key access. Check residency and regional restore support. Redundancy changes have configuration-dependent constraints; do not assume all existing servers can switch backup modes in place.
2. Choose a recovery time **before** corruption/deletion and explain the potential loss of later valid writes. For a single table, plan recovery on a separate server and a separately approved selective data reconciliation.
3. Present the source ID, UTC restore point, new target server/name/region, network/DNS, identity, cost, verification, and cutover/rollback plan. Restore creates a **new server**, not an overwrite of the source.
4. After explicit approval, restore through the documented management workflow. Inspect target configuration; verify data and application behavior before changing routing. Recheck users/grants, Entra configuration, firewall/private connectivity, HA, monitoring, and backup settings rather than assume they were inherited.
5. Approve cutover separately. Retain the source until the agreed rollback window closes; deletion is not an implicit cleanup step. Record observed restore time and data loss against RPO/RTO rather than promise an SLA.

Managed backups are not downloadable database dumps. Use approved logical export tools when portable data export is required, with destination and sensitive-data controls.

Source: [Backup and restore](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-backup-restore).

## Replica Promotion and Disaster Recovery

Measure lag and confirm replica health, endpoint, capacity, application grants, and authentication. Promotion/cutover can lose unreplicated writes and changes the topology. Fence writes to the old primary where possible to prevent split-brain, get explicit approval for the accepted loss and new write target, and verify application read/write routing. Do not use promotion as a shortcut for ordinary lag troubleshooting.

## Migration and Major-Version Upgrade

- Check the current [version support policy](https://learn.microsoft.com/azure/mysql/concepts-version-policy) and the application's drivers, SQL modes, character sets/collations, auth plugins, schema features, routines, and privileges. Choose a supported GA target; preview/innovation versions are not production defaults.
- Select offline dump/restore when downtime is acceptable, or a documented migration/replication service when the workload requires reduced downtime. Assess data size, network throughput, compatibility, validation, and cutover before choosing tooling. Do not silently provision a migration service.
- Rehearse on a restored copy with representative queries and load. Check the current major-upgrade procedure and required upgrade checks. Do not skip required intermediate major versions or promise zero downtime because HA is enabled.
- Capture a verified pre-upgrade recovery point. An in-place downgrade is not a rollback plan: plan restore/cutback, data reconciliation, and the fate of writes made after cutover. Get explicit approval for the maintenance window.
- Verify engine/authentication, data consistency, representative query plans, application behavior, replica topology, and recovery settings afterward.

Sources: [Major upgrades and limitations](https://learn.microsoft.com/azure/mysql/flexible-server/how-to-upgrade-faq), [migration with dump/restore](https://learn.microsoft.com/azure/mysql/concepts-migrate-dump-restore).
