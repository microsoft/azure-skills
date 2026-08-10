# Try It Out -- azure-kusto-irql-graph

Paste any of these into **Copilot Chat** to see the skill in action.
Cluster: `https://kc7001.eastus.kusto.windows.net`

Supply the source KQL/IRQL pipeline with the graph description. The skill maps the query's output columns; it does not normally author the underlying investigation query.

Use this skill for `Lift_To_Graph`, rendering, folding, and IRQL graph extraction/enrichment functions. Use `azure-kusto-graph` for native `make-graph`, `graph-match`, paths, components, graph models, and snapshots.

Before trying the prompts on another database, verify `Lift_To_Graph` and `Graph_Render_View` with `.show functions`; also verify `Graph_Fold_By_Property` or enrichers when a prompt uses them. Deploy missing definitions from `references/DEPLOY_IRQL_FUNCTIONS.md`.

---

## ValdyTimes (IRQL selectors -> Lift_To_Graph)

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Given `Get_Event_Authentication_All | take 200`, create a graph showing users authenticating to hosts" | User + Host mapping -> `Lift_To_Graph` -> `Graph_Render_View` |
| 2 | "Given `Get_Event_Authentication_All | where Result == 'Failed Login' | take 100`, show IPs connecting to hosts through authentication events" | SrcIp -> AuthEvent -> Host with 3 node types |
| 3 | "Given `Get_Email_All | take 300`, visualize email flow between senders and recipients" | Sender -> Message -> Recipient mapping |
| 4 | "Given `Get_Email_All | take 400`, graph emails and collapse messages by verdict" | Email mapping -> `Graph_Fold_By_Property("EmailMessage", "Verdict")` |
| 5 | "Given `Get_Event_Process_All | where ProcessCommandLine has 'powershell' | take 200`, show process execution trees with hosts and users" | Process -> ParentProcess + Host + User mapping |
| 6 | "Given my query returning `ClientIp`, `DomainName`, and `EnvTime`, graph outbound connections and label IPs with employee names" | Network mapping -> `Enrich_Node_Ip_Employee` -> render |
| 7 | "Create a graph mapping for file creation events showing which user created which file on which host" | Open-ended -- Copilot generates a new mapping JSON |
| 8 | "Use the known outbound-network selector to graph connections to raisinkanes.com and show who's behind each IP" | Basic source fallback -> filter -> `Lift_To_Graph` -> enrich -> fold -> render |

## AzureCrest (raw KQL -> Lift_To_Graph)

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Given `Email | take 400`, create a graph showing email flow between senders and recipients" | Raw `Email` -> mapping -> `Lift_To_Graph` -> `Graph_Render_View` |
| 2 | "Graph emails in AzureCrest and collapse messages by verdict" | Email mapping -> `Graph_Fold_By_Property("EmailMessage", "verdict")` |
| 3 | "Given `AuthenticationEvents | take 200`, create a Lift_To_Graph visualization of users authenticating to hosts" | Raw `AuthenticationEvents` -> User + Host mapping |
| 4 | "Show IPs connecting to hosts through auth events in AzureCrest, with user nodes" | 4-entity auth mapping: SrcIp -> AuthEvent -> Host + User |
| 5 | "Show process execution trees for hosts running powershell in AzureCrest" | Raw `ProcessEvents` -> Process -> Parent + Host + User |
| 6 | "Graph outbound network connections from IPs to domains in AzureCrest" | Raw `OutboundNetworkEvents` -> IP -> Domain mapping |
| 7 | "Create a graph of file creation events in AzureCrest showing users, files, and hosts" | Raw `FileCreationEvents` -> User + File + Host mapping |
| 8 | "Graph DNS lookups in AzureCrest and fold IPs by domain" | `PassiveDns` -> IP -> Domain mapping -> fold by domain |
