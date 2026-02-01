# LiteLLM Teams & Spend Architecture - On-Premise Infrastructure

## Overview

This document explains how **Teams** and **Spend** tracking work in LiteLLM when deployed on-premise with locally hosted LLMs (vLLM). Even though you're not paying external cloud providers, LiteLLM still tracks "spend" based on **virtual costs** to enable chargeback, cost allocation, and resource governance.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Consumer Applications"
        RAG[RAG App]
        CodeSupport[Code Support Tool]
        Translate[Translation Service]
        DataPipeline[Data Pipeline]
    end
    
    subgraph "LiteLLM Central Gateway"
        Proxy[LiteLLM Proxy]
        VirtualKeys[Virtual Key Manager]
        TeamManager[Team Manager]
        SpendTracker[Spend Tracker]
        BudgetEnforcer[Budget Enforcer]
    end
    
    subgraph "vLLM Inference Engines - On-Prem"
        vLLM1[vLLM: Llama-2-7B]
        vLLM2[vLLM: CodeLlama-13B]
        vLLM3[vLLM: Mistral-7B]
        vLLM4[vLLM: Embeddings]
    end
    
    subgraph "PostgreSQL Database"
        TeamsTable[(Teams Table)]
        UsersTable[(Users Table)]
        KeysTable[(Virtual Keys Table)]
        SpendLogs[(Spend Logs Table)]
    end
    
    subgraph "Redis Cache"
        RateLimitCounters[Rate Limit Counters]
        BudgetCache[Budget Cache]
        SpendBuffer[Spend Buffer]
    end
    
    RAG -->|API Key: rag-key-001| Proxy
    CodeSupport -->|API Key: code-key-001| Proxy
    Translate -->|API Key: trans-key-001| Proxy
    DataPipeline -->|API Key: pipeline-key-001| Proxy
    
    Proxy --> VirtualKeys
    VirtualKeys --> TeamManager
    Proxy --> SpendTracker
    SpendTracker --> BudgetEnforcer
    
    Proxy --> vLLM1
    Proxy --> vLLM2
    Proxy --> vLLM3
    Proxy --> vLLM4
    
    TeamManager --> TeamsTable
    VirtualKeys --> KeysTable
    SpendTracker --> SpendLogs
    BudgetEnforcer --> TeamsTable
    BudgetEnforcer --> KeysTable
    
    SpendTracker --> SpendBuffer
    BudgetEnforcer --> BudgetCache
    VirtualKeys --> RateLimitCounters
