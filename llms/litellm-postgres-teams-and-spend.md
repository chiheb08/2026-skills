# LiteLLM + PostgreSQL: Teams and Spend — Definitions and Details

This document defines **Teams** and **Spend** in the context of LiteLLM’s PostgreSQL data layer: what they are, how they are stored, and how they are used.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Teams — Definition and Details](#2-teams--definition-and-details)
3. [Spend — Definition and Details](#3-spend--definition-and-details)
4. [How Teams and Spend Relate](#4-how-teams-and-spend-relate)
5. [Database Tables Involved](#5-database-tables-involved)
6. [API Endpoints and Usage](#6-api-endpoints-and-usage)
7. [References](#7-references)

---

## 1. Overview

When LiteLLM is run with a **PostgreSQL database** (via `DATABASE_URL`), it uses the DB to store:

- **Virtual keys** (API keys issued by the proxy)
- **Users** (internal users who own keys or belong to teams)
- **Teams** (groups of users with shared budgets and settings)
- **Spend** (cost attributed to keys, users, and teams)

**Teams** and **Spend** are two core concepts for **access control** and **cost tracking** in a multi-tenant or multi-team setup. This document defines them and describes how they are stored and used.

---

## 2. Teams — Definition and Details

### 2.1 What is a Team?

A **Team** in LiteLLM is an **organizational unit** that:

- Groups one or more **users** (via team membership).
- Can have **API keys** (virtual keys) associated with it; keys created with a `team_id` belong to that team.
- Has **team-level settings**: budgets, rate limits, model access, and metadata.
- Is used to **track and cap spend** at the team level (e.g. “QA Prod Bot” has a $100/month budget).

In short: a **Team** is a named group (e.g. “QA Prod Bot”, “RAG Team”, “Code Support”) for which you can set **budgets**, **rate limits**, and **model access**, and to which **spend** is aggregated.

### 2.2 How Teams Are Created and Stored

- **Creation:** Via the API `POST /team/new` (or the LiteLLM UI). You provide at least a **team alias** (display name); you can also set `max_budget`, `budget_duration`, and metadata.
- **Storage:** Teams are stored in the **`LiteLLM_TeamTable`** in PostgreSQL. Each row has:
  - **team_id** (unique identifier, e.g. UUID)
  - **team_alias** (human-readable name)
  - **max_budget** (optional; dollar cap for the team)
  - **budget_duration** (optional; e.g. `"1d"`, `"30d"` — how often the budget resets)
  - **budget_reset_at** (when the current budget window resets)
  - **spend** (current spend in the current window; updated as requests are made with keys belonging to this team)
  - Other fields (metadata, rate limits, model access, etc., depending on schema).

### 2.3 Team Membership and Keys

- **Team membership:** The **`LiteLLM_TeamMembership`** table links **users** to **teams** (and can store per-membership roles or budgets).
- **Keys and teams:** When you create a key with **`team_id`** (e.g. via `POST /key/generate` with `"team_id": "<team_id>"`), that key is **associated with the team**. All usage of that key is counted toward the **team’s spend** and is subject to the **team’s budget** (if set).

So: **Team** = entity in `LiteLLM_TeamTable`; **spend** for any key with that `team_id` is aggregated into the team’s `spend` and checked against the team’s `max_budget`.

### 2.4 Team Budgets

- **max_budget:** Maximum amount (in dollars) the team is allowed to spend in one budget window.
- **budget_duration:** Length of the budget window. Examples:
  - `"1s"` — reset every second
  - `"1m"` — every minute
  - `"1h"` — every hour
  - `"1d"` — daily
  - `"30d"` — monthly
- When **team spend** (aggregated from all keys with that `team_id`) reaches **max_budget**, further requests using those keys can be **rejected** with a budget-exceeded error until the next reset.

Teams are therefore the main way to **cap cost per group** (e.g. per department or per app) when using LiteLLM with PostgreSQL.

---

## 3. Spend — Definition and Details

### 3.1 What is Spend?

**Spend** in LiteLLM is the **monetary cost** (in dollars, or equivalent) attributed to **LLM usage**:

- Per **request**: each call to `/chat/completions`, `/embeddings`, etc., has an associated cost based on model and token usage.
- **Aggregated** at three levels: **per key**, **per user**, and **per team**.

So **Spend** = “how much money this key / user / team has consumed” according to LiteLLM’s cost model.

### 3.2 How Spend Is Calculated

- LiteLLM uses a **model cost map** (e.g. from `model_prices_and_context_window.json`) that defines **price per token** (or per request) for each model.
- After each request, LiteLLM computes **cost** from:
  - **Model** used
  - **Prompt tokens** and **completion tokens** (and any other factors in the cost formula)
- This **per-request cost** is:
  - **Attributed** to the **virtual key** used for the request.
  - If the key has a **user_id**, the cost is also added to that **user’s spend** (in `LiteLLM_UserTable`).
  - If the key has a **team_id**, the cost is also added to that **team’s spend** (in `LiteLLM_TeamTable`).

So **spend** is **stored and updated** in PostgreSQL at the key, user, and team level; it is **calculated** using token counts and model prices.

### 3.3 Where Spend Is Stored

- **Per key:** In **`LiteLLM_VerificationToken`** — each virtual key row has a **spend** field (and optionally **model_spend** for per-model breakdown).
- **Per user:** In **`LiteLLM_UserTable`** — each user row has a **spend** field; it is the sum of spend from all keys that have that **user_id**.
- **Per team:** In **`LiteLLM_TeamTable`** — each team row has a **spend** field; it is the sum of spend from all keys that have that **team_id**.

Spend is **updated** as requests complete (either written directly to PostgreSQL or buffered in Redis and flushed in batch when the **transaction buffer** is enabled).

### 3.4 Spend Logs (Detailed Records)

- **`LiteLLM_SpendLogs`** stores **per-request** usage and cost: model, tokens (prompt/completion/total), cost (spend), key (hashed), user, team, end_user, tags, etc.
- These logs are used for **reporting**, **audit**, and **detailed breakdowns** (e.g. spend by model, by day). They can be disabled with **`disable_spend_logs: True`** in `general_settings` if you do not need them in the DB (cost/usage can still be sent to other systems, e.g. Prometheus, Langfuse).

So: **Spend** as a **number** = aggregated cost in key/user/team tables; **Spend logs** = line-by-line records of each request’s cost and usage.

---

## 4. How Teams and Spend Relate

- A **Team** has a **spend** field in `LiteLLM_TeamTable` that holds the **total cost** of all usage from keys that belong to that team.
- When a request is made with a key that has **team_id** set:
  1. The request’s cost is computed (from model + tokens).
  2. The key’s **spend** is updated (in `LiteLLM_VerificationToken`).
  3. The **team’s spend** is updated (in `LiteLLM_TeamTable`).
  4. If the key has **user_id**, the **user’s spend** is also updated (in `LiteLLM_UserTable`).
- **Budget enforcement:** Before (or after) the request, LiteLLM checks whether the **team’s spend** (and/or the **key’s** or **user’s** spend) has reached the configured **max_budget**. If so, the request can be **rejected** with a budget-exceeded error.

So: **Teams** define **who** (which group) is allowed to spend **how much**; **Spend** is the **actual cost** attributed to keys, users, and teams, and is used to enforce those limits.

---

## 5. Database Tables Involved

| Table | Purpose |
|-------|---------|
| **LiteLLM_TeamTable** | Teams: team_id, team_alias, max_budget, budget_duration, spend, metadata, etc. |
| **LiteLLM_TeamMembership** | Links users to teams; can store per-membership roles/budgets. |
| **LiteLLM_UserTable** | Users: user_id, spend, model access, rate limits, etc. |
| **LiteLLM_VerificationToken** | Virtual keys: token, team_id, user_id, spend, max_budget, models, etc. |
| **LiteLLM_SpendLogs** | Per-request logs: model, tokens, spend, key (hashed), user, team, end_user, tags. |
| **LiteLLM_BudgetTable** | Budget/rate-limit configurations (e.g. for orgs, keys, end users). |

For **migrations**, the tables that must be copied to avoid losing teams and spend semantics are: **LiteLLM_VerificationToken**, **LiteLLM_UserTable**, **LiteLLM_TeamTable**, **LiteLLM_TeamMembership**, **LiteLLM_BudgetTable**. **LiteLLM_SpendLogs** is optional if you only need aggregated spend in the key/user/team rows.

---

## 6. API Endpoints and Usage

### 6.1 Teams

- **Create team:** `POST /team/new` — body: `team_alias`, optional `max_budget`, `budget_duration`, metadata. Returns `team_id`, `team_alias`, `max_budget`, `budget_duration`, `budget_reset_at`.
- **Team info (including spend):** `GET /team/info?team_id=<id>` — returns team details and **spend** for that team.
- **Update team:** Use the appropriate update endpoint (e.g. update budget or duration).

### 6.2 Spend

- **Spend per key:** `GET /key/info?key=<key>` — returns key details including **spend** (and optionally model_spend).
- **Spend per user:** `GET /user/info?user_id=<id>` — returns user details and **spend** (and keys belonging to that user).
- **Spend per team:** `GET /team/info?team_id=<id>` — returns team details and **spend**.
- **Spend logs (per-request):** `GET /spend/logs?...` — optional query params (e.g. start_date, end_date, summarize) to get detailed or aggregated logs.
- **Global spend report:** `GET /global/spend/report?...` — e.g. by team (`group_by=team`), by customer, by API key, or by internal user; used for reporting and dashboards.
- **Reset spend (master key only):** `POST /global/spend/reset` — sets spend to 0 for all keys and teams in the relevant tables; **LiteLLM_SpendLogs** is kept for audit.

### 6.3 Typical Flow

1. Create a **team** with `POST /team/new` (e.g. `team_alias: "RAG Team"`, `max_budget: 100`, `budget_duration: "30d"`).
2. Create a **key** for that team: `POST /key/generate` with `team_id: "<team_id>"`.
3. Applications use that key for LLM requests. Each request’s cost is added to the **key’s spend** and the **team’s spend**.
4. When **team spend** reaches **max_budget**, further requests with that team’s keys are rejected (budget exceeded).
5. Query **team spend** with `GET /team/info?team_id=<id>` or use **/global/spend/report** for reporting.

---

## 7. References

- LiteLLM: [Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- LiteLLM: [Spend Tracking / Cost Tracking](https://docs.litellm.ai/docs/proxy/cost_tracking)
- LiteLLM: [What is stored in the DB](https://docs.litellm.ai/docs/proxy/db_info)
- LiteLLM: [Setting Team Budgets](https://docs.litellm.ai/docs/proxy/team_budgets)
- Repo: [LiteLLM Data Layer Technical Challenges](./litellm-data-layer-technical-challenges.md)
- Repo: [LiteLLM Production Configuration Guide](./litellm-production-configuration-guide.md)

---

## Summary

- **Team:** An organizational group in PostgreSQL (`LiteLLM_TeamTable`) with an optional budget and rate limits; keys can be associated with a team via `team_id`; team **spend** is the sum of cost from all those keys.
- **Spend:** The **cost** (in dollars) of LLM usage, computed per request from model and token usage, and **aggregated** per key, per user, and per team in PostgreSQL; also recorded in **LiteLLM_SpendLogs** for detailed reporting. Spend is used to enforce **max_budget** at key, user, and team level.

Together, **Teams** and **Spend** in PostgreSQL give you **group-based access control** and **cost caps** for LiteLLM.
