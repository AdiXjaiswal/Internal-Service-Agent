# System Design — Internal Service Agent (IT Support)

## 1. Proposed Architecture

```text
                    ┌──────────────────────┐
                    │   Reviewer / User    │
                    │   Streamlit UI       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Agent Orchestrator  │
                    │  LLM + workflow      │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
      │ KB Search   │   │ Ticket      │   │ Policy /     │
      │ / Retrieval │   │ Search      │   │ Rule Engine  │
      └──────┬──────┘   └──────┬──────┘   └──────┬───────┘
             │                 │                  │
             └─────────────────┼──────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Decision / Action    │
                    │ Resolve / Follow-up  │
                    │ / Escalate           │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
             ┌─────────────┐       ┌──────────────┐
             │ Ticket Store│       │ Audit Log    │
             └─────────────┘       └──────────────┘
```

## 2. Core Components

### 2.1 User Interface

A lightweight Streamlit interface is proposed for the 6-hour prototype.

The UI should provide:

- Employee/request input.
- Optional request/ticket ID.
- Submit button.
- Agent response.
- Status.
- Sources.
- Structured ticket.
- Audit trail.

A sample-case selector can be included to make the demo fast.

### 2.2 Agent Orchestrator

The orchestrator controls the sequence of work:

```text
Input
  ↓
Understand request
  ↓
Retrieve policy
  ↓
Search relevant ticket history
  ↓
Check policy/risk constraints
  ↓
Need clarification?
  ├── Yes → Ask follow-up
  └── No
       ↓
Resolve or escalate
       ↓
Create/update ticket
       ↓
Record audit event
       ↓
Return response + sources
```

The LLM should be responsible primarily for language understanding, classification, summarization, and selecting relevant tools. Deterministic policy checks should enforce important constraints.

### 2.3 Knowledge Retrieval

For the supplied dataset, a simple retrieval implementation is sufficient.

Recommended prototype approach:

- Store KB entries as structured records.
- Create embeddings or use lightweight keyword/semantic retrieval.
- Retrieve top relevant KB records.
- Pass only relevant records to the agent.

Example record:

```json
{
  "id": "KB-04",
  "title": "Software Installation",
  "content": "Standard software ... Non-catalog software requires Security review ..."
}
```

### 2.4 Ticket Retrieval

Store the supplied ticket queue in structured form.

The search tool should distinguish:

- Active tickets
- Closed historical tickets

Closed records can provide precedent/context but must not be directly acted upon.

### 2.5 Policy / Rule Engine

Important policy constraints should be implemented outside the LLM.

Examples:

```text
IF suspected phishing
→ Security escalation

IF non-catalog software
→ Security review

IF expense account does not exist
→ Finance owns access

IF guest Wi-Fi
→ No IT ticket required

IF VPN request AND contractor
→ Manager approval required

IF laptop replacement AND <4 years
→ Require verified hardware failure
```

This layer reduces hallucinated or inconsistent policy decisions.

### 2.6 Action Layer

Prototype tools can include:

```text
search_knowledge_base(query)
search_tickets(query)
check_policy(category, details)
create_ticket(ticket_data)
update_ticket(ticket_id, data)
create_audit_event(event)
```

The tool layer can initially write to SQLite or JSON files.

## 3. Decision States

### RESOLVED

Use when the supplied policy explicitly allows self-service/direct handling and no additional approval or investigation is required.

### FOLLOW_UP_REQUIRED

Use when a decision depends on missing information.

### ESCALATED

Use when the request requires:

- Security review
- Finance approval/processing
- Manager approval
- Human investigation
- Another specialized team
- Clarification that cannot safely be inferred

## 4. Ticket State Model

```text
NEW
 │
 ├── FOLLOW_UP_REQUIRED
 │
 ├── RESOLVED
 │
 └── ESCALATED
        │
        └── Human/team handling
```

Historical source tickets remain visible but are not changed unless the prototype explicitly represents a new linked case.

## 5. Example Flows

### Example A — Locked Account

```text
Employee: "I'm locked out after 6 password attempts."

→ Retrieve KB-01
→ Detect >5 failed attempts
→ Direct IT manual reset/unlock path
→ No approval required
→ Create structured ticket
→ Show KB-01
→ Audit action
```

### Example B — Guest Wi-Fi

```text
Employee: "Can I get Wi-Fi access for a guest tomorrow?"

→ Retrieve KB-07
→ Guest Wi-Fi code is valid for 24 hours
→ Employee can generate code at front-desk kiosk
→ No IT ticket required
→ Show KB-07
→ Audit response
```

### Example C — Phishing

```text
Employee: "I received an email asking for my login."

→ Retrieve KB-09
→ Security-sensitive request
→ Tell employee to report immediately to supplied Security address
→ Do not recommend forwarding it to other employees
→ Escalate / flag for Security
→ Create audit event
→ Show KB-09
```

### Example D — Non-Catalog Software

```text
Employee: "I need a data-analysis tool that isn't in the catalog."

→ Retrieve KB-04
→ Non-catalog software detected
→ Security review required
→ 3–5 business day expectation from policy
→ Escalate to Security
→ Create ticket
→ Show KB-04
```

## 6. Audit Design

Example:

```json
{
  "audit_id": "AUD-0001",
  "timestamp": "ISO-8601",
  "request_id": "REQ-03",
  "action": "escalate",
  "status": "escalated",
  "sources": ["KB-01"],
  "reason": "Account locked after more than five failed attempts",
  "destination": "IT"
}
```

Only concise evidence/reason fields should be stored; hidden chain-of-thought should not be exposed or persisted.

## 7. Technology Proposal

A practical 6-hour stack:

- **Python**
- **Streamlit** — UI
- **LLM API** — agent reasoning/language understanding
- **LangGraph or a simple tool-calling workflow** — orchestration
- **FAISS / Chroma or lightweight retrieval** — KB search
- **SQLite** — tickets and audit log
- **Pydantic** — structured input/output validation

The implementation should favor fewer moving parts if time becomes constrained.

## 8. Deployment

Preferred submission:

- GitHub repository
- Simple hosted Streamlit demo if feasible

Fallback:

- One-command local run documented in README.

Example:

```bash
pip install -r requirements.txt
streamlit run app.py
```