```

---

## Core Concepts: Teams & Spend in On-Prem Context

### What is a "Team"?

A **Team** is an organizational unit that groups:
- **Multiple users** (engineers, data scientists, applications)
- **Multiple virtual API keys** (one per app or service)
- **Shared budget limits** (monthly/weekly/daily caps)
- **Shared rate limits** (RPM/TPM across all team keys)
- **Model access permissions** (which LLMs this team can use)

**On-Prem Context:**
- Teams represent **business units**, **departments**, or **projects**
- Examples: "Data Science Team", "Product Engineering", "Customer Support Tools"

---

### What is "Spend"?

**Spend** is the **virtual cost** of LLM usage, even though you're not paying external providers.

**Why track spend on-prem?**
1. **Chargeback/Showback**: Allocate internal infrastructure costs to departments
2. **Resource Governance**: Prevent any single team from monopolizing GPU resources
3. **Usage Analytics**: Understand which teams/apps consume the most resources
4. **Capacity Planning**: Forecast GPU needs based on usage trends
5. **Fair Sharing**: Enforce quotas so all teams get fair access

**How is spend calculated on-prem?**
- You define **virtual pricing** in `litellm_settings` in config.yaml
- LiteLLM calculates cost = `(input_tokens × input_price) + (output_tokens × output_price)`
- This "cost" is tracked per key, per user, per team, and logged in PostgreSQL

---

## Detailed Architecture: Request Flow with Team & Spend Tracking

```mermaid
sequenceDiagram
    participant App as Consumer App<br/>(e.g., RAG)
    participant Proxy as LiteLLM Proxy
    participant Redis as Redis
    participant Auth as Virtual Key Manager
    participant Team as Team Manager
    participant Budget as Budget Enforcer
    participant vLLM as vLLM Backend
    participant PG as PostgreSQL
    
    App->>Proxy: POST /chat/completions<br/>Header: Authorization: Bearer rag-key-001
    
    Proxy->>Auth: Validate key: rag-key-001
    Auth->>Redis: Check key in cache
    Redis-->>Auth: Key not in cache
    Auth->>PG: SELECT * FROM LiteLLM_VerificationToken WHERE token='rag-key-001'
    PG-->>Auth: Key valid, team_id=team-abc, user_id=user-123
    Auth->>Redis: Cache key metadata (5 min TTL)
    Auth-->>Proxy: Key valid
    
    Proxy->>Team: Get team info for team-abc
    Team->>Redis: Check team budget cache
    Redis-->>Team: Team budget: $1000/month, spent: $450
    Team-->>Proxy: Team OK, budget available
    
    Proxy->>Budget: Check budget limits
    Budget->>Redis: Get current spend for key + team
    Redis-->>Budget: Key spent: $120, Team spent: $450
    Budget-->>Proxy: Within limits, proceed
    
    Proxy->>Redis: Check rate limits (RPM/TPM)
    Redis-->>Proxy: Within limits
    
    Proxy->>vLLM: Forward request to Llama-2-7B
    vLLM-->>Proxy: Response (tokens: 50 in, 200 out)
    
    Proxy->>Budget: Calculate spend<br/>Cost = (50×$0.01) + (200×$0.02) = $4.50
    Budget->>Redis: Increment spend counters<br/>- rag-key-001: +$4.50<br/>- team-abc: +$4.50<br/>- user-123: +$4.50
    
    Budget->>Redis: Add to transaction buffer
    Redis->>PG: Async batch write<br/>INSERT INTO LiteLLM_SpendLogs
    
    Proxy-->>App: Return LLM response
    
    Note over Redis,PG: Budget checks happen in Redis (fast)<br/>Detailed logs written to PostgreSQL (batched)
```

---

## Database Schema: Teams & Spend Tables

### 1. LiteLLM_TeamTable

Stores team definitions, budgets, and aggregated spend.

```sql
CREATE TABLE "LiteLLM_TeamTable" (
    team_id VARCHAR(256) PRIMARY KEY,           -- e.g., "team-data-science"
    team_alias VARCHAR(256),                     -- Human-readable name: "Data Science Team"
    admins TEXT[],                               -- List of admin user IDs
    members TEXT[],                              -- List of member user IDs
    members_with_roles JSONB,                    -- Detailed role assignments
    
    -- Budget settings
    max_budget DECIMAL(10,2),                    -- e.g., 1000.00 (virtual dollars)
    budget_duration VARCHAR(50),                 -- "monthly", "weekly", "daily"
    budget_reset_at TIMESTAMP,                   -- Next reset time
    
    -- Spend tracking
    spend DECIMAL(10,2) DEFAULT 0.00,            -- Current period spend
    
    -- Rate limits
    tpm_limit BIGINT,                            -- Tokens per minute (team-wide)
    rpm_limit BIGINT,                            -- Requests per minute (team-wide)
    
    -- Model access control
    models TEXT[],                               -- Allowed models: ["llama-2-7b", "codellama-13b"]
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB                               -- Additional custom fields
);
```

**Example Row:**
```json
{
  "team_id": "team-data-science",
  "team_alias": "Data Science Team",
  "admins": ["user-admin-001"],
  "members": ["user-001", "user-002", "user-003"],
  "max_budget": 1000.00,
  "budget_duration": "monthly",
  "budget_reset_at": "2026-02-01T00:00:00Z",
  "spend": 450.75,
  "tpm_limit": 100000,
  "rpm_limit": 1000,
  "models": ["llama-2-7b", "codellama-13b", "mistral-7b"]
}
```

---

### 2. LiteLLM_VerificationToken (Virtual Keys)

Stores API keys with team/user associations and per-key budgets.

```sql
CREATE TABLE "LiteLLM_VerificationToken" (
    token VARCHAR(256) PRIMARY KEY,              -- e.g., "rag-key-001"
    key_name VARCHAR(256),                       -- Human-readable: "RAG App Production Key"
    key_alias VARCHAR(256),                      -- Alternative name
    
    -- Ownership
    team_id VARCHAR(256),                        -- FK to LiteLLM_TeamTable
    user_id VARCHAR(256),                        -- FK to LiteLLM_UserTable
    
    -- Budget (per-key limits)
    max_budget DECIMAL(10,2),                    -- e.g., 500.00
    budget_duration VARCHAR(50),                 -- "monthly", "weekly", "daily"
    budget_reset_at TIMESTAMP,
    spend DECIMAL(10,2) DEFAULT 0.00,            -- Current period spend for this key
    
    -- Rate limits (per-key)
    tpm_limit BIGINT,
    rpm_limit BIGINT,
    
    -- Model access (can be more restrictive than team)
    models TEXT[],
    
    -- Expiration
    expires_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);
