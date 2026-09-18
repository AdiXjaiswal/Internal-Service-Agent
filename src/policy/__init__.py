"""Policy engine package for the Internal Service Agent.

Provides a fully deterministic policy rule engine that enforces IT-support
policy constraints without relying on LLM judgment.

Public API
----------
:class:`PolicyEngine`
    Main engine — call ``engine.evaluate(request)`` to get a verdict.

:class:`PolicyRequest`
    Input model populated by the agent's classifier or follow-up Q&A.

:class:`PolicyVerdict`
    Output model carrying the decision, reason, escalation team, and
    optional follow-up question.

:class:`Decision`
    Enum of possible outcomes: RESOLVED, ESCALATED, FOLLOW_UP_REQUIRED, PASS.

:class:`EscalationTeam`
    Canonical team names used as escalation destinations.

Quick example
-------------
>>> from src.policy import PolicyEngine, PolicyRequest, Decision
>>> engine = PolicyEngine()
>>> verdict = engine.evaluate(PolicyRequest(
...     kb_ids=["KB-09"],
...     raw_text="I received a suspicious email asking for my password",
... ))
>>> verdict.decision == Decision.ESCALATED
True
>>> verdict.escalation_team
'Security'
"""

from __future__ import annotations

from .engine import PolicyEngine
from .models import Decision, EscalationTeam, PolicyRequest, PolicyRule, PolicyVerdict

__all__ = [
    "PolicyEngine",
    "PolicyRequest",
    "PolicyVerdict",
    "PolicyRule",
    "Decision",
    "EscalationTeam",
]
