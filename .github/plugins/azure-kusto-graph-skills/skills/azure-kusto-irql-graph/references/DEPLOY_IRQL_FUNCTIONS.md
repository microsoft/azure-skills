# Deploy IRQL Graph Functions

The `Lift_To_Graph`, `Graph_Render_View`, and `Graph_Fold_By_Property` functions must be present in the target Kusto database. They are pre-deployed on the kc7001 example cluster but may be missing on other clusters.

## Check for existing functions

```kql
.show functions
| where Name in~ ("Lift_To_Graph", "Graph_Render_View", "Graph_Fold_By_Property")
| project Name
```

If any required function is missing, deploy it using the `.create-or-alter` commands below.

## Lift_To_Graph

```kql
.create-or-alter function with (folder="irql_draft", docstring="Transforms a generic table to a Kusto graph table using the given JSON mapping")
Lift_To_Graph(T:(), mappingJson:string)
{
let calcIcon = (T:(type:string, defIcon:string)) {
    T
    | extend iconUrl = defIcon
    | project-away defIcon
};
let mapping = (mapping_json:string) {
    parse_json(mapping_json)
};
let Tpacked = (T:()) {
    T | extend _row = pack_all()
};
let KustoResultsToNodes = (T:(), mapping_json:dynamic) {
    let NodeExpanded =
        Tpacked(T)
        | mv-expand nodeDef = mapping(mapping_json).node_types to typeof(dynamic)
        | extend name=tostring(_row[tostring(nodeDef.key)]),
                 type=tostring(nodeDef.type),
                 _nodeKeys=iif(isnull(nodeDef.props),dynamic([]),nodeDef.props),
                 defaults=nodeDef.defaults
        | extend nodeColor=iff(isnotnull(nodeDef.color), tostring(_row[tostring(nodeDef.color)]), "")
        | extend nodeSize=iff(isnotnull(nodeDef.size), toreal(_row[tostring(nodeDef.size)]), 1.0)
        | extend iconColor=iff(isnotnull(nodeDef.iconColor), tostring(_row[tostring(nodeDef.iconColor)]), "")
        | extend id = strcat(nodeDef.id,"/",name)
        | extend nodeDisplayName=iff(isnotnull(nodeDef.displayName),
                    strcat(type,'/',tostring(_row[tostring(nodeDef.displayName)])), id)
        | extend defIcon = iif(isnotempty(nodeDef.defIcon), nodeDef.defIcon, "")
        | where isnotempty(split(id, "/")[-1])
        | extend type = tostring(nodeDef.type)
        | extend iconUrl=""
        | invoke calcIcon();
    let NodePropsFilled = (T:(_row:dynamic, _nodeKeys:dynamic, id:string, type:string,
            nodeDisplayName:string, nodeColor:string, nodeSize:real,
            iconUrl:string, iconColor:string, defaults:dynamic)) {
        T
        | mv-expand k=_nodeKeys to typeof(string)
        | extend v=_row[k], def=defaults[k]
        | extend v = iif(isnull(v) or isempty(tostring(v)), iif(isnull(def), v, def), v)
        | summarize properties=make_bag(bag_pack(k,v))
            by id,type,nodeDisplayName,nodeColor,nodeSize,iconUrl,iconColor
    };
    let NodeNoProps = (T:(_nodeKeys:dynamic, id:string, type:string,
            nodeDisplayName:string, nodeColor:string, nodeSize:real,
            iconUrl:string, iconColor:string)) {
        T
        | where array_length(_nodeKeys)==0
        | extend properties=dynamic({})
        | project id,type,properties,nodeDisplayName,nodeColor,nodeSize,iconUrl, iconColor
    };
    let Nodes = (T:(_row:dynamic, _nodeKeys:dynamic, id:string, type:string,
            nodeDisplayName:string, nodeColor:string, nodeSize:real,
            iconUrl:string, iconColor:string, defaults:dynamic))
    {
        union
            NodePropsFilled(T),
            NodeNoProps(T)
        | project id,type,properties,nodeDisplayName,nodeColor,nodeSize,iconUrl, iconColor
    };
    union
        (T | extend EntityType = "data"),
        (Nodes(NodeExpanded) | extend EntityType = "node")
};
let KustoResultsToEdges = (T:(EntityType:string, ),mapping_json:dynamic) {
    let edges = datatable(SourceId:string, TargetId:string) [];
    let EdgeExpanded =
        Tpacked((T | where EntityType == "data"))
        | extend nodeDef = mapping(mapping_json).node_types
        | mv-expand edgeDef = mapping(mapping_json).edges to typeof(dynamic)
        | mv-apply nodeDefSrc = nodeDef on (
            where tostring(nodeDefSrc["type"]) == tostring(edgeDef.source.type))
        | extend SourceId = strcat(nodeDefSrc.id,"/",tostring(_row[tostring(nodeDefSrc.key)]))
        | mv-apply nodeDefTgt = nodeDef on (
            where tostring(nodeDefTgt["type"]) == tostring(edgeDef.target.type))
        | extend TargetId = strcat(nodeDefTgt.id,"/",tostring(_row[tostring(nodeDefTgt.key)]))
        | extend edgeType=tostring(edgeDef.type),
                 _edgeKeys=iif(isnull(edgeDef.props),dynamic([]),edgeDef.props)
        | extend edgeDisplayName = iff(isnotnull(edgeDef.displayName),
                    strcat(edgeType,'/',tostring(_row[tostring(edgeDef.displayName)])), edgeType)
        | extend edgeColor= iff(isnotnull(edgeDef.color),
                    tostring(_row[tostring(edgeDef.color)]), edgeType);
    let EdgePropsFilled = (T:(_row:dynamic, _edgeKeys:dynamic,
            SourceId:string, TargetId:string, edgeType:string,
            edgeDisplayName:string, edgeColor:string)) {
        T
        | mv-expand k=_edgeKeys to typeof(string)
        | extend v=_row[k]
        | summarize edgeProperties=make_bag(bag_pack(k,v))
            by SourceId,TargetId,edgeType,edgeDisplayName,edgeColor
    };
    let EdgeNoProps = (T:(_edgeKeys:dynamic, SourceId:string, TargetId:string,
            edgeType:string, edgeDisplayName:string, edgeColor:string)) {
        T
        | where array_length(_edgeKeys)==0
        | extend edgeProperties=dynamic({})
        | project SourceId,TargetId,edgeType, edgeProperties,edgeDisplayName,edgeColor
    };
    let Edges = (T:(_edgeKeys:dynamic, SourceId:string, TargetId:string,
            edgeType:string, edgeDisplayName:string, edgeColor:string)) {
        union
            EdgePropsFilled(EdgeExpanded),
            EdgeNoProps(EdgeExpanded)
        | where isnotempty(split(SourceId, "/")[-1]) and isnotempty(split(TargetId, "/")[-1])
        | project-reorder SourceId,TargetId,edgeType,edgeProperties,edgeDisplayName,edgeColor
    };
    union
        (T | where EntityType=="node"),
        (Edges(EdgeExpanded) | extend EntityType = "edge")
};
T
| invoke KustoResultsToNodes(mappingJson)
| invoke KustoResultsToEdges(mappingJson)
| where EntityType != "data"
| project EntityType, id, type, properties, nodeDisplayName, nodeColor, nodeSize,
         iconUrl, iconColor, SourceId, TargetId, edgeType, edgeProperties,
         edgeDisplayName, edgeColor
}
```