```

**Example Row:**
```json
{
  "token": "rag-key-001",
  "key_name": "RAG App Production Key",
  "team_id": "team-data-science",
  "user_id": "user-001",
  "max_budget": 500.00,
  "budget_duration": "monthly",
  "budget_reset_at": "2026-02-01T00:00:00Z",
  "spend": 120.50,
  "tpm_limit": 50000,
  "rpm_limit": 500,
  "models": ["llama-2-7b", "mistral-7b"],
  "expires_at": "2026-12-31T23:59:59Z"
}
```

---

### 3. LiteLLM_SpendLogs

Detailed per-request spend logs (for auditing and analytics).

```sql
CREATE TABLE "LiteLLM_SpendLogs" (
    request_id VARCHAR(256) PRIMARY KEY,         -- Unique request ID
    
    -- Request details
    api_key VARCHAR(256),                        -- Which key made the request
    team_id VARCHAR(256),
    user_id VARCHAR(256),
    model VARCHAR(256),                          -- Which model was used
    
    -- Token usage
    prompt_tokens INTEGER,                       -- Input tokens
    completion_tokens INTEGER,                   -- Output tokens
    total_tokens INTEGER,
    
    -- Cost calculation
    prompt_tokens_cost DECIMAL(10,6),            -- Cost for input
    completion_tokens_cost DECIMAL(10,6),        -- Cost for output
    total_cost DECIMAL(10,6),                    -- Total request cost
    
    -- Pricing used (for auditing)
    input_cost_per_token DECIMAL(12,10),         -- Price per input token
    output_cost_per_token DECIMAL(12,10),        -- Price per output token
    
    -- Timing
    startTime TIMESTAMP,
    endTime TIMESTAMP,
    
    -- Additional metadata
    call_type VARCHAR(50),                       -- "completion", "embedding", etc.
    cache_hit BOOLEAN DEFAULT FALSE,             -- Was this a cache hit?
    cache_key VARCHAR(256),
    request_tags TEXT[],                         -- Custom tags for grouping
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example Row:**
```json
{
  "request_id": "req-abc123",
  "api_key": "rag-key-001",
  "team_id": "team-data-science",
  "user_id": "user-001",
  "model": "llama-2-7b",
  "prompt_tokens": 50,
  "completion_tokens": 200,
  "total_tokens": 250,
  "prompt_tokens_cost": 0.0005,
  "completion_tokens_cost": 0.0040,
  "total_cost": 0.0045,
  "input_cost_per_token": 0.00001,
  "output_cost_per_token": 0.00002,
  "startTime": "2026-01-29T10:15:30Z",
  "endTime": "2026-01-29T10:15:32Z",
  "call_type": "completion",
  "cache_hit": false
}
```

---

## Budget Enforcement Flow

```mermaid
flowchart TD
    Start[Request arrives with API key] --> ValidateKey{Is key valid?}
    ValidateKey -->|No| Reject1[Return 401 Unauthorized]
    ValidateKey -->|Yes| CheckKeyBudget{Key budget<br/>exceeded?}
    
    CheckKeyBudget -->|Yes| Reject2[Return 429<br/>Key budget exceeded]
    CheckKeyBudget -->|No| CheckTeamBudget{Team budget<br/>exceeded?}
    
    CheckTeamBudget -->|Yes| Reject3[Return 429<br/>Team budget exceeded]
    CheckTeamBudget -->|No| CheckRateLimits{Rate limits<br/>exceeded?}
    
    CheckRateLimits -->|Yes| Reject4[Return 429<br/>Rate limit exceeded]
    CheckRateLimits -->|No| CheckModelAccess{Model allowed<br/>for team?}
    
    CheckModelAccess -->|No| Reject5[Return 403<br/>Model not allowed]
    CheckModelAccess -->|Yes| Forward[Forward to vLLM]
    
    Forward --> ProcessRequest[vLLM processes request]
    ProcessRequest --> CalcCost[Calculate cost:<br/>tokens × price]
    
    CalcCost --> UpdateRedis[Update spend in Redis:<br/>- Key spend<br/>- Team spend<br/>- User spend]
    
    UpdateRedis --> BufferLog[Add to transaction buffer]
    BufferLog --> AsyncWrite[Async batch write to PostgreSQL]
    
    AsyncWrite --> Return[Return response to client]
```

---

## On-Premise Budget Configuration

### Setting Virtual Pricing in config.yaml

Since you're on-prem, you define **virtual costs** that reflect your internal accounting model.

```yaml
litellm_settings:
  # Define virtual pricing for internal cost allocation
  model_cost_map:
    llama-2-7b:
      input_cost_per_token: 0.00001    # $0.01 per 1000 input tokens
      output_cost_per_token: 0.00002   # $0.02 per 1000 output tokens
      max_tokens: 4096
    
    codellama-13b:
      input_cost_per_token: 0.00002    # Larger model = higher virtual cost
      output_cost_per_token: 0.00004
      max_tokens: 4096
    
    mistral-7b:
      input_cost_per_token: 0.00001
      output_cost_per_token: 0.00002
      max_tokens: 8192
    
    embeddings-model:
      input_cost_per_token: 0.000001   # Embeddings are cheaper
      output_cost_per_token: 0.0
      max_tokens: 512

# Alternative: Use cost per request instead of per token
# This is simpler but less accurate
general_settings:
  use_request_based_cost: false        # Set to true for flat per-request pricing
  request_cost: 0.01                   # $0.01 per request (if enabled)
```

### How to Decide Virtual Pricing

**Method 1: GPU Hour Allocation**
```
GPU Cost: $2/hour for A100
Expected throughput: 1000 requests/hour at 250 tokens avg
Cost per request: $2 / 1000 = $0.002
Cost per token: $0.002 / 250 = $0.000008
```

**Method 2: Total Infrastructure Cost Allocation**
```
Monthly GPU costs: $10,000
Expected monthly tokens: 1 billion
Cost per token: $10,000 / 1,000,000,000 = $0.00001
```

**Method 3: Fair Share Units (no real dollars)**
```
Just use arbitrary units: 1 token = 1 credit
Monthly allocation: 100,000 credits per team
This ensures fair distribution without dollar values
```

---

## Team & Budget Setup: Complete Example

### Step 1: Create Teams via API

```bash
# Create Data Science Team
curl -X POST http://litellm.company.local/team/new \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "team-data-science",
    "team_alias": "Data Science Team",
    "admins": ["admin@company.com"],
    "members": ["datascientist1@company.com", "datascientist2@company.com"],
    "max_budget": 1000.00,
    "budget_duration": "monthly",
    "tpm_limit": 100000,
    "rpm_limit": 1000,
    "models": ["llama-2-7b", "codellama-13b", "mistral-7b"]
  }'

# Create Product Engineering Team
curl -X POST http://litellm.company.local/team/new \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "team-product-eng",
    "team_alias": "Product Engineering",
    "admins": ["eng-lead@company.com"],
    "members": ["engineer1@company.com", "engineer2@company.com"],
    "max_budget": 1500.00,
    "budget_duration": "monthly",
    "tpm_limit": 150000,
    "rpm_limit": 1500,
    "models": ["llama-2-7b", "codellama-13b"]
  }'
```

### Step 2: Generate Virtual Keys for Applications

```bash
# Key for RAG application (Data Science team)
curl -X POST http://litellm.company.local/key/generate \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "RAG App Production Key",
    "team_id": "team-data-science",
    "user_id": "user-rag-app",
    "max_budget": 500.00,
    "budget_duration": "monthly",
    "tpm_limit": 50000,
    "rpm_limit": 500,
    "models": ["llama-2-7b", "mistral-7b"]
  }'

# Response:
# {
#   "key": "sk-litellm-abc123xyz789...",
#   "key_name": "RAG App Production Key",
#   "team_id": "team-data-science",
#   "expires": null
# }

# Key for Code Support tool (Product Engineering team)
curl -X POST http://litellm.company.local/key/generate \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "Code Support Production Key",
    "team_id": "team-product-eng",
    "user_id": "user-code-support",
    "max_budget": 800.00,
    "budget_duration": "monthly",
    "tpm_limit": 80000,
    "rpm_limit": 800,
    "models": ["codellama-13b"]
  }'
```

### Step 3: Monitor Spend

```bash
# Get team spend
curl http://litellm.company.local/team/info?team_id=team-data-science \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"

# Response:
# {
#   "team_id": "team-data-science",
#   "spend": 450.75,
#   "max_budget": 1000.00,
#   "budget_remaining": 549.25,
#   "budget_reset_at": "2026-02-01T00:00:00Z"
# }

# Get per-key spend
curl http://litellm.company.local/key/info?key=sk-litellm-abc123xyz789... \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"

# Get detailed spend logs
curl http://litellm.company.local/spend/logs?team_id=team-data-science&start_date=2026-01-01 \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

---

## Redis Role in Budget Enforcement

### Why Redis is Critical for Budget Checks

```mermaid
graph LR
    Request[Incoming Request] --> Redis{Redis Check<br/>1-2ms}
    Redis -->|Budget OK| Forward[Forward to vLLM]
    Redis -->|Budget exceeded| Reject[Reject 429]
    
    Forward --> Response[Get Response]
    Response --> UpdateRedis[Update Redis Counters<br/>1-2ms]
    UpdateRedis --> Buffer[Add to Buffer]
    Buffer --> PostgreSQL[(PostgreSQL<br/>Async Batch Write<br/>10-50ms)]
    
    PostgreSQL -.->|Hourly sync| Redis
    
    style Redis fill:#ff9999
    style PostgreSQL fill:#99ccff
```

**Redis stores:**
1. **Current spend counters** (per key, per team, per user) - fast increment
2. **Budget limits** - cached from PostgreSQL (5-10 min TTL)
3. **Rate limit sliding windows** (RPM/TPM)
4. **Transaction buffer** - queued spend logs before PostgreSQL write

**PostgreSQL stores:**
1. **Team/User/Key definitions** (source of truth)
2. **Detailed spend logs** (every request, for auditing)
3. **Historical spend data** (for analytics)

**Why this split?**
- **Redis**: sub-millisecond reads/writes, can handle 10,000+ RPS
- **PostgreSQL**: durable, ACID, but 10-50ms per write
- **Trade-off**: Accept eventual consistency (Redis → PostgreSQL) for performance

---

## Budget Reset Mechanism

```mermaid
sequenceDiagram
    participant Cron as Scheduled Job<br/>(every hour)
    participant PG as PostgreSQL
    participant Redis as Redis
    
    loop Every Hour
        Cron->>PG: SELECT * FROM LiteLLM_TeamTable<br/>WHERE budget_reset_at < NOW()
        PG-->>Cron: Teams needing reset: [team-abc, team-xyz]
        
        loop For each team
            Cron->>PG: UPDATE LiteLLM_TeamTable<br/>SET spend = 0,<br/>budget_reset_at = NOW() + budget_duration<br/>WHERE team_id = 'team-abc'
            
            Cron->>PG: SELECT * FROM LiteLLM_VerificationToken<br/>WHERE team_id = 'team-abc'
            PG-->>Cron: Keys: [key-001, key-002]
            
            loop For each key
                Cron->>PG: UPDATE LiteLLM_VerificationToken<br/>SET spend = 0<br/>WHERE token = 'key-001'
            end
        end
        
        Cron->>Redis: DEL budget:cache:team-abc
        Cron->>Redis: DEL spend:team-abc
        Cron->>Redis: DEL spend:key-001
        
        Note over Cron,Redis: Next request will reload<br/>fresh budget from PostgreSQL
    end
```

---

## Organizational Structure Example

```
Company Infrastructure
├── Team: Data Science (team-data-science)
│   ├── Budget: $1000/month
│   ├── Members: [datascientist1, datascientist2]
│   ├── Models: [llama-2-7b, codellama-13b, mistral-7b]
│   └── Keys:
│       ├── rag-key-001 (RAG App) - $500/month
│       ├── pipeline-key-001 (Data Pipeline) - $300/month
│       └── notebook-key-001 (Jupyter Notebooks) - $200/month
│
├── Team: Product Engineering (team-product-eng)
│   ├── Budget: $1500/month
│   ├── Members: [engineer1, engineer2, engineer3]
│   ├── Models: [llama-2-7b, codellama-13b]
│   └── Keys:
│       ├── code-key-001 (Code Support) - $800/month
│       ├── api-key-001 (Product API) - $500/month
│       └── test-key-001 (Testing) - $200/month
│
└── Team: Customer Support (team-customer-support)
    ├── Budget: $500/month
    ├── Members: [support1, support2]
    ├── Models: [llama-2-7b, mistral-7b]
    └── Keys:
        ├── chatbot-key-001 (Support Chatbot) - $300/month
        └── translate-key-001 (Translation) - $200/month
```

---

## Chargeback/Showback Report Example

At the end of each month, you can generate reports from PostgreSQL:

```sql
-- Monthly spend by team
SELECT 
    team_id,
    SUM(total_cost) as total_spend,
    COUNT(*) as total_requests,
    SUM(total_tokens) as total_tokens,
    AVG(total_cost) as avg_cost_per_request
FROM "LiteLLM_SpendLogs"
WHERE startTime >= '2026-01-01' AND startTime < '2026-02-01'
GROUP BY team_id
ORDER BY total_spend DESC;

-- Results:
-- team_id              | total_spend | total_requests | total_tokens | avg_cost_per_request
-- team-product-eng     | 1245.50     | 125000         | 31250000     | 0.00996
-- team-data-science    | 987.25      | 98500          | 24625000     | 0.01002
-- team-customer-support| 423.10      | 42000          | 10500000     | 0.01007

-- Spend by application (via API key)
SELECT 
    k.key_name,
    k.team_id,
    SUM(s.total_cost) as total_spend,
    COUNT(*) as total_requests
FROM "LiteLLM_SpendLogs" s
JOIN "LiteLLM_VerificationToken" k ON s.api_key = k.token
WHERE s.startTime >= '2026-01-01' AND s.startTime < '2026-02-01'
GROUP BY k.key_name, k.team_id
ORDER BY total_spend DESC;

-- Spend by model (which models are most used?)
SELECT 
    model,
    SUM(total_cost) as total_spend,
    COUNT(*) as total_requests,
    AVG(prompt_tokens) as avg_prompt_tokens,
    AVG(completion_tokens) as avg_completion_tokens
FROM "LiteLLM_SpendLogs"
WHERE startTime >= '2026-01-01' AND startTime < '2026-02-01'
GROUP BY model
ORDER BY total_spend DESC;
```

---

## Key Takeaways for On-Premise

1. **Teams = Organizational Units**
   - Group users, keys, and budgets by department/project
   - Enforce fair resource sharing across teams

2. **Spend = Virtual Costs, Not Real Money**
   - You define pricing based on internal accounting
   - Could be GPU hours, arbitrary credits, or estimated cloud-equivalent costs

3. **Budget Enforcement = Resource Governance**
   - Prevents any single team from monopolizing GPUs
   - Enables chargeback to departments
   - Forces teams to optimize their usage

4. **Redis is Essential for Performance**
   - Budget checks must be fast (<5ms)
   - PostgreSQL is too slow for per-request checks
   - Redis → PostgreSQL pipeline handles high RPS

5. **PostgreSQL is Source of Truth**
   - All team/user/key definitions
   - Complete audit trail of every request
   - Historical analytics and reporting

6. **Benefits for On-Prem**
   - **Visibility**: Who is using what models, how much
   - **Fairness**: No team can exhaust shared resources
   - **Planning**: Data-driven decisions on GPU capacity
   - **Accountability**: Departments know their consumption

---

## Configuration Summary

### Environment Variables

```bash
# PostgreSQL (source of truth)
DATABASE_URL="postgresql://litellm:password@postgres.llm-data.svc.cluster.local:5432/litellm"

# Redis (fast budget checks)
REDIS_HOST="redis.llm-data.svc.cluster.local"
REDIS_PORT="6379"
REDIS_PASSWORD="your-redis-password"

# LiteLLM admin credentials
LITELLM_MASTER_KEY="sk-master-very-secret-key"

# Important: Enable transaction buffer for high RPS
LITELLM_USE_REDIS_TRANSACTION_BUFFER="true"
```

### config.yaml

```yaml
model_list:
  - model_name: llama-2-7b
    litellm_params:
      model: openai/llama-2-7b
      api_base: http://vllm-llama-2-7b.llm-service.svc.cluster.local:8000/v1
      api_key: dummy-key
    rpm: 1000
    tpm: 100000

litellm_settings:
  # Virtual pricing for on-prem cost allocation
  model_cost_map:
    llama-2-7b:
      input_cost_per_token: 0.00001
      output_cost_per_token: 0.00002
      max_tokens: 4096

router_settings:
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
  routing_strategy: least-busy

general_settings:
  use_redis_transaction_buffer: true
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
```

---

## Next Steps

1. **Define Your Internal Pricing Model**
   - Decide: GPU hours? Flat credits? Cloud-equivalent?
   - Document this in your internal wiki

2. **Map Your Organization to Teams**
   - Create teams for each department/project
   - Assign appropriate budgets based on expected usage

3. **Generate Keys for Each Application**
   - One key per app/service
   - Set per-key budgets (subset of team budget)

4. **Set Up Monitoring**
   - Grafana dashboards for spend trends
   - Alerts when teams approach budget limits
   - Weekly/monthly reports

5. **Iterate on Budgets**
   - Start conservative, adjust based on actual usage
   - Review monthly and reallocate as needed

---

## References

- [Main deep-dive on Teams & Spend](./litellm-postgres-teams-and-spend.md)
- [Data layer technical challenges](./litellm-data-layer-technical-challenges.md)
- [Production configuration guide](./litellm-production-configuration-guide.md)
- [Project architecture overview](./projects/01-architecture-overview.md)
