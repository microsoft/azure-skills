# Architecture Diagram Template

Render this mermaid diagram in the terminal, replacing all `{{PLACEHOLDER}}` tokens with detected values from Section 1 (Detection) and the chosen backing services.

## Diagram

~~~mermaid
flowchart LR
    Users([Users]) -->|HTTPS| GW

    subgraph AKS["AKS Cluster: {{AKS_CLUSTER_NAME}}"]
        direction LR
        GW[{{INGRESS_TYPE}}] --> SVC[Service\n{{APP_NAME}}:{{PORT}}]
        SVC --> DEP[Deployment\n{{REPLICA_COUNT}} replicas]
    end

    DEP -.->|Workload Identity| MI[Managed Identity\n{{IDENTITY_NAME}}]
    ACR[ACR\n{{ACR_NAME}}.azurecr.io] -->|pull| AKS
    CICD[GitHub Actions] -->|push| ACR

    %% Backing services — include only those in the architecture contract
    %% Delete lines for services not selected
    DEP -.->|Workload Identity| PG[(PostgreSQL\n{{PG_SERVER_NAME}})]
    DEP -.->|Workload Identity| REDIS[(Redis\n{{REDIS_NAME}})]
    DEP -.->|Workload Identity| KV[Key Vault\n{{KV_NAME}}]

    MON[Log Analytics\n{{LAW_NAME}}] -..- AKS

    style AKS fill:#e8f5e9,stroke:#107C10,stroke-width:2px
    style ACR fill:#e3f2fd,stroke:#0078D4
    style PG fill:#fff3e0,stroke:#f57c00
    style REDIS fill:#fce4ec,stroke:#c62828
    style KV fill:#f3e5f5,stroke:#7b1fa2
    style MON fill:#f5f5f5,stroke:#757575
~~~

## Rendering instructions

Output this diagram as a fenced mermaid code block in the terminal. The developer will see it rendered if their terminal/tool supports mermaid, or as readable text if not.

After the diagram, output a cost estimate table listing each Azure resource with its SKU/tier and approximate monthly cost. Use your knowledge of Azure pricing to provide estimates.
