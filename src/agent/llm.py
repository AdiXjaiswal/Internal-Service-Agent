"""LLM integration and prompt definitions for the Internal Service Agent.

Connects to NVIDIA Nemotron via langchain-openai ChatOpenAI, with structured
prompts for:
1. Issue classification and entity extraction
2. Policy-grounded response synthesis
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..policy.models import Decision, PolicyVerdict
from ..retrieval.models import RetrievalResult

# Ensure .env is loaded
load_dotenv()

DEFAULT_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
DEFAULT_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_API_KEY = os.getenv("NVIDIA_API_KEY", "")


def get_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> BaseChatModel:
    """Instantiate a ChatOpenAI client configured for NVIDIA Nemotron endpoint."""
    key = api_key or DEFAULT_API_KEY or os.getenv("OPENAI_API_KEY", "")
    url = base_url or DEFAULT_BASE_URL
    mod = model or DEFAULT_MODEL

    return ChatOpenAI(
        model=mod,
        api_key=key,
        base_url=url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Extraction & Classification
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You are an IT Support request analyzer.
Analyze the employee's request and extract structured information in strictly valid JSON format.
Do NOT include markdown formatting or backticks around the JSON. Output only raw JSON.

Output fields:
- "category": One of:
    "Password/Account Access", "VPN", "Laptop/Hardware", "Software Installation",
    "Printer", "Email/Mailbox", "Guest Wi-Fi", "Finance/Expense Software",
    "Security Incident", "Home-Office Equipment", "Admin Access", "Other/Unclear"
- "summary": A concise 1-sentence summary of the user's issue.
- "search_query": Concise keywords to search the IT Knowledge Base (e.g. "locked out password", "contractor vpn", "non-catalog software").
- "employee_type": "employee" | "contractor" | null
- "is_catalog_software": true (if standard/approved catalog) | false (if non-catalog/unapproved/external tool) | null
- "laptop_age_years": number | null (age of device in years)
- "hardware_failure_verified": true | false | null
- "quota_gb_requested": number | null (mailbox quota size requested)
- "is_guest_wifi": true | false | null
- "expense_account_exists": true | false | null
- "wfh_days_per_week": number | null (remote work days per week)
- "priority_or_risk": "low" | "medium" | "high" | "critical" (phishing/security must be high or critical)
"""


def extract_entities_with_fallback(
    request_text: str, llm: Optional[BaseChatModel] = None
) -> dict[str, Any]:
    """Extract classification facts using LLM, with deterministic regex fallback."""
    entities: dict[str, Any] = {
        "category": "Other/Unclear",
        "summary": request_text.strip(),
        "search_query": request_text.strip(),
        "employee_type": None,
        "is_catalog_software": None,
        "laptop_age_years": None,
        "hardware_failure_verified": None,
        "quota_gb_requested": None,
        "is_guest_wifi": None,
        "expense_account_exists": None,
        "wfh_days_per_week": None,
        "priority_or_risk": "medium",
    }

    # Deterministic heuristics for extraction (applied first or as baseline)
    lower = request_text.lower()

    if any(w in lower for w in ("phish", "suspicious email", "malware", "compromised", "ransomware", "security incident")):
        entities["category"] = "Security Incident"
        entities["search_query"] = "security incident phishing malware"
        entities["priority_or_risk"] = "critical"
    elif any(w in lower for w in ("wifi", "wi-fi", "guest code", "visitor internet")):
        entities["category"] = "Guest Wi-Fi"
        entities["is_guest_wifi"] = True
        entities["search_query"] = "guest wifi access"
        entities["priority_or_risk"] = "low"
    elif any(w in lower for w in ("password", "locked out", "lockout", "reset password", "login attempts")):
        entities["category"] = "Password/Account Access"
        entities["search_query"] = "password reset account lockout"
    elif "vpn" in lower:
        entities["category"] = "VPN"
        entities["search_query"] = "vpn access remote connection"
        if "contractor" in lower:
            entities["employee_type"] = "contractor"
        elif "full-time" in lower or "employee" in lower:
            entities["employee_type"] = "employee"
    elif any(w in lower for w in ("software", "install", "tool", "license", "application")):
        entities["category"] = "Software Installation"
        entities["search_query"] = "software installation approved catalog"
        if any(w in lower for w in ("not in the catalog", "not in catalog", "non-catalog", "unapproved", "external tool")):
            entities["is_catalog_software"] = False
        elif any(w in lower for w in ("catalog", "approved software", "self-service portal", "standard tool")):
            entities["is_catalog_software"] = True
    elif any(w in lower for w in ("laptop", "macbook", "computer", "hardware replacement")):
        entities["category"] = "Laptop/Hardware"
        entities["search_query"] = "laptop replacement hardware refresh"
        age_match = re.search(r"(\d+(\.\d+)?)\s*(?:years?|yrs?)\s*old", lower)
        if age_match:
            try:
                entities["laptop_age_years"] = float(age_match.group(1))
            except ValueError:
                pass
        if "hardware failure" in lower or "broken" in lower or "motherboard" in lower or "defective" in lower:
            entities["hardware_failure_verified"] = True
    elif any(w in lower for w in ("mailbox", "quota", "outlook storage", "exchange quota")):
        entities["category"] = "Email/Mailbox"
        entities["search_query"] = "mailbox storage quota increase"
        quota_match = re.search(r"(\d+)\s*(?:gb|gigabytes)", lower)
        if quota_match:
            try:
                entities["quota_gb_requested"] = float(quota_match.group(1))
            except ValueError:
                pass
    elif any(w in lower for w in ("wfh", "work from home", "home office", "monitor", "desk", "chair")):
        entities["category"] = "Home-Office Equipment"
        entities["search_query"] = "work from home equipment allowance"
        days_match = re.search(r"(\d+)\s*(?:days?|days\s*/\s*week)", lower)
        if days_match:
            try:
                entities["wfh_days_per_week"] = float(days_match.group(1))
            except ValueError:
                pass
    elif any(w in lower for w in ("expense", "concur", "expensify", "reimbursement")):
        entities["category"] = "Finance/Expense Software"
        entities["search_query"] = "expense software access finance"
        if "new account" in lower or "create account" in lower or "don't have an account" in lower:
            entities["expense_account_exists"] = False
        elif "existing" in lower or "login issue" in lower or "reset" in lower:
            entities["expense_account_exists"] = True
    elif any(w in lower for w in ("printer", "print", "jam", "toner")):
        entities["category"] = "Printer"
        entities["search_query"] = "printer troubleshooting queue"

    # If LLM is provided and has an API key, invoke for richer extraction
    if llm is not None:
        try:
            messages = [
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=f"Employee request: {request_text}"),
            ]
            response = llm.invoke(messages)
            raw = response.content.strip()
            # Clean markdown fences if any
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if v is not None and k in entities:
                        entities[k] = v
        except Exception:
            # Silently fall back to heuristic extraction on error
            pass

    return entities


