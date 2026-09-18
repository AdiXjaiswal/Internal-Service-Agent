# Internal Service Agent — IT Support

An agentic AI prototype for handling internal employee IT-support requests using the supplied Veridian Corp knowledge base, policies, employee requests, and ticket history.

## 1. Assignment

**Assignment:** Assignment 2 — Internal Service Agent  
**Company:** Veridian Corp  
**Function:** IT Support  
**Time limit:** 6 hours

The assignment requires a working agent/clickable prototype, architecture and process flow, inputs/sources/assumptions, AI-tool usage, a 15-minute demo and defence, GitHub submission, demo video, and a 10-slide presentation.

## 2. What the Agent Does

The agent:

1. Understands an employee request.
2. Retrieves relevant company policy.
3. Searches existing ticket history when useful.
4. Determines whether more information is needed.
5. Resolves simple policy-supported requests.
6. Escalates requests requiring approval, investigation, Security, Finance, or human judgment.
7. Creates a structured ticket.
8. Shows the sources used.
9. Records an audit event.

## 3. Design Principle

The supplied company material is the source of truth.

The system should not invent policies or rely on general LLM knowledge when a company-specific policy is required.

The LLM is used for language understanding and agent orchestration; important policy constraints are enforced through deterministic application logic where practical.

## 4. High-Level Architecture

```text
Employee Request
       ↓
Agent / Orchestrator
       ↓
┌───────────────┬────────────────┐
│ Knowledge     │ Ticket History │
│ Retrieval     │ Retrieval      │
└───────┬───────┴───────┬────────┘
        └───────┬───────┘
                ↓
        Policy / Rule Check
                ↓
      ┌─────────┼──────────┐
      ↓         ↓          ↓
   Resolve   Follow-up  Escalate
      └─────────┼──────────┘
                ↓
        Structured Ticket
                ↓
            Audit Log
```

See [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) for the detailed design.

## 5. Source Data

The prototype uses only the supplied assignment material:

- KB-01 to KB-10
- Asset Management Policy extract
- REQ-01 to REQ-15
- TK-1042 to TK-1051

Closed tickets are historical context and are not actionable.

## 6. Example Behaviors

### Password Lockout

A user locked out after more than five failed attempts is directed to the IT manual unlock/reset path according to KB-01.

### Guest Wi-Fi

A guest Wi-Fi request can be handled using the 24-hour guest-code process in KB-07. No IT ticket is required by the policy.

### Non-Catalog Software

A non-catalog software request is routed for Security review according to KB-04.

### Phishing

A suspected phishing incident follows KB-09 and is reported/escalated to Security. The agent should not recommend forwarding the suspicious email to other employees.

### Ambiguous Request

An unclear request such as "it's not working" should result in a useful follow-up question rather than an invented resolution.

## 7. Suggested Project Structure

```text
internal-service-agent/
│
├── app.py
├── requirements.txt
├── README.md
│
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── REQUIREMENTS.md
│   ├── SYSTEM_DESIGN.md
│   └── EXPERIMENT_PLAN.md
│
├── data/
│   ├── knowledge_base.json
│   ├── employee_requests.json
│   └── tickets.json
│
├── src/
│   ├── agent/
│   ├── retrieval/
│   ├── tools/
│   ├── policy/
│   └── storage/
│
└── tests/
```

## 8. Local Run

The exact commands depend on the selected implementation.

Typical Streamlit setup:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Environment variables for API keys should be stored in a local `.env` file and excluded from Git.

## 9. Prototype Assumptions

- The supplied assignment document is the authoritative company-policy source.
- The prototype does not actually reset passwords, issue VPN credentials, grant admin access, approve purchases, or perform Security/Finance actions unless an explicit integration is implemented.
- A "resolved" response means the agent has provided the policy-supported resolution/action in the prototype; it does not imply an external IT system was changed.
- Existing closed tickets are historical context.
- Existing active tickets may influence routing/context.
- When policy information is insufficient, the agent should ask for clarification or escalate rather than invent a rule.

## 10. AI Tools Used

The final submission should document the actual AI tools used during development and explain their purpose.

Example categories:

- LLM-assisted coding
- LLM-assisted debugging
- LLM/agent framework
- Embedding/retrieval model, if used
- Any AI-assisted testing/documentation

Only tools actually used in the final implementation should be listed in the final submission.

## 11. Demo Plan

A concise 15-minute demo can follow:

```text
1 min   — Problem and objective
2 min   — Architecture
7 min   — Live agent demonstrations
2 min   — Sources + structured tickets
1 min   — Audit trail
2 min   — Design decisions, limitations, future improvements
```

Recommended live cases:

- Password lockout
- Guest Wi-Fi
- Non-catalog software
- Contractor VPN
- Ambiguous request

## 12. Documentation

- [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) — project scope and objectives
- [`REQUIREMENTS.md`](REQUIREMENTS.md) — functional and technical requirements
- [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) — architecture and process flow
- [`EXPERIMENT_PLAN.md`](EXPERIMENT_PLAN.md) — test/evaluation plan

## 13. Final Submission Checklist

- [ ] Working agent or clickable prototype
- [ ] Architecture/process flow documented
- [ ] Inputs, sources, and assumptions documented
- [ ] AI tools and their usage documented
- [ ] Structured ticket generation works
- [ ] Source attribution works
- [ ] Audit trail works
- [ ] Security escalation works
- [ ] Follow-up questions work
- [ ] GitHub repository is clean
- [ ] Demo video has open access
- [ ] 10-slide PPT prepared
- [ ] 15-minute demo flow rehearsed
