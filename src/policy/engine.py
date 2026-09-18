"""Deterministic policy engine for the Internal Service Agent.

The engine evaluates a :class:`~src.policy.models.PolicyRequest` against an
ordered list of policy rules and returns the first non-PASS
:class:`~src.policy.models.PolicyVerdict`.

Usage
-----
>>> from src.policy import PolicyEngine, PolicyRequest
>>> engine = PolicyEngine()
>>> verdict = engine.evaluate(PolicyRequest(
...     category="VPN",
...     kb_ids=["KB-02"],
...     employee_type="contractor",
... ))
>>> verdict.decision
<Decision.ESCALATED: 'ESCALATED'>
>>> verdict.escalation_team
'Manager'
"""

from __future__ import annotations

from typing import Callable, Optional

from .models import Decision, PolicyRequest, PolicyRule, PolicyVerdict
from .rules import RULE_REGISTRY

# Type alias for a rule callable
RuleFunc = Callable[[PolicyRequest], PolicyVerdict]


class PolicyEngine:
    """Deterministic policy rule engine.

    Evaluates a :class:`PolicyRequest` against all registered rules in
    priority order and returns the first non-PASS verdict.  If no rule
    fires, returns a default ``FOLLOW_UP_REQUIRED`` verdict.

    Parameters
    ----------
    rules:
        Optional override list of ``(rule_func, PolicyRule)`` tuples.
        Defaults to :data:`~src.policy.rules.RULE_REGISTRY`.
    """

    def __init__(
        self,
        rules: Optional[list[tuple[RuleFunc, PolicyRule]]] = None,
    ) -> None:
        self._rules: list[tuple[RuleFunc, PolicyRule]] = (
            rules if rules is not None else list(RULE_REGISTRY)
        )
        # Sort by priority (ascending — lowest = first)
        self._rules.sort(key=lambda entry: entry[1].priority)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, request: PolicyRequest) -> PolicyVerdict:
        """Evaluate *request* against all registered rules.

        Returns the first non-PASS verdict.  If no rule matches, returns
        a ``FOLLOW_UP_REQUIRED`` verdict prompting the agent to gather
        more information.

        Parameters
        ----------
        request:
            The fully or partially populated policy request.

        Returns
        -------
        PolicyVerdict
            Deterministic decision with rule ID, reason, and optional
            escalation team or follow-up question.
        """
        for rule_fn, rule_meta in self._rules:
            verdict = rule_fn(request)
            if verdict.decision != Decision.PASS:
                return verdict

        # No rule matched — ask the agent/employee for more context
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="engine-no-match",
            source_kb_id="",
            reason=(
                "No matching policy rule was found for this request. "
                "Additional context or clarification is needed to determine "
                "the correct course of action."
            ),
            follow_up_question=(
                "Could you provide more details about your request? "
                "For example: the type of issue, software name, or device involved."
            ),
        )

    def evaluate_all(self, request: PolicyRequest) -> list[PolicyVerdict]:
        """Return verdicts from ALL rules that fire (not just the first).

        Useful for debugging or when multiple policies may overlap.

        Returns
        -------
        list[PolicyVerdict]
            All non-PASS verdicts, in priority order.
        """
        verdicts: list[PolicyVerdict] = []
        for rule_fn, _ in self._rules:
            verdict = rule_fn(request)
            if verdict.decision != Decision.PASS:
                verdicts.append(verdict)
        return verdicts

    def list_rules(self) -> list[PolicyRule]:
        """Return metadata for all registered rules, in priority order."""
        return [meta for _, meta in self._rules]

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        """Look up a registered rule by its ``rule_id``."""
        for _, meta in self._rules:
            if meta.rule_id == rule_id:
                return meta
        return None

    # ------------------------------------------------------------------
    # Convenience class method
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "PolicyEngine":
        """Return a ``PolicyEngine`` loaded with the default rule registry."""
        return cls()
