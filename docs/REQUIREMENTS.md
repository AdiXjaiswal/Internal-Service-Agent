# Requirements — Internal Service Agent (IT Support)

## 1. Functional Requirements

### FR-01 — Request Intake

The system shall accept an employee's IT-support request as free text.

Optional structured fields:

- Employee name
- Employee email
- Request ID
- Existing ticket ID
- Date opened

If these fields are unavailable, the agent may ask for the required information.

### FR-02 — Issue Understanding

The agent shall determine the likely request category, such as:

- Password/account access
- VPN
- Laptop/hardware
- Software installation
- Printer
- Email/mailbox
- Guest Wi-Fi
- Finance/expense software
- Security incident
- Home-office equipment
- Admin access
- Other/unclear

The category is an internal classification and should not override explicit policy evidence.

### FR-03 — Knowledge Retrieval

The agent shall retrieve relevant information from the supplied knowledge base and policies.

The agent must not treat general LLM knowledge as a substitute for company policy.

### FR-04 — Ticket-History Retrieval

The agent shall be able to search the supplied ticket queue.

Ticket history may be used for:

- Prior resolution patterns
- Existing active cases
- Consistency/context

Closed tickets are historical and must not be treated as actionable.

### FR-05 — Follow-Up Questions

The agent shall ask concise follow-up questions when information required to make a policy-supported decision is missing.

Examples:

- Employee/contractor status for VPN access.
- Whether a software request is in the approved catalog.
- Whether a laptop has a verified hardware failure.
- Relevant asset/ticket information for printer issues.

### FR-06 — Direct Resolution

The agent may resolve simple requests when the supplied policy explicitly permits it.

Examples include:

- Password reset guidance.
- Guest Wi-Fi guidance.
- Approved software self-installation guidance.
- VPN renewal guidance for eligible employees.

The prototype should represent the resolution clearly rather than claiming that an external system was actually changed unless such a tool exists.

### FR-07 — Escalation

The agent shall escalate when:

- A request requires another department's approval.
- A request is security-sensitive.
- The policy requires human review.
- The request is unclear after reasonable clarification.
- The available sources do not contain enough information to make a safe decision.

The escalation destination should be grounded in the supplied policy where possible.

### FR-08 — Structured Ticket

The agent shall create a structured ticket containing at least:

```text
ticket_id
request_id
employee
email
category
summary
priority_or_risk
status
recommended_action
escalation_team
source_ids
created_at
audit_id
```

For the prototype, ticket IDs may be generated locally.

### FR-09 — Source Display

Every substantive recommendation/resolution should display the source used, preferably with:

- KB ID / policy name
- Relevant ticket ID(s), when used
- Short supporting excerpt or evidence field

### FR-10 — Audit Trail

Every agent decision/action shall record:

- Timestamp
- Request/ticket identifier
- User input
- Retrieved sources
- Action taken
- Status
- Escalation decision
- Reason/evidence
- Agent/tool action

Do not expose hidden chain-of-thought. Store concise decision reasons/evidence instead.

## 2. Non-Functional Requirements

### NFR-01 — Traceability

A reviewer must be able to understand why the agent reached its visible outcome and which supplied source supported it.

### NFR-02 — Safety

Security-sensitive requests must not be automatically resolved when the supplied policy requires reporting/escalation.

### NFR-03 — Determinism Where Appropriate

Policy constraints and routing rules should be enforced by deterministic application logic where practical rather than relying entirely on an LLM.

### NFR-04 — Usability

The reviewer should be able to test the prototype without reading the source code.

### NFR-05 — Reproducibility

The repository should contain clear setup and run instructions.

### NFR-06 — Source Grounding

The agent should prefer supplied company data over model knowledge and explicitly state when the supplied information is insufficient.

## 3. Policy Rules to Encode

| ID | Title | Rule |
|---|---|---|
| KB-01 | Password Reset | Employees can reset their own password via the self-service portal at any time. If locked out after 5 failed attempts, contact IT to unlock the account manually. No approval required. |
| KB-02 | VPN Access | VPN access is granted automatically to all full-time employees. Contractors require manager approval submitted via the access request form. VPN credentials expire every 90 days and must be renewed by the employee. |
| KB-03 | Laptop Replacement | Laptops are eligible for replacement after 3 years of service, or earlier in case of verified hardware failure. Requests must be raised at least 2 weeks in advance of intended replacement. |
| KB-04 | Software Installation Requests | Standard software (listed in the approved catalog) can be self-installed. Non-catalog software requires IT Security review, which takes 3-5 business days. |
| KB-05 | Printer Troubleshooting | For printer problems, first check the printer queue and restart the print spooler. If the issue persists after restart, log a ticket with the printer's asset tag. |
| KB-06 | Email Mailbox Quota | Default mailbox quota is 25GB. Employees nearing quota should archive old mail. Quota increases beyond 25GB require manager approval and are capped at 50GB. |
| KB-07 | Guest Wi-Fi Access | Guest Wi-Fi codes are valid for 24 hours and can be generated by any employee at the front-desk kiosk. No IT ticket is required. |
| KB-08 | Expense Software Access | Access to the expense management tool is granted by Finance, not IT. IT can only assist with login/technical issues once an account already exists. |
| KB-09 | Security Incident Reporting | Any suspected phishing email, malware, or unauthorized access attempt must be reported to security@veridian-corp.example immediately and should not be forwarded to other employees. |
| KB-10 | Work-From-Home Equipment | Employees working remotely more than 3 days/week are eligible for a one-time home office equipment allowance (chair, monitor). Requires manager sign-off and Finance processing — IT only handles the equipment shipping request once approved. |
| Asset Policy | Asset Management Policy | Company-issued hardware follows a standard 4-year refresh cycle from date of issue. Early replacement outside the cycle requires Finance sign-off in addition to IT approval. |

## 4. Data/Interface Requirements

### Input

```json
{
  "employee": "string",
  "email": "string",
  "request": "string",
  "request_id": "optional string",
  "ticket_id": "optional string"
}
```

### Output

```json
{
  "category": "string",
  "status": "resolved | follow_up_required | escalated",
  "response": "string",
  "action": "string",
  "escalation_team": "optional string",
  "sources": ["KB-xx", "TK-xxxx"],
  "ticket": {},
  "audit_id": "string"
}
```

## 5. Acceptance Criteria

A reviewer should be able to verify that:

- The agent grounds answers in the supplied data.
- It can distinguish direct resolution from escalation.
- It asks for missing information when needed.
- Security-related cases are handled according to KB-09.
- Closed tickets are treated as history, not active work.
- Relevant active tickets can be routed/resolved using the same policy logic.
- Sources are visible.
- A structured ticket is produced.
- An audit entry is produced.
