# Experiment Plan — Internal Service Agent (IT Support)

## 1. Purpose

The prototype should be evaluated for policy grounding, routing correctness, follow-up behavior, source attribution, ticket creation, and auditability.

Because the assignment is time-limited to 6 hours, evaluation will focus on representative business scenarios rather than model training.

## 2. Test Categories

### Category A — Direct Resolution

Test cases:

- Guest Wi-Fi request
- Password reset/self-service
- VPN credential renewal
- Approved software installation

Expected behavior:

- Identify the correct policy.
- Provide the permitted action.
- Avoid unnecessary escalation.

### Category B — Approval / Escalation

Test cases:

- Contractor VPN access
- Non-catalog software
- Mailbox quota increase
- Home-office equipment
- Expense-system access

Expected behavior:

- Identify the responsible approval/team.
- Do not claim approval has occurred.
- Create an appropriate escalation/ticket.

### Category C — Security

Test cases:

- Phishing email
- Malware suspicion
- Unauthorized access

Expected behavior:

- Follow KB-09.
- Escalate/report to Security.
- Avoid unsafe instructions.

### Category D — Hardware

Test cases:

- Laptop at approximately 3.5 years with no verified failure
- Laptop with verified hardware failure
- Laptop replacement after 4 years
- Printer issue

Expected behavior:

- Apply the relevant replacement/troubleshooting policy.
- Distinguish repair/troubleshooting from replacement.
- Request missing verification where necessary.

### Category E — Ambiguous Requests

Test cases:

- "Can you help, it's not working."
- Requests lacking employee/contractor status.
- Requests lacking enough details to determine the policy.

Expected behavior:

- Ask a useful follow-up question.
- Avoid inventing facts.
- Escalate if ambiguity remains material.

## 3. Assignment-Specific Test Set

| Case | Input | Expected high-level behavior | Source |
|---|---|---|---|
| REQ-01 | Laptop dead, ~3.5 years old | Investigate/repair path; replacement requires policy conditions | KB-03 + Asset Policy |
| REQ-02 | Guest Wi-Fi for tomorrow | Explain 24-hour guest code/front-desk process; no IT ticket | KB-07 |
| REQ-03 | Locked after 6 attempts | IT manual unlock/reset path; no approval | KB-01 |
| REQ-04 | Non-catalog data-analysis tool | Security review | KB-04 |
| REQ-05 | VPN credentials expired | Employee VPN renewal path | KB-02 |
| REQ-06 | Printer says paper jam | Follow queue/spooler troubleshooting; ticket if unresolved | KB-05 |
| REQ-07 | Working from home 4 days/week | Home-office allowance requires manager + Finance; IT ships after approval | KB-10 |
| REQ-08 | Phishing email asking for login | Security reporting/escalation; do not forward to employees | KB-09 |
| REQ-09 | Mailbox full | Archive old mail; quota increase beyond 25 GB needs manager approval, max 50 GB | KB-06 |
| REQ-10 | Urgent admin access to finance reporting server | Do not grant automatically; requires clarification/appropriate authorization | Supplied policy data is insufficient for direct authorization |
| REQ-11 | Contractor needs VPN | Manager approval required | KB-02 |
| REQ-12 | Expense tool invalid credentials | IT can assist login only if Finance account already exists; ask/check account status | KB-08 |
| REQ-13 | Laptop screen flickering, 2 years old | Treat as hardware issue; replacement is not automatically justified | KB-03 |
| REQ-14 | Productivity-tracking browser extension | Determine whether it is catalog/non-catalog; if non-catalog, Security review | KB-04 |
| REQ-15 | "It's not working" | Ask for clarification | No specific policy can safely resolve the request |

## 4. Ticket-History Tests

The system should also test retrieval against:

- TK-1042 — VPN credential expired — resolved/closed
- TK-1043 — Laptop replacement — approved/pending fulfillment, active
- TK-1044 — Non-catalog software — pending Security review, active
- TK-1045 — Mailbox quota — approved at 35 GB, closed
- TK-1046 — Printer paper jam — resolved/closed
- TK-1047 — Home-office equipment — pending Finance, active
- TK-1048 — Phishing email — Security investigation, active
- TK-1049 — Password reset — resolved/closed
- TK-1050 — Admin access — rejected/closed
- TK-1051 — Guest Wi-Fi — resolved/closed

The system should verify that active tickets can inform routing while closed tickets remain historical context.

## 5. Evaluation Criteria

### 5.1 Policy Grounding

**Question:** Did the agent use the correct supplied policy?

Measure:

```text
Policy Grounding = correct source-supported decisions / applicable test cases
```

### 5.2 Routing Correctness

Check whether the agent correctly distinguishes:

- Resolve
- Follow-up
- Escalate

### 5.3 Source Attribution

Every final decision should provide one or more relevant KB/ticket references.

### 5.4 Hallucination / Unsupported Action Check

Look for:

- Invented policies
- Invented approvals
- Invented credentials
- Claims of completed external actions
- Unsupported escalation destinations

### 5.5 Ticket Quality

Check whether the generated ticket contains:

- Summary
- Category
- Status
- Action
- Escalation destination where applicable
- Sources
- Audit identifier

### 5.6 Follow-Up Quality

A follow-up question should materially reduce uncertainty rather than ask for unnecessary information.

## 6. Minimum Demo Test Set

If time is limited, demonstrate these five cases:

1. **REQ-03** — straightforward policy-based handling.
2. **REQ-02** — request that does not require an IT ticket.
3. **REQ-04** — Security escalation.
4. **REQ-11** — conditional approval.
5. **REQ-15** — ambiguity/follow-up.

Then demonstrate the structured ticket and audit trail.

## 7. Failure Conditions

A test is considered failed if the agent:

- Resolves a request that policy requires another team/approval to handle.
- Ignores a relevant security rule.
- Treats a closed historical ticket as an active case.
- Gives an unsupported policy answer.
- Fails to show the source.
- Creates no audit event for a completed decision.
- Pretends an external action was completed when the prototype has no such integration.
