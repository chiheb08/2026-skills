# Redis Enterprise Cluster on OpenShift — Architecture Diagram

This file contains Mermaid diagrams that render on GitHub. See [11-redis-enterprise-openshift-architecture-and-config.md](../11-redis-enterprise-openshift-architecture-and-config.md) for full documentation.

---

## Pods and communications (overview)

```mermaid
flowchart TB
    subgraph Operator["Operator"]
        OP[redis-enterprise-operator]
    end

    subgraph NS["REC namespace"]
        S_rec["Service: rec<br/>9443, 8001"]
        S_ui["Service: rec-ui<br/>8443"]
        R0[rec-0]
        R1[rec-1]
        R2[rec-2]
        SR[rec-services-rigger]
    end

    OP -->|"K8s API"| NS
    OP -->|"GET rec:9443, pod:9443"| S_rec
    S_rec --> R0
    S_rec --> R1
    S_rec --> R2
    SR -->|"GET rec:9443/v1/nodes"| S_rec
    R0 <-.->|"Internode"| R1
    R1 <-.-> R2
    R0 <-.-> R2
```

---

## Critical path: services-rigger → RS API (9443)

```mermaid
sequenceDiagram
    participant SR as rec-services-rigger
    participant SVC as Service rec
    participant R0 as rec-0 (REC node)

    SR->>SVC: GET https://rec:9443/v1/nodes
    SVC->>R0: Forward to pod (9443)
    R0-->>SVC: Response
    SVC-->>SR: Response

    Note over SR,R0: If NetworkPolicy blocks ingress to rec-0, or Service has no endpoints, SR gets "context deadline exceeded"
```

---

## Ports and services table (reference)

| Service  | Port(s) | Targets   | Used by                    |
|----------|---------|-----------|----------------------------|
| rec      | 9443    | REC pods  | services-rigger, operator  |
| rec      | 8001    | REC pods  | Discovery                  |
| rec-ui   | 8443    | REC pods  | Cluster Manager UI         |
| rec-prom | 8070    | REC pods  | Prometheus                 |

REC pod labels (for NetworkPolicy): `app=redis-enterprise`, `redis.io/cluster=rec`, `redis.io/role=node`  
rec-services-rigger labels: `app=redis-enterprise`, `name=services-rigger`, `redis.io/cluster=rec`
