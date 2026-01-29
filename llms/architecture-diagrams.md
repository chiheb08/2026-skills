# LiteLLM Local Models - Architecture Diagrams

This document contains interactive Mermaid diagrams that can be rendered in GitHub, GitLab, and many markdown viewers.

---

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph Clients["Client Services Layer"]
        RAG["RAG System"]
        Code["Code Support"]
        Apps["Custom Apps"]
    end
    
    subgraph LiteLLM["LiteLLM Proxy Layer"]
        Router["Router & Load Balancer"]
        RateLimit["Rate Limiter"]
        Cache["Cache Manager"]
    end
    
    subgraph vLLM["vLLM Backend Layer"]
        L7B1["Llama 2 7B<br/>Instance 1"]
        L7B2["Llama 2 7B<br/>Instance 2"]
        C13B["CodeLlama 13B"]
        M7B["Mistral 7B"]
    end
    
    subgraph Support["Supporting Services"]
        Redis["Redis<br/>(Cache/LB)"]
        DB["PostgreSQL<br/>(Keys/Spend)"]
    end
    
    RAG --> Router
    Code --> Router
    Apps --> Router
    
    Router --> RateLimit
    RateLimit --> Cache
    Cache --> L7B1
    Cache --> L7B2
    Cache --> C13B
    Cache --> M7B
    
    Router -.-> Redis
    Router -.-> DB
    Cache -.-> Redis
```

---

## 2. Component Interaction Flow

```mermaid
sequenceDiagram
    participant Client
    participant LiteLLM
    participant Redis
    participant DB
    participant vLLM
    
    Client->>LiteLLM: POST /v1/chat/completions
    LiteLLM->>DB: Validate API Key
    DB-->>LiteLLM: Key Valid
    LiteLLM->>Redis: Check Rate Limits
    Redis-->>LiteLLM: Within Limits
    LiteLLM->>Redis: Get Available Instances
    Redis-->>LiteLLM: Instance List
    LiteLLM->>LiteLLM: Select Instance (Load Balance)
    LiteLLM->>vLLM: Forward Request
    vLLM->>vLLM: Process Inference
    vLLM-->>LiteLLM: Stream Response
    LiteLLM->>Redis: Update Counters
    LiteLLM->>DB: Track Cost
    LiteLLM-->>Client: Stream Response
```

---

## 3. Load Balancing Architecture

```mermaid
graph LR
    subgraph Router["LiteLLM Router"]
        LB["Load Balancer<br/>simple-shuffle"]
    end
    
    subgraph Instances["vLLM Instances"]
        I1["Instance 1<br/>Load: 45%"]
        I2["Instance 2<br/>Load: 30%"]
        I3["Instance 3<br/>Load: 25%"]
    end
    
    subgraph State["Shared State"]
        Redis["Redis<br/>Load Tracking"]
    end
    
    LB -->|Weighted Selection| I1
    LB -->|Weighted Selection| I2
    LB -->|Weighted Selection| I3
    
    LB -.->|Update State| Redis
    Redis -.->|Provide Metrics| LB
```

---

## 4. OpenShift Deployment Structure

```mermaid
graph TB
    subgraph Cluster["OpenShift Cluster"]
        subgraph NS["Namespace: llm-service"]
            subgraph LiteLLMDeploy["LiteLLM Deployment"]
                LP1["Pod 1<br/>4 CPU, 8GB"]
                LP2["Pod 2<br/>4 CPU, 8GB"]
                LP3["Pod 3<br/>4 CPU, 8GB"]
            end
            
            subgraph LiteLLMSvc["LiteLLM Service"]
                LSvc["ClusterIP<br/>Port 4000"]
            end
            
            subgraph LiteLLMRoute["LiteLLM Route"]
                LRoute["Edge TLS<br/>External Access"]
            end
            
            subgraph vLLMDeploy["vLLM Deployments"]
                V1["Llama 2 7B<br/>Pod 1 (GPU)"]
                V2["Llama 2 7B<br/>Pod 2 (GPU)"]
                V3["CodeLlama 13B<br/>Pod 1 (GPU)"]
            end
            
            subgraph Config["Configuration"]
                CM["ConfigMap<br/>config.yaml"]
                Sec["Secrets<br/>Keys/DB"]
            end
        end
        
        subgraph DBNS["Namespace: database"]
            PG["PostgreSQL"]
            RD["Redis"]
        end
    end
    
    LRoute --> LSvc
    LSvc --> LP1
    LSvc --> LP2
    LSvc --> LP3
    
    LP1 --> V1
    LP1 --> V2
    LP1 --> V3
    LP2 --> V1
    LP2 --> V2
    LP2 --> V3
    
    LP1 -.-> PG
    LP1 -.-> RD
    LP2 -.-> PG
    LP2 -.-> RD
    
    CM --> LP1
    CM --> LP2
    CM --> LP3
    Sec --> LP1
    Sec --> LP2
    Sec --> LP3
