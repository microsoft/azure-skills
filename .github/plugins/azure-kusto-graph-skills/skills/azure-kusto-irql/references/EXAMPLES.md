# Try It Out -- azure-kusto-irql

Paste any of these into **Copilot Chat** to see the skill in action.
Cluster: `https://kc7001.eastus.kusto.windows.net`

---

## ValdyTimes (IRQL functions: `Get_*`, `Extract_*`, `Enrich_*`)

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Find all failed logins in ValdyTimes" | Basic `Get_Event_Authentication` with filter |
| 2 | "Which sender domains are emailing executives?" | `Get_Email` -> `Extract_Email_Sender_Domain` -> `Enrich_Username_Employee` |
| 3 | "Show me users with more than 20 failed logins and their job roles" | `Get_Event_Authentication` -> `summarize` -> `Enrich_Username_Employee` |
| 4 | "Find powershell or rundll32 execution on any host" | `Get_Event_Process` with command-line filter |
| 5 | "What domains are being accessed by IPs with failed logins?" | Auth -> distinct IPs -> `Enrich_Ip_Domain` |
| 6 | "Find authentication from external IPs" | `Get_Event_Authentication_All` with RFC1918 exclusion |
| 7 | "A file called Raisin_Kane appeared on some hosts. What processes ran on those hosts?" | `Get_Event_FileCreation_All` -> victim hosts -> `Get_Event_Process` |
| 8 | "Which users are logging in from the most distinct IPs?" | `Get_Event_Authentication_All` -> `summarize dcount(ClientIp) by Username` |

## AzureCrest (raw KQL — no IRQL)

AzureCrest has no IRQL functions. In this environment, route to the `azure-kusto` skill to author raw KQL equivalents (do not use `azure-kusto-irql`).

| # | Ask This | What It Does |
|---|----------|--------------|
| 1 | "Find all failed logins in AzureCrest" | Raw `AuthenticationEvents` with `result` filter |
| 2 | "Which sender domains are emailing executives in AzureCrest?" | `Email` -> extract domain -> join `Employees` |
| 3 | "Show users with more than 20 failed logins and their roles in AzureCrest" | `AuthenticationEvents` -> `summarize` -> join `Employees` |
| 4 | "Find powershell execution across all hosts in AzureCrest" | `ProcessEvents` with `process_commandline` filter |
| 5 | "What domains are accessed by IPs with failed logins in AzureCrest?" | `AuthenticationEvents` -> distinct `src_ip` -> join `PassiveDns` |
| 6 | "Find authentication from external IPs in AzureCrest" | `AuthenticationEvents` with RFC1918 exclusion |
