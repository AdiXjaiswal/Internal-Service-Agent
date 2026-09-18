# Internal Service Agent - AI-Powered IT Support

An autonomous IT Support agent combining LangGraph orchestration, NVIDIA Nemotron language models, deterministic policy enforcement, and SQLite persistence to process employee requests, enforce company policy, and generate structured audit trails - with a full Streamlit reviewer interface.

---

## Table of Contents

1. [Overview](#overview)
2. [What the Agent Does](#what-the-agent-does)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Quick Start](#quick-start)
6. [Project Structure](#project-structure)
7. [Knowledge Base and Policies](#knowledge-base-and-policies)
8. [Example Flows](#example-flows)
9. [Streamlit UI](#streamlit-ui)
10. [Running Tests](#running-tests)
11. [Environment Configuration](#environment-configuration)
12. [Design Principles](#design-principles)

---

## Overview

The **Internal Service Agent** is an LLM-powered IT helpdesk automation system built for the Veridian Corporation prototype. It processes employee IT requests end-to-end:

- Classifies the request (password, VPN, software, security, etc.)
- Retrieves relevant company knowledge base policies
- Enforces deterministic policy rules (zero hallucination on security and compliance paths)
- Generates grounded, human-readable responses citing specific KB articles
- Creates structured tickets and compliance audit records in SQLite
- Exposes a full-featured Streamlit reviewer dashboard

---

## What the Agent Does

| Capability | Implementation |
|---|---|
| Free-text IT request intake | AgentRequest Pydantic model |
| Issue classification + entity extraction | NVIDIA Nemotron LLM + heuristic fallback |
| Knowledge Base retrieval (BM25 + FAISS) | KBRetriever, UnifiedRetriever |
| Ticket history retrieval | TicketRetriever, SQLite query |
| Deterministic policy enforcement | PolicyEngine (10 rules, KB-01 to KB-10) |
| Response generation | NVIDIA Nemotron grounded on KB content |
| Structured ticket creation | Store.create_ticket() to SQLite |
| Audit trail logging | Store.create_audit_event() to SQLite |
| Reviewer UI | Streamlit dashboard (app.py) |

---

## Architecture

`
Employee / Reviewer UI (Streamlit)
            |  AgentRequest
            v
    LangGraph StateGraph
    [understand] -> [retrieve] -> [policy] -> [generate] -> [persist]
     LLM+rules     KB+Tickets    PolicyEngine  Nemotron LLM  Ticket+Audit
                                                                  |
                                                           SQLite DB (app.db)
`

### Pipeline Nodes

| Node | Responsibility |
|---|---|
| understand | Extract category, search query, and domain facts (laptop age, employee type, catalog status) using LLM and deterministic heuristics |
| retrieve | Query UnifiedRetriever for top-3 KB policies and top-2 ticket history entries |
| policy | Run PolicyEngine - evaluates 10 priority-ordered rules and returns a deterministic PolicyVerdict |
| generate | Call NVIDIA Nemotron to generate a grounded response citing policy sources; falls back to deterministic synthesis if LLM unavailable |
| persist | Write structured Ticket and AuditEvent records to SQLite |

---

## Tech Stack

| Component | Technology |
|---|---|
| Orchestration | LangGraph StateGraph |
| LLM | NVIDIA Nemotron-3-Ultra-550B-A55B via OpenAI-compatible API |
| LLM Client | langchain-openai ChatOpenAI |
| Data Validation | Pydantic v2 |
| Knowledge Retrieval | BM25 (lexical) + optional FAISS (semantic) |
| Persistence | SQLite (WAL mode, thread-safe) |
| Reviewer UI | Streamlit 1.64 |
| Python | 3.13+ |

---

## Quick Start

### Prerequisites

- Python 3.13+
- NVIDIA API key (for live LLM mode)

### 1. Clone and install

`ash
git clone https://github.com/AdiXjaiswal/Internal-Service-Agent.git
cd Internal-Service-Agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
`

Or with uv (recommended):

`ash
uv sync
`

### 2. Configure environment

Create a .env file in the project root:

`env
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
`

### 3. Launch the Streamlit UI

`ash
.venv\Scripts\streamlit.exe run app.py
`

The app opens at http://localhost:8501.

### 4. Run Tests

`ash
.venv\Scripts\python.exe -m unittest discover tests -v
`

Expected: 77 tests, OK

---

## Project Structure

`
Internal-Service-Agent/
|-- app.py                         # Streamlit reviewer UI
|-- pyproject.toml                 # Project metadata and dependencies
|-- .env                           # API key configuration (not committed)
|
|-- data/
|   |-- knowledge_base.json        # 11 company IT policies (KB-01 to KB-10 + Asset)
|   |-- tickets.json               # Seeded historical ticket queue
|   |-- employee_requests.json     # 15 benchmark requests (REQ-01 to REQ-15)
|   -- app.db                     # SQLite database (auto-created)
|
|-- src/
|   |-- agent/                     # LangGraph orchestration layer
|   |   |-- models.py              # AgentRequest, AgentResponse, AgentState
|   |   |-- tools.py               # AgentTools wrappers
|   |   |-- llm.py                 # NVIDIA Nemotron client and prompt templates
|   |   -- orchestrator.py        # LangGraph StateGraph (AgentOrchestrator)
|   |
|   |-- policy/                    # Deterministic policy engine
|   |   |-- models.py              # Decision, EscalationTeam, PolicyRequest, PolicyVerdict
|   |   |-- rules.py               # 10 rule functions (KB-01 to KB-10 + Asset)
|   |   -- engine.py              # PolicyEngine: evaluate(), evaluate_all()
|   |
|   |-- retrieval/                 # Knowledge retrieval layer
|   |   |-- models.py              # KBArticle, RetrievalResult
|   |   |-- kb.py                  # KBRetriever (BM25 + optional FAISS)
|   |   |-- ticket.py              # TicketRetriever
|   |   -- service.py             # UnifiedRetriever (KB + Ticket combined)
|   |
|   -- storage/                   # SQLite persistence layer
|       |-- models.py              # Ticket, AuditEvent Pydantic models
|       -- store.py               # Store CRUD operations
|
-- tests/
    |-- test_policy.py             # 50 policy engine unit tests
    |-- test_retrieval.py          # 12 retrieval layer tests
    -- test_agent.py              # 15 agent orchestration integration tests
`

---

## Knowledge Base and Policies

The agent grounds all decisions in 11 company knowledge base articles. No LLM general knowledge is used as a policy substitute.

| Article | Title | Coverage |
|---|---|---|
| KB-01 | Password Reset | Account lockout, self-service portal, >5 failed attempts |
| KB-02 | VPN Access | Employee auto-grant, contractor requires Manager approval |
| KB-03 | Laptop Replacement | 3-year cycle, early with verified hardware failure |
| KB-04 | Software Installation | Catalog: self-install; non-catalog: IT Security review (3-5 days) |
| KB-05 | Printer Troubleshooting | Queue check, spooler restart, asset tag ticket |
| KB-06 | Email Mailbox Quota | Default 25 GB, >25 GB needs Manager approval, max 50 GB |
| KB-07 | Guest Wi-Fi Access | 24h codes from front-desk kiosk, no IT ticket needed |
| KB-08 | Expense Software Access | Finance owns provisioning; IT handles login issues only |
| KB-09 | Security Incident Reporting | Priority 1 - phishing/malware escalates to Security immediately |
| KB-10 | Work-From-Home Equipment | >3 days/week WFH requires Manager + Finance approval |
| Asset | Asset Management Policy | 4-year hardware refresh; early replacement requires Finance sign-off |

### Policy Rule Priority Order

`
Priority  5   KB-09  Security Incident     (evaluated FIRST - cannot be bypassed)
Priority 10   KB-01  Password Reset
Priority 15   KB-02  VPN Access
Priority 20   KB-03  Laptop Replacement
Priority 22   Asset  Asset Management Policy
Priority 25   KB-04  Software Installation
Priority 30   KB-05  Printer Troubleshooting
Priority 35   KB-06  Email Mailbox Quota
Priority 40   KB-07  Guest Wi-Fi
Priority 45   KB-08  Expense Software
Priority 50   KB-10  Work-From-Home Equipment
`

---

## Example Flows

### A - Account Lockout (RESOLVED)

> Employee: I am locked out after 6 password attempts.

- KB-01 triggered
- PolicyEngine: RESOLVED (no approval required)
- Response: Self-service portal link + IT manual unlock instructions
- Ticket: RESOLVED | Source: [KB-01] | Audit: logged

### B - Phishing Email (ESCALATED to Security)

> Employee: I got a suspicious email asking for my login.

- KB-09 triggered at priority 5 (security first)
- PolicyEngine: ESCALATED to Security
- Response: Report to security@veridian-corp.example immediately, do not forward
- Ticket: ESCALATED | Escalation team: Security | Audit: logged

### C - Non-Catalog Software (ESCALATED to IT Security)

> Employee: I need a data-analysis tool not in the approved catalog.

- KB-04 triggered, is_catalog_software = False
- PolicyEngine: ESCALATED to IT Security
- Response: IT Security review required, 3-5 business days
- Ticket: ESCALATED | Escalation team: IT Security

### D - Contractor VPN (ESCALATED to Manager)

> Employee: I am a contractor and need VPN access.

- KB-02 triggered, employee_type = contractor
- PolicyEngine: ESCALATED to Manager
- Response: Manager approval required via access request form
- Ticket: ESCALATED | Escalation team: Manager

### E - Laptop Replacement (FOLLOW_UP_REQUIRED)

> Employee: I need a replacement laptop.

- KB-03 triggered, laptop_age_years unknown
- PolicyEngine: FOLLOW_UP_REQUIRED
- Response: How old is your current laptop?
- Ticket: FOLLOW_UP_REQUIRED (awaiting employee response)

---

## Streamlit UI

| Panel | Features |
|---|---|
| Request Intake | Sample request dropdown (REQ-01 to REQ-15) + free-text entry |
| Execution Toggle | NVIDIA Nemotron (live) vs Fast Deterministic Engine (offline) |
| Decision Card | Color-coded status badge (RESOLVED / FOLLOW_UP / ESCALATED), escalation team, direct response |
| Sources Panel | KB article citations with titles and supporting excerpts |
| Ticket Inspector | Structured ticket fields + raw JSON view |
| Audit Trail | Compliance record with timestamps, rule evidence, destination |
| Database Explorer | Filterable view of all tickets and audit events in data/app.db |

---

## Running Tests

`ash
# Full suite (77 tests)
.venv\Scripts\python.exe -m unittest discover tests -v

# By module
.venv\Scripts\python.exe -m unittest tests.test_policy -v      # 50 tests
.venv\Scripts\python.exe -m unittest tests.test_retrieval -v   # 12 tests
.venv\Scripts\python.exe -m unittest tests.test_agent -v       # 15 tests
`

---

## Environment Configuration

| Variable | Description | Default |
|---|---|---|
| NVIDIA_API_KEY | NVIDIA Build API key | Required for live mode |
| NVIDIA_BASE_URL | NVIDIA OpenAI-compatible endpoint | https://integrate.api.nvidia.com/v1 |
| NVIDIA_MODEL | Model identifier | nvidia/nemotron-3-ultra-550b-a55b |

Falls back to **Fast Deterministic Engine** if no API key is set.

---

## Design Principles

**LLM for Language, Rules for Policy**
The LLM (NVIDIA Nemotron) handles classification, entity extraction, and response synthesis only. All routing decisions (RESOLVED, ESCALATED, FOLLOW_UP_REQUIRED) are made deterministically by PolicyEngine - preventing hallucinated or inconsistent policy enforcement.

**Security First**
KB-09 (Security Incident) runs at priority 5 - the highest priority rule. A phishing or malware signal always escalates to Security and cannot be bypassed by any other rule, regardless of retrieval context.

**No LLM Policy Substitution**
The system never uses general LLM knowledge to infer company policy. All responses must be grounded in the supplied data/knowledge_base.json articles.

**Full Traceability**
Every agent run produces a structured Ticket and AuditEvent in SQLite. The Streamlit UI provides a full audit trail viewer for compliance review.