# ---------------------------------------------------------------------------
# Response Generation
# ---------------------------------------------------------------------------

RESPONSE_SYSTEM_PROMPT = """You are the Internal IT Service Agent.
Your goal is to provide a clear, professional, helpful response to the employee.

CRITICAL RULES:
1. Ground your response STRICTLY in the provided Knowledge Base policies and Policy Verdict.
2. Do NOT invent policies or make promises beyond what the policy specifies.
3. Cite the relevant policy sources using their IDs (e.g. [KB-01], [KB-07]).
4. Conform strictly to the required outcome:
   - If status is RESOLVED: Give complete, step-by-step resolution instructions.
   - If status is ESCALATED: Clearly inform the employee that their request has been routed to the specified team ({escalation_team}). Provide the policy reason, expected timeframe if mentioned in policy (e.g. 3-5 business days for software), and any important instructions (e.g. for security incidents, warn them never to forward suspicious emails).
   - If status is FOLLOW_UP_REQUIRED: Politely ask the specific clarifying question required.
5. Keep your response concise, empathetic, and professional.
"""


def generate_agent_response(
    employee: str,
    request_text: str,
    verdict: PolicyVerdict,
    sources: list[RetrievalResult],
    llm: Optional[BaseChatModel] = None,
) -> str:
    """Generate grounded customer response based on verdict and KB sources."""
    # Deterministic fallback response if LLM is not provided or fails
    kb_citations = [s.citation for s in sources if s.is_kb]
    source_str = " ".join(kb_citations) if kb_citations else f"[{verdict.source_kb_id}]" if verdict.source_kb_id else ""

    if verdict.decision == Decision.FOLLOW_UP_REQUIRED:
        default_resp = verdict.follow_up_question or (
            "Could you please provide additional details regarding your request?"
        )
    elif verdict.decision == Decision.ESCALATED:
        team = verdict.escalation_team or "IT Support"
        default_resp = (
            f"Hello {employee}, your request has been escalated to the {team} team for review. "
            f"Reason: {verdict.reason} {source_str}".strip()
        )
        if "KB-09" in verdict.source_kb_id or "Security" in team:
            default_resp += (
                " Please do NOT forward any suspicious emails to other colleagues. "
                "The Security team will follow up directly."
            )
        elif "KB-04" in verdict.source_kb_id or "Software" in verdict.rule_id:
            default_resp += " Software security reviews typically take 3–5 business days."
    else:  # Decision.RESOLVED
        default_resp = (
            f"Hello {employee}, your request has been processed. "
            f"{verdict.reason} {source_str}".strip()
        )

    if llm is None:
        return default_resp

    try:
        # Build prompt context
        kb_text = "\n\n".join(
            f"Source {s.citation} ({s.title}):\n{s.content}"
            for s in sources if s.is_kb
        )

        user_content = f"""Employee: {employee}
Original Request: {request_text}

Decision Outcome: {verdict.decision.value}
Reason: {verdict.reason}
Escalation Team: {verdict.escalation_team or 'None'}
Follow-up Question (if required): {verdict.follow_up_question or 'None'}

Retrieved Knowledge Base Policies:
{kb_text or 'No specific KB content'}

Please write the response to the employee following the system prompt rules."""

        messages = [
            SystemMessage(
                content=RESPONSE_SYSTEM_PROMPT.format(
                    escalation_team=verdict.escalation_team or "the responsible team"
                )
            ),
            HumanMessage(content=user_content),
        ]
        response = llm.invoke(messages)
        res_text = response.content.strip()
        return res_text if res_text else default_resp
    except Exception:
        return default_resp