## Graph_Render_View

```kql
.create-or-alter function with (folder="irql_draft", docstring="Renders a graph table using make-graph in Kusto Explorer")
Graph_Render_View(T:(id:string, type:string, properties:dynamic, nodeDisplayName:string,
    nodeColor:string, nodeSize:real, iconUrl:string, iconColor:string,
    SourceId:string, TargetId:string, edgeType:string, edgeProperties:dynamic,
    edgeDisplayName:string, edgeColor:string, EntityType:string))
{
let NodesTable =
    T
    | where EntityType=="node"
    | project id, type, properties, nodeDisplayName, nodeColor, nodeSize, iconUrl, iconColor;
let EdgesTable =
    T
    | where EntityType=="edge"
    | project SourceId, TargetId, type=edgeType, properties=edgeProperties, edgeDisplayName, edgeColor;
// #graph-style("Default")
let Default = dynamic({
    "name":"Default",
    "graph_style":{
        "layout":{"kind":"Grouped"},
        "nodes_config":{
            "density":80.0,
            "label_by":"id",
            "color_by":"iconUrl",
            "lifetime_start_by":"",
            "lifetime_end_by":"",
            "image_url_by":"iconUrl",
            "image_size":2.0
        },
        "edges_config":{
            "lifetime_start_by":"",
            "lifetime_end_by":""
        }
    },
    "script":"// Use right-click on the nodes to explore interactive operations over the graph.",
    "matches":[]
});
EdgesTable
| make-graph SourceId --> TargetId with (NodesTable) on id
}
```