```

---

## 5. Request Flow Diagram

```mermaid
flowchart TD
    Start([Client Request]) --> Auth{Authenticate<br/>API Key}
    Auth -->|Invalid| Error1[Return 401]
    Auth -->|Valid| RateLimit{Check Rate<br/>Limits}
    RateLimit -->|Exceeded| Error2[Return 429]
    RateLimit -->|OK| FindModel{Find Model<br/>in Config}
    FindModel -->|Not Found| Error3[Return 404]
    FindModel -->|Found| GetInstances[Get Available<br/>Instances from Redis]
    GetInstances --> Select[Load Balance<br/>Select Instance]
    Select --> Forward[Forward to<br/>vLLM Backend]
    Forward --> Process[vLLM Processes<br/>Inference]
    Process --> Response[Stream Response]
    Response --> Update[Update Redis<br/>Update DB]
    Update --> Return([Return to Client])
    
    style Start fill:#90EE90
    style Return fill:#90EE90
    style Error1 fill:#FFB6C1
    style Error2 fill:#FFB6C1
    style Error3 fill:#FFB6C1
```

---

## 6. Failover and Resilience

```mermaid
graph TB
    subgraph Normal["Normal Operation"]
        R1[Router] -->|Routes to| I1[Instance 1<br/>Healthy]
    end
    
    subgraph Failure["Failure Detected"]
        R2[Router] -->|Detects| I2[Instance 1<br/>Timeout/Error]
        R2 -->|Mark Unhealthy| Redis[Update Redis]
        Redis -->|Remove from Pool| LB[Load Balancer]
    end
    
    subgraph Recovery["Automatic Recovery"]
        R3[Router] -->|Retry with| I3[Instance 2<br/>Healthy]
        R3 -->|Fallback| I4[Model Fallback<br/>llama-2-7b]
    end
    
    Normal --> Failure
    Failure --> Recovery
```

---

## 7. Caching Flow

```mermaid
sequenceDiagram
    participant Client
    participant LiteLLM
    participant Redis
    participant vLLM
    
    Client->>LiteLLM: Request
    LiteLLM->>Redis: Check Cache
    alt Cache Hit
        Redis-->>LiteLLM: Cached Response
        LiteLLM-->>Client: Return Cached
    else Cache Miss
        Redis-->>LiteLLM: Cache Miss
        LiteLLM->>vLLM: Forward Request
        vLLM-->>LiteLLM: Response
        LiteLLM->>Redis: Store in Cache
        LiteLLM-->>Client: Return Response
    end
```

---

## 8. Network Architecture

```mermaid
graph TB
    subgraph External["External"]
        Clients["Client Applications"]
    end
    
    subgraph Route["OpenShift Route"]
        TLS["Edge TLS Termination"]
    end
    
    subgraph LiteLLMNS["Namespace: llm-service"]
        subgraph LiteLLM["LiteLLM Pods"]
            LP["LiteLLM<br/>Port 4000"]
        end
        
        subgraph vLLM["vLLM Pods"]
            VP["vLLM Backend<br/>Port 8000"]
        end
    end
    
    subgraph DBNS["Namespace: database"]
        Redis["Redis<br/>Port 6379"]
        PG["PostgreSQL<br/>Port 5432"]
    end
    
    Clients -->|HTTPS| TLS
    TLS -->|HTTP| LP
    LP -->|HTTP| VP
    LP -.->|Cache/LB| Redis
    LP -.->|Keys/Spend| PG
    
    style Clients fill:#E6F3FF
    style LP fill:#90EE90
    style VP fill:#FFD700
    style Redis fill:#FF6B6B
    style PG fill:#4ECDC4
