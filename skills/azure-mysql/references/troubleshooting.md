# MySQL Troubleshooting

## Evidence Before Remediation

Establish the exact server/database, engine and driver versions, configured network/authentication model, affected operations, impact, UTC incident window, and recent deployment/configuration changes. Use supplied evidence first. If live access is prohibited or not authorized, do not collect from Azure.

For permitted collection:

1. Check Azure Service Health/resource health and the server's operational state; correlate maintenance, failover, scaling, and parameter/network changes. A resource existing in ARM is not evidence of a healthy database.
2. Use [MySQL tools](tools.md) to inspect server configuration and relevant parameter values before recommending a change.
3. Discover Azure Monitor metric definitions, then collect time-bounded CPU, memory, storage/I/O, connections, and replication signals relevant to the incident. Use the server's exact resource ID and supported aggregations.
4. Inspect enabled log categories, diagnostic settings, destination workspace, retention, and table schema before querying logs. Do not assume logs are enabled, historical data exists, or every workspace uses `AzureDiagnostics`. Use `azure-kusto` when available for the discovered schema.
5. Compare the failing period with a baseline and the application timeline. Separate observations from hypotheses; an empty query or missing telemetry does not prove that no incident occurred.

Sources: [Monitoring](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-monitor-mysql), [supported metrics and logs](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-monitor-mysql-reference).

## Symptom Routing

| Symptom | Inspect first | Do not do by default |
| --- | --- | --- |
| Timeout / error 2003 | App-side DNS, FQDN/port, routes/NSGs, firewall or private endpoint, server state | Open all IPs or assume `az login` proves connectivity |
| TLS failure / error 2026 or 3159 | Trust bundle, hostname, client TLS support, secure-transport settings | Disable TLS or certificate validation |
| Access denied / error 1045 | Mapped user, auth mode, token tenant/audience/expiry, SQL grants | Reset the admin password or grant broad privileges |
| Too many connections / error 1040 | Pool totals across app instances, leaks, idle sessions, connection limits and memory | Raise `max_connections` without a capacity assessment |
| High CPU or slow queries | Query latency/throughput, plans/indexes, concurrency, I/O waits, Burstable CPU credits | Scale immediately or copy a self-managed tuning value |
| Lock timeout / error 1205 or deadlock / error 1213 | Transaction duration, lock order, relevant indexes and blocking evidence | Kill sessions or replay writes without understanding effects |
| Storage pressure or read-only state | Free space, growth, binlogs/large transactions, autogrow and maximum capacity | Delete managed files or promise storage can shrink later |
| Replication lag | Primary write rate, replica CPU/I/O, long transactions, primary keys, replication health | Promote a lagging replica as a routine performance fix |

For connectivity, load [the layer-by-layer checklist](connectivity.md). For failover, recovery, and replication decisions, load [reliability and lifecycle](reliability.md).

## Query Performance

Start with existing slow logs, query statistics, and [explicit schema/index inspection](tools.md#schema-and-index-inspection); the MCP schema tool's column-only output does not include indexes or constraints. Apply the data-plane preflight before SQL collection and use a verified native client when MCP cannot meet it. When permitted and supported by the engine, inspect bounded statement digest metadata without returning SQL literals or application rows:

```sql
SELECT SCHEMA_NAME, DIGEST, COUNT_STAR, SUM_TIMER_WAIT, SUM_ROWS_EXAMINED
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
ORDER BY SUM_TIMER_WAIT DESC, DIGEST
LIMIT 10;
```

Check Performance Schema availability and privileges first. These are cumulative counters since their last reset, not measurements of the incident window; compare snapshots/deltas and correlate with time-bounded logs. Do not enable instrumentation, clear counters, or broaden privileges silently.

For a specific statement, inspect its plan and parameter/selectivity behavior with an authorized client. `EXPLAIN ANALYZE` **executes** the statement and is not a harmless default production probe. Index changes, table maintenance, session termination, and parameter changes require impact review and approval. Reproduce on a representative nonproduction copy where possible.

If slow-query logging is disabled, explain that enabling it cannot recreate past logs. Propose a bounded capture window, threshold, destination/retention, overhead and sensitive-data controls. Record previous values and obtain approval before changing logging parameters or diagnostic settings; restore temporary settings after the approved window.

Sources: [Azure query performance guidance](https://learn.microsoft.com/azure/mysql/flexible-server/how-to-troubleshoot-query-performance-new#listing-the-most-used-queries-on-the-database-server), [Performance Schema digest summaries](https://docs.oracle.com/cd/E17952_01/mysql-8.4-en/performance-schema-statement-summary-tables.html), [slow-query logging](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-slow-query-logs). Use the manual matching the actual engine version for version-specific queries.

## Remediation and Evidence

Choose the smallest evidence-supported change. State its target, expected benefit, downtime/cost/security impact, approval needed, and rollback. Capture before/after metrics over comparable load, re-read configuration, and repeat the original failing operation using the application's identity and network. Report unresolved hypotheses explicitly instead of declaring a root cause from one metric. Never invent missing logs, support-case evidence, or successful tests.
