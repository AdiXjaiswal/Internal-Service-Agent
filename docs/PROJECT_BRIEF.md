# Project Brief — Internal Service Agent (IT Support)

## 1. Project Overview

**Company:** Veridian Corp  
**Assignment:** Assignment 2 — Internal Service Agent  
**Function:** IT Support  
**Time limit:** 6 hours

The goal is to build a working internal employee-support agent that can handle common IT service requests using the supplied company knowledge base, employee-request queue, and ticket history.

The assignment is intended to test whether the candidate can turn a messy business problem into a working agent. The use of AI tools is explicitly allowed.

## 2. Problem Statement

Employees submit IT requests with different levels of clarity, risk, urgency, and required approvals. The support agent must understand the request, identify the applicable company policy or prior resolution, ask for missing information when necessary, resolve simple requests, and route risky or unclear requests to the appropriate human team.

The agent must also create a structured ticket and maintain an auditable record of what it decided and which source(s) supported the response.

## 3. Objectives

The prototype should:

1. Understand an employee's issue or request.
2. Identify the relevant knowledge-base policy or ticket-history context.
3. Ask sensible follow-up questions when required information is missing.
4. Resolve straightforward IT requests when policy permits.
5. Escalate requests that require another team, approval, investigation, or human judgment.
6. Create or update a structured ticket.
7. Show the source used for the answer or decision.
8. Maintain an audit trail of the agent's actions.

## 4. In-Scope Requests

The supplied data covers examples including:

- Password reset / account lockout
- VPN access and expired VPN credentials
- Laptop replacement and hardware faults
- Software installation
- Printer troubleshooting
- Mailbox quota
- Guest Wi-Fi
- Finance/expense-tool access and login issues
- Security incident reporting
- Home-office equipment
- Admin-access requests
- Browser-extension requests
- Ambiguous or incomplete requests

## 5. Source Data

The agent must use the assignment material as its source of truth:

### Knowledge Base / Policies

- KB-01 — Password Reset
- KB-02 — VPN Access
- KB-03 — Laptop Replacement
- KB-04 — Software Installation
- KB-05 — Printer Troubleshooting
- KB-06 — Email Mailbox Quota
- KB-07 — Guest Wi-Fi Access
- KB-08 — Expense Software Access
- KB-09 — Security Incident Reporting
- KB-10 — Work-from-Home Equipment
- Asset Management Policy extract — Finance & Assets, last updated Q2 2026

### Employee Requests

REQ-01 through REQ-15 are supplied in the assignment data and represent current employee cases.

### Existing Ticket Queue

TK-1042 through TK-1051 are supplied as ticket history/current cases.

Tickets marked **Resolved (closed)**, **Rejected (closed)**, or **Approved (closed)** are historical and are not actionable. Active tickets may be resolved directly or routed to a human according to the same judgment used for employee requests.

## 6. Expected User Experience

A reviewer should be able to submit an employee request and see:

1. Interpreted issue/category.
2. Relevant policy or historical ticket context.
3. Missing information / follow-up questions, if needed.
4. Proposed action.
5. Whether the request is resolved or escalated.
6. Structured ticket details.
7. Source citations.
8. Audit-trail entry.

## 7. Scope Boundaries

The prototype should not invent company policies, approvals, credentials, ticket outcomes, or external procedures that are not supported by the supplied sources.

Where the source material is insufficient or the request is risky/unclear, the agent should escalate rather than guess.

## 8. Success Criteria

The prototype is successful if a reviewer can open and test it and observe consistent behavior across simple, approval-dependent, security-sensitive, historical-context, and ambiguous requests.

The solution should prioritize correctness, traceability, and a clear demonstration over unnecessary product complexity.
