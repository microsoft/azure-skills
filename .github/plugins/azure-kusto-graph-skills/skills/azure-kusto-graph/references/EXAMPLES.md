# Try It Out -- azure-kusto-graph

Paste any of these into **Copilot Chat** to see the skill in action.
Cluster: `https://kc7001.eastus.kusto.windows.net`

---

## ValdyTimes (IRQL as data source -> graph operators)

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Use IRQL to get auth events in ValdyTimes and build a user-to-host graph" | `Get_Event_Authentication` -> `make-graph` -> `graph-match` |
| 2 | "Use IRQL to find failed logins, enrich with employee data, and build a graph showing roles" | IRQL enrichers -> `make-graph` with employee metadata on nodes |
| 3 | "Find the shortest auth path from external IPs to a mail server in ValdyTimes" | IRQL -> `make-graph` -> `graph-shortest-paths` |
| 4 | "Find DNS clusters of IPs and domains using connected components in ValdyTimes" | IRQL -> `make-graph` -> `graph-mark-components` |
| 5 | "Detect credential spray -- users sharing failed-login hosts in ValdyTimes" | IRQL -> `make-graph` -> bidirectional `graph-match` |
| 6 | "Combine email, auth, and process data into one investigation graph in ValdyTimes" | Multi-IRQL sources -> union -> `make-graph` |
| 7 | "Graph outbound connections from IPs to domains in ValdyTimes using IRQL extractors" | `Get_Event_NetworkOutbound` -> `Extract_Event_Network_Domain` -> `make-graph` |
| 8 | "A malicious file appeared on hosts -- graph the blast radius of processes on those hosts" | IRQL file creation -> victims -> `make-graph` -> variable-length `graph-match` |

## AzureCrest (raw KQL -> graph operators)

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Build a graph of users authenticating to hosts in AzureCrest" | `AuthenticationEvents` -> edges-first -> `make-graph` |
| 2 | "Build a graph showing which IPs authenticate as which users to which hosts in AzureCrest" | Three-entity IP -> User -> Host multi-hop graph |
| 3 | "Find users with more than 20 failed logins and the hosts they targeted in AzureCrest, as a graph" | `make-graph` -> `graph-match` with `where` constraint |
| 4 | "Find the shortest authentication path from any external IP to a critical server in AzureCrest" | `make-graph` -> `graph-shortest-paths` |
| 5 | "Find clusters of IPs and domains that communicate together in AzureCrest" | `PassiveDns` -> `make-graph` -> `graph-mark-components` |
| 6 | "Find pairs of users who both have failed logins to the same host in AzureCrest" | Bidirectional `graph-match` for credential spray detection |
| 7 | "Build an auth graph from AzureCrest and export nodes and edges as tables" | `make-graph` -> `graph-to-table` |
| 8 | "Build a graph of email senders and recipients in AzureCrest" | `Email` -> Sender -> Message -> Recipient graph |
| 9 | "Combine email, auth, and process data into one investigation graph in AzureCrest" | Multi-source union -> `make-graph` |
| 10 | "Visualize the AzureCrest authentication graph in Kusto Explorer" | `make-graph` without pipe -- triggers KE graph window |
