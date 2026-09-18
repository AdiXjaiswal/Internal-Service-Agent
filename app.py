"""Streamlit Reviewer UI for the Internal Service Agent.

Features:
- Sample Request Dropdown (REQ-01 to REQ-15) for quick 1-click testing
- Free-text Request Box for custom employee inputs
- Decision Card with Status badges (RESOLVED, FOLLOW_UP_REQUIRED, ESCALATED),
  Escalation Team, and Direct Response
- Sources Panel displaying cited KB articles / ticket IDs with supporting excerpts
- Structured Ticket Inspector & Audit Trail Viewer
- SQLite Database & Ticket Queue Explorer
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv

from src.agent import AgentOrchestrator, AgentRequest, AgentResponse, get_llm
from src.policy import PolicyEngine
from src.retrieval import UnifiedRetriever
from src.storage import Store

# ---------------------------------------------------------------------------
# Page configuration & styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Internal Service Agent — IT Support",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()

# Inject modern styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.35rem 0.9rem;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .status-resolved {
        background-color: #DCFCE7;
        color: #15803D;
        border: 1px solid #86EFAC;
    }
    .status-follow-up {
        background-color: #FEF3C7;
        color: #B45309;
        border: 1px solid #FCD34D;
    }
    .status-escalated {
        background-color: #FEE2E2;
        color: #B91C1C;
        border: 1px solid #FCA5A5;
    }
    .decision-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 0.75rem;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
    }
    .response-box {
        background: #FFFFFF;
        border-left: 4px solid #3B82F6;
        padding: 1rem 1.25rem;
        border-radius: 0.375rem;
        font-size: 1.05rem;
        line-height: 1.6;
        margin-top: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .source-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 0.5rem;
        padding: 0.9rem;
        margin-bottom: 0.75rem;
    }
    .metric-card {
        background: #F1F5F9;
        border-radius: 0.5rem;
        padding: 0.75rem;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached Resources
# ---------------------------------------------------------------------------
@st.cache_resource
def get_storage() -> Store:
    return Store(db_path="data/app.db", seed=True)


@st.cache_resource
def get_retriever() -> UnifiedRetriever:
    store = get_storage()
    return UnifiedRetriever(store=store, db_path="data/app.db")


@st.cache_resource
def get_policy_engine() -> PolicyEngine:
    return PolicyEngine()


@st.cache_data
def load_sample_requests() -> list[dict[str, Any]]:
    path = Path("data/employee_requests.json")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# Sidebar: Setup & Sample Requests
# ---------------------------------------------------------------------------
store = get_storage()
retriever = get_retriever()
policy_engine = get_policy_engine()
sample_requests = load_sample_requests()

with st.sidebar:
    st.image("https://img.icons8.com/color/96/shield.png", width=64)
    st.title("Configuration")

    # Execution Mode
    api_key_available = bool(os.getenv("NVIDIA_API_KEY"))
    mode_options = ["NVIDIA Nemotron (Live LLM)", "Fast Deterministic Engine (Offline)"]
    default_mode_idx = 0 if api_key_available else 1
    selected_mode = st.radio(
        "Agent Execution Mode",
        mode_options,
        index=default_mode_idx,
        help="Choose whether to call NVIDIA Nemotron for language generation or run deterministically offline.",
    )
    use_llm = "Live LLM" in selected_mode

    if use_llm and not api_key_available:
        st.warning("⚠️ NVIDIA_API_KEY is not set in environment or .env. Falling back to offline mode.")
        use_llm = False

    st.markdown("---")
    st.subheader("Benchmark Requests")
    st.caption("Select a sample case (REQ-01 to REQ-15) for 1-click evaluation:")

    sample_titles = ["-- Custom / Free-text --"] + [
        f"{req['request_id']}: {req['employee']} — {req['request'][:38]}..."
        for req in sample_requests
    ]
    selected_sample_idx = st.selectbox(
        "Load Sample Case",
        range(len(sample_titles)),
        format_func=lambda i: sample_titles[i],
    )

    st.markdown("---")
    # DB stats
    try:
        all_tickets = store.list_tickets()
        active_count = sum(1 for t in all_tickets if t.is_active)
        all_audits = store.get_audit_events()
        st.metric("Total Stored Tickets", len(all_tickets))
        st.metric("Active Tickets", active_count)
        st.metric("Audit Trail Events", len(all_audits))
    except Exception:
        pass

    if st.button("🔄 Re-seed Sample Tickets"):
        store.seed_tickets()
        st.success("Tickets re-seeded from data/tickets.json")
        st.rerun()


# ---------------------------------------------------------------------------
# Pre-fill Logic
# ---------------------------------------------------------------------------
default_employee = "Alex Taylor"
default_email = "alex.taylor@veridiancorp.example"
default_request_id = "REQ-CUSTOM"
default_request_text = "I am locked out after 6 password attempts. Can you unlock my account?"

if selected_sample_idx > 0:
    sample_data = sample_requests[selected_sample_idx - 1]
    default_employee = sample_data.get("employee", "")
    default_email = sample_data.get("email", "")
    default_request_id = sample_data.get("request_id", "")
    default_request_text = sample_data.get("request", "")


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------
st.markdown('<div class="main-title">🛡️ Internal Service Agent — IT Support</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">AI IT-Support Orchestrator powered by LangGraph, NVIDIA Nemotron, deterministic policy rules, and SQLite audit persistence.</div>',
    unsafe_allow_html=True,
)

tab_agent, tab_explorer = st.tabs(["🚀 Agent Reviewer Interface", "🗄️ Database & Ticket Queue Explorer"])

with tab_agent:
    # -----------------------------------------------------------------------
    # Request Intake Form
    # -----------------------------------------------------------------------
    with st.container():
        st.subheader("1. Employee Request Intake")
        col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
        with col1:
            input_employee = st.text_input("Employee Name", value=default_employee, key="emp_name")
        with col2:
            input_email = st.text_input("Email Address", value=default_email, key="emp_email")
        with col3:
            input_req_id = st.text_input("Request ID (optional)", value=default_request_id, key="req_id")
        with col4:
            input_ticket_id = st.text_input("Ticket ID (if updating)", value="", placeholder="e.g. TK-1001", key="ticket_id")

        input_request = st.text_area(
            "IT Support Request (Free-text)",
            value=default_request_text,
            height=100,
            key="req_text",
            help="Type the employee's issue or select a benchmark sample from the sidebar.",
        )

        submit_col, _ = st.columns([2, 8])
        with submit_col:
            submit_pressed = st.button("⚡ Process Request", type="primary", use_container_width=True)

    # -----------------------------------------------------------------------
    # Execution & Results
    # -----------------------------------------------------------------------
    if submit_pressed:
        if not input_request.strip():
            st.error("Please enter a support request.")
        else:
            with st.spinner("Processing request through LangGraph pipeline..."):
                # Instantiate orchestrator
                llm = get_llm() if use_llm else None
                orchestrator = AgentOrchestrator(
                    llm=llm,
                    retriever=retriever,
                    policy_engine=policy_engine,
                    store=store,
                    use_llm=use_llm,
                )

                agent_req = AgentRequest(
                    employee=input_employee.strip() or "Employee",
                    email=input_email.strip(),
                    request=input_request.strip(),
                    request_id=input_req_id.strip() or None,
                    ticket_id=input_ticket_id.strip() or None,
                )

                response: AgentResponse = orchestrator.run(agent_req)
                st.session_state["latest_response"] = response

    # Display results if available in session
    if "latest_response" in st.session_state:
        resp: AgentResponse = st.session_state["latest_response"]

        st.markdown("---")
        st.subheader("2. Decision & Agent Outcome")

        # Status badge determination
        status_raw = resp.status.upper()
        if "RESOLVED" in status_raw:
            badge_class = "status-resolved"
            badge_icon = "🟢"
        elif "FOLLOW_UP" in status_raw:
            badge_class = "status-follow-up"
            badge_icon = "🟡"
        else:
            badge_class = "status-escalated"
            badge_icon = "🔴"

        with st.container():
            st.markdown(
                f"""
                <div class="decision-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <div>
                            <span class="status-badge {badge_class}">{badge_icon} {status_raw}</span>
                            <span style="margin-left: 0.75rem; font-weight: 600; color: #475569;">Category:</span>
                            <span style="color: #1E293B; font-weight: 500;">{resp.category}</span>
                        </div>
                        <div>
                            {f'<span style="background: #EFF6FF; color: #1D4ED8; font-weight: 600; padding: 0.3rem 0.75rem; border-radius: 0.375rem; border: 1px solid #BFDBFE;">Destination: {resp.escalation_team}</span>' if resp.escalation_team else ''}
                        </div>
                    </div>
                    <div style="font-weight: 600; color: #334155; margin-top: 0.75rem;">Direct Response to Employee:</div>
                    <div class="response-box">
                        {resp.response.replace(chr(10), '<br>')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -------------------------------------------------------------------
        # Sources Panel & Ticket/Audit Viewers
        # -------------------------------------------------------------------
        col_sources, col_ticket = st.columns([1, 1])

        with col_sources:
            st.subheader("📚 Sources & Policy Precedents")
            if not resp.sources:
                st.info("No specific knowledge base or ticket sources cited.")
            else:
                for src_id in resp.sources:
                    item = retriever.get_by_id(src_id)
                    with st.container():
                        if item:
                            st.markdown(
                                f"""
                                <div class="source-card">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <strong style="color: #1E40AF;">{item.citation} {item.title}</strong>
                                        <span style="font-size: 0.8rem; background: #F1F5F9; padding: 0.2rem 0.5rem; border-radius: 4px;">
                                            Type: {item.source_type.upper()}
                                        </span>
                                    </div>
                                    <div style="font-size: 0.92rem; color: #334155; margin-top: 0.5rem; line-height: 1.5;">
                                        {item.content[:280]}...
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"""
                                <div class="source-card">
                                    <strong>Source ID: {src_id}</strong>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

        with col_ticket:
            st.subheader("🎫 Structured Ticket & Audit Trail")

            # Structured Ticket tab
            ticket_tab, audit_tab = st.tabs(["Structured Ticket (FR-08)", "Audit Log Entry (FR-10)"])

            with ticket_tab:
                if resp.ticket:
                    t = resp.ticket
                    st.markdown(
                        f"""
                        - **Ticket ID:** `{t.get('ticket_id', 'N/A')}`
                        - **Status:** `{t.get('status', 'N/A')}`
                        - **Priority / Risk:** `{t.get('priority_or_risk', 'medium')}`
                        - **Category:** `{t.get('category', 'N/A')}`
                        - **Recommended Action:** {t.get('recommended_action', 'N/A')}
                        - **Escalation Team:** `{t.get('escalation_team') or 'None'}`
                        - **Source IDs:** `{t.get('source_ids', [])}`
                        - **Created At:** `{t.get('created_at', 'N/A')}`
                        """
                    )
                    with st.expander("Raw Ticket JSON"):
                        st.json(resp.ticket)
                else:
                    st.info("No ticket record available.")

            with audit_tab:
                if resp.audit_id:
                    audit_event = store.get_audit_event(resp.audit_id)
                    if audit_event:
                        st.markdown(
                            f"""
                            - **Audit ID:** `{audit_event.audit_id}`
                            - **Timestamp:** `{audit_event.timestamp}`
                            - **Action:** `{audit_event.action}`
                            - **Destination:** `{audit_event.destination or 'None'}`
                            - **Reason:** {audit_event.reason}
                            - **Evidence:** `{audit_event.evidence or 'None'}`
                            - **Tool / Rule:** `{audit_event.agent_tool_action or 'None'}`
                            """
                        )
                        with st.expander("Raw Audit Event JSON"):
                            st.json(audit_event.model_dump())
                    else:
                        st.write(f"Audit ID: `{resp.audit_id}`")
                else:
                    st.info("No audit ID recorded.")


# ---------------------------------------------------------------------------
# Database Explorer Tab
# ---------------------------------------------------------------------------
with tab_explorer:
    st.subheader("SQLite Persistence Explorer (`data/app.db`)")

    col_t_search, col_t_filter = st.columns([3, 1])
    with col_t_search:
        search_query = st.text_input("🔍 Search Tickets", placeholder="Search by employee, summary, category...", key="t_search")
    with col_t_filter:
        active_only = st.checkbox("Active tickets only", value=False)

    if search_query.strip():
        tickets_to_display = store.search_tickets(search_query, active_only=active_only)
    else:
        tickets_to_display = store.list_tickets(active_only=active_only)

    st.write(f"Showing **{len(tickets_to_display)}** tickets:")

    ticket_rows = []
    for t in tickets_to_display:
        ticket_rows.append(
            {
                "Ticket ID": t.ticket_id,
                "Status": t.status,
                "Employee": t.employee,
                "Category": t.category,
                "Summary": t.summary[:60] + ("..." if len(t.summary) > 60 else ""),
                "Escalation Team": t.escalation_team or "—",
                "Created At": t.created_at[:19] if t.created_at else "—",
            }
        )

    if ticket_rows:
        st.dataframe(ticket_rows, use_container_width=True)
    else:
        st.info("No tickets found matching query.")

    st.markdown("---")
    st.subheader("Recent Audit Trail Events")
    audits = store.get_audit_events()
    recent_audits = audits[-20:] if len(audits) > 20 else audits
    recent_audits.reverse()

    audit_rows = []
    for a in recent_audits:
        audit_rows.append(
            {
                "Audit ID": a.audit_id,
                "Timestamp": a.timestamp[:19] if a.timestamp else "—",
                "Ticket ID": a.ticket_id or "—",
                "Action": a.action,
                "Status": a.status,
                "Destination": a.destination or "—",
                "Reason": a.reason[:80] + ("..." if len(a.reason) > 80 else ""),
            }
        )

    if audit_rows:
        st.dataframe(audit_rows, use_container_width=True)
    else:
        st.info("No audit events recorded yet.")
