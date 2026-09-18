"""Agent Orchestrator powered by LangGraph.

Coordinates language understanding, knowledge/ticket retrieval, deterministic
policy constraints, response synthesis, ticket creation, and audit logging.
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph

from ..policy.engine import PolicyEngine
from ..policy.models import Decision, PolicyRequest, PolicyVerdict
from ..retrieval.service import UnifiedRetriever
from ..storage.models import AuditEvent, Ticket
from ..storage.store import Store
from .llm import extract_entities_with_fallback, generate_agent_response, get_llm
from .models import AgentRequest, AgentResponse, AgentState


class AgentOrchestrator:
    """End-to-end IT support agent orchestrator.

    Parameters
    ----------
    llm:
        Chat model instance. Defaults to NVIDIA Nemotron client if None.
    retriever:
        Retrieval service for KB and ticket history.
    policy_engine:
        Deterministic policy rule engine.
    store:
        SQLite storage layer for tickets and audit logs.
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        retriever: Optional[UnifiedRetriever] = None,
        policy_engine: Optional[PolicyEngine] = None,
        store: Optional[Store] = None,
        use_llm: bool = True,
    ) -> None:
        if llm is not None:
            self.llm = llm
        elif use_llm:
            self.llm = get_llm()
        else:
            self.llm = None

        self.retriever = retriever or UnifiedRetriever()
        self.policy_engine = policy_engine or PolicyEngine()
        self.store = store or Store()

        # Build and compile the LangGraph workflow
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("understand", self._understand_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("policy", self._policy_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_node("persist", self._persist_node)

        workflow.set_entry_point("understand")
        workflow.add_edge("understand", "retrieve")
        workflow.add_edge("retrieve", "policy")
        workflow.add_edge("policy", "generate")
        workflow.add_edge("generate", "persist")
        workflow.add_edge("persist", END)

        return workflow

    # ------------------------------------------------------------------ #
    # Graph Nodes
    # ------------------------------------------------------------------ #

    def _understand_node(self, state: AgentState) -> dict[str, Any]:
        """Node 1: Extract classification category, search keywords, and domain facts."""
        entities = extract_entities_with_fallback(state.request.request, self.llm)
        return {"extracted_entities": entities}

    def _retrieve_node(self, state: AgentState) -> dict[str, Any]:
        """Node 2: Retrieve applicable knowledge base policies and ticket history."""
        search_query = (
            state.extracted_entities.get("search_query")
            or state.request.request
        )

        results = self.retriever.search(
            query=search_query, kb_k=3, ticket_k=2, active_only=False
        )

        # Filter out low-relevance noise (keep top or results with score >= 0.2)
        kb_items = [r for r in results if r.is_kb]
        if kb_items:
            max_score = kb_items[0].score
            threshold = min(0.2, max_score * 0.4) if max_score > 0 else 0.0
            kb_items = [r for r in kb_items if r.score >= threshold]

        kb_ids = [r.source_id for r in kb_items]
        ticket_ids = [r.source_id for r in results if r.is_ticket]

        return {
            "retrieval_results": results,
            "kb_ids": kb_ids,
            "ticket_ids": ticket_ids,
        }

    def _policy_node(self, state: AgentState) -> dict[str, Any]:
        """Node 3: Deterministic policy evaluation enforcing security & routing constraints."""
        entities = state.extracted_entities

        policy_req = PolicyRequest(
            category=entities.get("category", ""),
            kb_ids=state.kb_ids,
            raw_text=state.request.request,
            employee_type=entities.get("employee_type"),
            is_catalog_software=entities.get("is_catalog_software"),
            laptop_age_years=entities.get("laptop_age_years"),
            hardware_failure_verified=entities.get("hardware_failure_verified"),
            quota_gb_requested=entities.get("quota_gb_requested"),
            is_guest_wifi=entities.get("is_guest_wifi"),
            expense_account_exists=entities.get("expense_account_exists"),
            wfh_days_per_week=entities.get("wfh_days_per_week"),
        )

        verdict = self.policy_engine.evaluate(policy_req)
        return {"policy_verdict": verdict}

    def _generate_node(self, state: AgentState) -> dict[str, Any]:
        """Node 4: Grounded customer-facing response synthesis."""
        verdict = state.policy_verdict or PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            reason="Additional clarification required.",
        )

        response_text = generate_agent_response(
            employee=state.request.employee,
            request_text=state.request.request,
            verdict=verdict,
            sources=state.retrieval_results,
            llm=self.llm,
        )

        return {"generated_response": response_text}

    def _persist_node(self, state: AgentState) -> dict[str, Any]:
        """Node 5: Create/update structured ticket and record audit trail event in SQLite."""
        verdict = state.policy_verdict or PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            reason="Clarification required",
        )

        # 1. Map verdict decision to ticket status
        if verdict.decision == Decision.RESOLVED:
            ticket_status = "RESOLVED"
            action = "resolve"
        elif verdict.decision == Decision.ESCALATED:
            ticket_status = "ESCALATED"
            action = "escalate"
        else:
            ticket_status = "FOLLOW_UP_REQUIRED"
            action = "follow_up"

        category = state.extracted_entities.get("category", "IT Support")
        summary = (
            state.extracted_entities.get("summary")
            or state.request.request[:100]
        )
        priority_or_risk = state.extracted_entities.get(
            "priority_or_risk", "medium"
        )

        source_ids = state.kb_ids + state.ticket_ids
        if verdict.source_kb_id and verdict.source_kb_id not in source_ids:
            source_ids.append(verdict.source_kb_id)

        # 2. Persist ticket
        if state.request.ticket_id:
            # Update existing ticket
            ticket = self.store.update_ticket(
                ticket_id=state.request.ticket_id,
                category=category,
                status=ticket_status,
                recommended_action=verdict.reason,
                escalation_team=verdict.escalation_team,
                source_ids=source_ids,
            )
            if not ticket:
                ticket = self.store.create_ticket(
                    Ticket(
                        ticket_id=state.request.ticket_id,
                        request_id=state.request.request_id,
                        employee=state.request.employee,
                        email=state.request.email,
                        category=category,
                        summary=summary,
                        priority_or_risk=priority_or_risk,
                        status=ticket_status,
                        recommended_action=verdict.reason,
                        escalation_team=verdict.escalation_team,
                        source_ids=source_ids,
                    )
                )
        else:
            ticket = self.store.create_ticket(
                Ticket(
                    request_id=state.request.request_id,
                    employee=state.request.employee,
                    email=state.request.email,
                    category=category,
                    summary=summary,
                    priority_or_risk=priority_or_risk,
                    status=ticket_status,
                    recommended_action=verdict.reason,
                    escalation_team=verdict.escalation_team,
                    source_ids=source_ids,
                )
            )

        # 3. Create Audit Event
        evidence = (
            f"Rule {verdict.rule_id} evaluated with source {verdict.source_kb_id}"
            if verdict.rule_id
            else None
        )

        audit_event = self.store.create_audit_event(
            AuditEvent(
                audit_id="",
                request_id=state.request.request_id,
                ticket_id=ticket.ticket_id,
                user_input=state.request.request,
                retrieved_sources=source_ids,
                action=action,
                status=ticket_status.lower(),
                escalation_decision=verdict.escalation_team,
                reason=verdict.reason,
                evidence=evidence,
                agent_tool_action=f"PolicyEngine:{verdict.rule_id or 'default'}",
                destination=verdict.escalation_team,
            )
        )

        # Link audit_id back to ticket
        if ticket.ticket_id:
            ticket = self.store.update_ticket(
                ticket.ticket_id, audit_id=audit_event.audit_id
            ) or ticket

        final_response = AgentResponse(
            category=category,
            status=ticket_status.lower(),
            response=state.generated_response,
            action=action,
            escalation_team=verdict.escalation_team,
            sources=source_ids,
            ticket=ticket.model_dump() if ticket else None,
            audit_id=audit_event.audit_id,
        )

        return {
            "ticket": ticket,
            "audit_id": audit_event.audit_id,
            "final_response": final_response,
        }

    # ------------------------------------------------------------------ #
    # Public Execution API
    # ------------------------------------------------------------------ #

    def run(self, request: AgentRequest) -> AgentResponse:
        """Run the full agent orchestration pipeline on an incoming request."""
        initial_state = AgentState(request=request)
        final_state = self.app.invoke(initial_state)

        if isinstance(final_state, dict):
            resp = final_state.get("final_response")
            if resp is not None:
                return resp
            # Fallback if state is dict
            return AgentResponse(
                category="IT Support",
                status="resolved",
                response=final_state.get("generated_response", ""),
                action="resolve",
            )

        return final_state.final_response  # type: ignore[return-value]
