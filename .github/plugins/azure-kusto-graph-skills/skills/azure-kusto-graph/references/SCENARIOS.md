
## Practical Usage Scenarios

### Scenario 1: "Who can reach the database server?"

Start from all users, find any path to a critical asset through authentication and network hops:

```kql
let auth_edges = AuthenticationEvents
    | where result == "Successful Login"
    | project Source = username, Target = hostname, edgeType = "LoggedInto";
let net_edges = NetworkFlows
    | where dst_port in (1433, 3306, 5432)  // DB ports
    | project Source = src_host, Target = dst_host, edgeType = "NetworkAccess";
let all_edges = union auth_edges, net_edges;
let nodes = union
    (all_edges | distinct Source | project nodeId = Source),
    (all_edges | distinct Target | project nodeId = Target);
all_edges
| make-graph Source --> Target with nodes on nodeId
| graph-shortest-paths (user)-[path*1..5]->(db)
    where db.nodeId == "DB-SERVER-PROD"
    project
        User = user.nodeId,
        PathLength = array_length(path),
        Route = path.Target
| order by PathLength asc
```

### Scenario 2: "Are there isolated networks?"

Find disconnected clusters in your network flow data -- useful for segmentation validation:

```kql
let edges = NetworkFlows
    | summarize Bytes = sum(bytes) by Source = src_ip, Target = dst_ip;
let nodes = union
    (edges | distinct Source | project nodeId = Source),
    (edges | distinct Target | project nodeId = Target);
edges
| make-graph Source --> Target with nodes on nodeId
| graph-mark-components with_component_id = Segment
| graph-to-table nodes
| summarize Hosts = make_list(nodeId), Size = count() by Segment
| order by Size desc
```

### Scenario 3: "Show me the blast radius of a compromised account"

Given a compromised user, find everything reachable within N hops:

```kql
let edges = union
    (AuthenticationEvents | project Source = username, Target = hostname),
    (FileCreationEvents | project Source = username, Target = hostname);
let nodes = union
    (edges | distinct Source | project nodeId = Source),
    (edges | distinct Target | project nodeId = Target);
edges
| make-graph Source --> Target with nodes on nodeId
| graph-match (compromised)-[e*1..3]->(reached)
    where compromised.nodeId == "jsmith"
    project
        Depth = array_length(e),
        ReachedEntity = reached.nodeId
| summarize ReachedEntities = make_set(ReachedEntity) by Depth
```

### Scenario 4: "Build a reusable security graph for the SOC team"

Create a persistent graph model so analysts can query without rebuilding:

```kql
// Step 1: Define the model (run once, requires Database Admin)
.create-or-alter graph_model SOC_Graph
{
  "Schema": {
    "Nodes": {
      "User": {"username": "string", "role": "string"},
      "Host": {"hostname": "string"},
      "IP":   {"ip": "string"}
    },
    "Edges": {
      "AuthTo": {"result": "string", "timestamp": "datetime"},
      "FromIP": {"timestamp": "datetime"}
    }
  },
  "Definition": {
    "Steps": [
      {"Kind": "AddNodes", "Query": "Employees | project username, role", "NodeIdColumn": "username", "Labels": ["User"]},
      {"Kind": "AddNodes", "Query": "AuthenticationEvents | distinct hostname | project hostname", "NodeIdColumn": "hostname", "Labels": ["Host"]},
      {"Kind": "AddEdges",
       "Query": "AuthenticationEvents | project username, hostname, result, timestamp",
       "SourceColumn": "username",
       "TargetColumn": "hostname",
       "Labels": ["AuthTo"]}
    ]
  }
}
```

// Step 2: Snapshot (run daily or on-demand)
.make graph_snapshot SOC_Graph Daily_2025_07_30

// Step 3: Any analyst can now query without setup
graph("SOC_Graph")
| graph-match (user)-[auth]->(host)
    where auth.result == "Failed Login"
    project User = user.username, Role = user.role, Host = host.hostname, Time = auth.timestamp
| summarize FailedLogins = count() by User, Role, Host
| order by FailedLogins desc
```

## MCP Tools Used