## Graph_Fold_By_Property

```kql
.create-or-alter function with (folder="irql_draft", docstring="Folds nodes of a given type by a shared property value into single collapsed nodes")
Graph_Fold_By_Property(T:(EntityType:string, id:string, type:string, properties:dynamic,
    nodeDisplayName:string, nodeColor:string, nodeSize:real,
    iconUrl:string, iconColor:string,
    SourceId:string, TargetId:string, edgeType:string, edgeProperties:dynamic,
    edgeDisplayName:string, edgeColor:string), NodeType:string, PropertyName:string)
{
let Nodes =
    T
    | where EntityType == "node"
    | project EntityType, id, type, properties, nodeDisplayName, nodeColor, nodeSize, iconUrl, iconColor,
             SourceId="", TargetId="", edgeType="", edgeProperties=dynamic(null),
             edgeDisplayName="", edgeColor="";
let Edges =
    T
    | where EntityType == "edge"
    | project EntityType, id="", type="", properties=dynamic({}),
             nodeDisplayName="", nodeColor="", nodeSize=real(0), iconUrl="", iconColor="",
             SourceId, TargetId, edgeType, edgeProperties, edgeDisplayName, edgeColor;
let FoldedNodes =
    Nodes
    | where type == NodeType
    | where isnotempty(properties[PropertyName])
    | extend val = tostring(properties[PropertyName])
    | summarize members = make_list(id), memberCount = count() by val
    | where memberCount > 1
    | extend
        id = strcat(PropertyName, "/", val),
        type = PropertyName,
        EntityType = "node",
        properties = pack("folded", val,
                         "memberCount", memberCount,
                         "members", members),
        nodeDisplayName = strcat(PropertyName, "/", val),
        nodeColor = "", nodeSize = real(0),
        iconUrl = "", iconColor = ""
    | project EntityType, id, type, properties, nodeDisplayName, nodeColor, nodeSize, iconUrl, iconColor,
             SourceId="", TargetId="", edgeType="", edgeProperties=dynamic(null),
             edgeDisplayName="", edgeColor="";
let MemberToFold =
    Nodes
    | where type == NodeType
    | where isnotempty(properties[PropertyName])
    | extend val = tostring(properties[PropertyName])
    | join kind=inner (
        FoldedNodes
        | extend val = tostring(properties["folded"])
        | project val, foldId=id
      ) on val
    | project memberId=id, foldId;
let RewiredEdges =
    Edges
    | lookup kind=leftouter (MemberToFold | project SourceId=memberId, FoldSourceId=foldId) on SourceId
    | lookup kind=leftouter (MemberToFold | project TargetId=memberId, FoldTargetId=foldId) on TargetId
    | extend
        NewSourceId = coalesce(FoldSourceId, SourceId),
        NewTargetId = coalesce(FoldTargetId, TargetId)
    | where NewSourceId != NewTargetId
    | project EntityType="edge",
             id="", type="", properties=dynamic({}),
             nodeDisplayName="", nodeColor="", nodeSize=real(0), iconUrl="", iconColor="",
             SourceId=NewSourceId, TargetId=NewTargetId, edgeType, edgeProperties,
             edgeDisplayName, edgeColor;
let FoldedMemberIds = MemberToFold | distinct memberId;
union
    (Nodes | where id !in (FoldedMemberIds)),
    FoldedNodes,
    RewiredEdges
}
```

## Deploying all three functions

Run each `.create-or-alter` block above in Kusto Explorer or the ADX web UI against your target database. The functions are placed in the `irql_draft` folder.

After deployment, verify:

```kql
.show functions
| where Name in~ ("Lift_To_Graph", "Graph_Render_View", "Graph_Fold_By_Property")
| project Name, Folder, DocString
```