```

---

## 9. Data Flow - Complete Request Lifecycle

```mermaid
graph LR
    subgraph Step1["Step 1: Request"]
        C1[Client]
    end
    
    subgraph Step2["Step 2: Auth"]
        A1[Validate Key]
        DB1[(PostgreSQL)]
    end
    
    subgraph Step3["Step 3: Rate Limit"]
        RL1[Check Limits]
        R1[(Redis)]
    end
    
    subgraph Step4["Step 4: Route"]
        RT1[Load Balance]
        R2[(Redis)]
    end
    
    subgraph Step5["Step 5: Inference"]
        V1[vLLM Backend]
    end
    
    subgraph Step6["Step 6: Response"]
        RS1[Stream Response]
        R3[(Redis)]
        DB2[(PostgreSQL)]
    end
    
    C1 --> A1
    A1 --> DB1
    A1 --> RL1
    RL1 --> R1
    RL1 --> RT1
    RT1 --> R2
    RT1 --> V1
    V1 --> RS1
    RS1 --> R3
    RS1 --> DB2
    RS1 --> C1
```

---

## 10. Health Check Architecture

```mermaid
graph TB
    subgraph Pod["LiteLLM Pod"]
        subgraph Main["Main Application"]
            MA[FastAPI App<br/>Port 4000<br/>Handles Requests]
        end
        
        subgraph Health["Health Check App"]
            HA[Lightweight App<br/>Port 8001<br/>Always Responsive]
        end
    end
    
    subgraph K8s["Kubernetes"]
        LP[Liveness Probe<br/>/health/liveliness]
        RP[Readiness Probe<br/>/health/readiness]
    end
    
    LP --> HA
    RP --> HA
    
    style HA fill:#90EE90
    style MA fill:#FFD700
```

---

## 11. Model Routing Decision Tree

```mermaid
graph TD
    Start([Request: model='llama-2-7b']) --> Parse[Parse Model Name]
    Parse --> Check{Model in<br/>Config?}
    Check -->|No| Error1[Return 404]
    Check -->|Yes| GetInst[Get Instances<br/>from Redis]
    GetInst --> Count{Instance<br/>Count?}
    Count -->|0| Error2[Return 503]
    Count -->|1| Direct[Route to<br/>Single Instance]
    Count -->|2+| LB[Load Balance<br/>Select Instance]
    LB --> Strategy{Strategy}
    Strategy -->|simple-shuffle| Weight[Weighted Random]
    Strategy -->|least-busy| Busy[Select Least Busy]
    Strategy -->|latency| Lat[Select Lowest Latency]
    Weight --> Forward[Forward Request]
    Busy --> Forward
    Lat --> Forward
    Direct --> Forward
    Forward --> Success([Success])
    
    style Start fill:#90EE90
    style Success fill:#90EE90
    style Error1 fill:#FFB6C1
    style Error2 fill:#FFB6C1
```

---

## 12. Scaling Architecture

```mermaid
graph TB
    subgraph HPA["Horizontal Pod Autoscaler"]
        Metrics[CPU/Memory Metrics]
        Scale[Scaling Decision]
    end
    
    subgraph LiteLLM["LiteLLM Deployment"]
        P1[Pod 1]
        P2[Pod 2]
        P3[Pod 3]
        P4[Pod 4<br/>Scaled Up]
    end
    
    subgraph Load["Load Distribution"]
        LB[Service Load Balancer]
    end
    
    Metrics --> Scale
    Scale -->|Scale Up| P4
    Scale -->|Scale Down| P1
    
    P1 --> LB
    P2 --> LB
    P3 --> LB
    P4 --> LB
    
    style P4 fill:#90EE90
    style Scale fill:#FFD700
```

---

## How to View These Diagrams

### GitHub/GitLab
These Mermaid diagrams will render automatically in markdown files on GitHub and GitLab.

### VS Code
Install the "Markdown Preview Mermaid Support" extension.

### Online Viewers
- [Mermaid Live Editor](https://mermaid.live/)
- [Mermaid.ink](https://mermaid.ink/)

### Local Rendering
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Render diagram
mmdc -i diagram.mmd -o diagram.png
```

---

## Diagram Legend

- **Green boxes**: Success states, healthy components
- **Yellow boxes**: Processing, active components
- **Red boxes**: Errors, failed states
- **Blue boxes**: External components, clients
- **Dashed lines**: Optional/background connections
- **Solid lines**: Direct data flow
