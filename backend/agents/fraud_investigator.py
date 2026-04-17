"""
Agent 1: Fraud Investigation Agent (HIGH IMPACT)
Reads all signals, explains suspicion, decides: approve / reject / escalate.
"""

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from backend.agents.base import (
    AgentState, invoke_with_structure, SYSTEM_PREAMBLE, format_context,
)
from backend.services.fraud_detector import FraudDetector
from backend.ml.fraud_model import fraud_model


def _base_decision_from_fraud_score(fraud_score: float) -> str:
    """Deterministic mapping from ML fraud_score (0-100) to a base decision.

    LLM may later escalate to ESCALATE, but should not downgrade risk.
    """

    if fraud_score < 30:
        return "APPROVE"
    if fraud_score <= 60:
        return "ESCALATE"
    return "REJECT"


def _base_confidence_from_fraud_score(fraud_score: float) -> float:
    """Heuristic confidence (0-1) based on distance from thresholds."""

    # Near the boundary -> lower confidence, far away -> higher confidence.
    if fraud_score < 30:
        # 0..30 => 0.5..1.0
        return max(0.5, min(1.0, 0.5 + (30 - fraud_score) / 60))
    if fraud_score <= 60:
        return 0.55
    # 60..100 => 0.5..1.0
    return max(0.5, min(1.0, 0.5 + (fraud_score - 60) / 80))


def _risk_level_from_fraud_score(fraud_score: float) -> str:
    if fraud_score < 25:
        return "LOW"
    if fraud_score < 50:
        return "MEDIUM"
    if fraud_score < 75:
        return "HIGH"
    return "CRITICAL"


# ─── Pydantic Output Schema ─────────────────────────────────────────────────

class FraudInvestigation(BaseModel):
    """Structured output for fraud investigation."""
    decision: str = Field(description="One of: APPROVE, REJECT, ESCALATE")
    reasoning: str = Field(description="Detailed reasoning explaining the decision step by step")
    suspicious_signals: list[str] = Field(description="List of suspicious signal names detected")
    confidence: float = Field(description="Confidence in the decision from 0.0 to 1.0")
    explanation_for_worker: str = Field(description="Simple, friendly explanation for the worker in plain language")
    risk_level: str = Field(description="Overall risk level: LOW, MEDIUM, HIGH, CRITICAL")


# ─── LangGraph Nodes ─────────────────────────────────────────────────────────

def gather_signals(state: AgentState) -> dict:
    """Node 1: Gather fraud signals and compute ML score.

    Source-of-truth numeric scoring comes from backend/ml/fraud_model.py.
    Rule-based signals are retained as supporting evidence and fallback.
    """
    context = state["context"]
    worker_data = context.get("worker_data", {})
    location_data = context.get("location_data", {})
    device_data = context.get("device_data", {})
    platform_data = context.get("platform_data", {})

    # ML score (deterministic). This is the source-of-truth for fraud_score.
    fraud_ml = None
    try:
        features = {
            "max_velocity": float(location_data.get("max_velocity_kmh", location_data.get("max_velocity", 0)) or 0),
            "days_in_zone": int(location_data.get("days_in_zone_30d", location_data.get("days_in_zone", 30)) or 30),
            "is_rooted": bool(device_data.get("is_rooted", False)),
            "mock_gps": bool(device_data.get("mock_gps_detected", device_data.get("mock_gps", False))),
            "is_emulator": bool(device_data.get("is_emulator", False)),
            "altitude_variance": float(location_data.get("altitude_variance", 5) or 5),
            "gps_cell_distance": float(location_data.get("gps_cell_distance_km", location_data.get("gps_cell_distance", 0)) or 0),
            "motion_level": float(device_data.get("motion_level", 0.5) or 0.5),
            "order_count": int(platform_data.get("order_count_today", platform_data.get("order_count", 0)) or 0),
        }
        fraud_ml = fraud_model.compute_anomaly_score(features)
    except Exception:
        fraud_ml = None

    if fraud_ml is not None:
        ml_score = float(fraud_ml.get("fraud_score", 0) or 0)
        context["fraud_ml"] = fraud_ml
        context["fraud_score"] = ml_score
        context["base_decision"] = _base_decision_from_fraud_score(ml_score)
        context["base_confidence"] = _base_confidence_from_fraud_score(ml_score)
        context["base_risk_level"] = _risk_level_from_fraud_score(ml_score)
    else:
        context["fraud_ml"] = None

    # Supporting: run existing 7-signal fraud analysis for evidence narrative.
    try:
        analysis = FraudDetector.analyze_claim(
            worker_data=worker_data,
            location_data=location_data,
            device_data=device_data,
            platform_data=platform_data,
        )
        context["fraud_analysis"] = analysis
    except Exception:
        context["fraud_analysis"] = {}

    return {"context": context}


def llm_reason(state: AgentState) -> dict:
    """Node 2: LLM explains the computed decision.

    Policy: LLM may only escalate to ESCALATE (human review). It may not
    downgrade risk or change ML-produced numeric scores.
    """
    context = state["context"]
    analysis = context.get("fraud_analysis", {})
    fraud_ml = context.get("fraud_ml") or {}

    # Base decision comes from ML score if available, otherwise from rule-based tier.
    base_decision = context.get("base_decision")
    base_confidence = context.get("base_confidence")
    base_risk_level = context.get("base_risk_level")
    fraud_score = context.get("fraud_score")

    if base_decision is None:
        tier = analysis.get("fraud_tier", "GREEN")
        fraud_score = analysis.get("fraud_score", 0)
        base_decision = "APPROVE" if tier == "GREEN" else ("ESCALATE" if tier == "AMBER" else "REJECT")
        base_confidence = max(0.0, min(1.0, float(analysis.get("confidence_score", 50) or 50) / 100))
        base_risk_level = "LOW" if tier == "GREEN" else ("MEDIUM" if tier == "AMBER" else "HIGH")

    ml_signal_scores = fraud_ml.get("signal_scores", {}) if isinstance(fraud_ml, dict) else {}
    ml_flagged = []
    if isinstance(ml_signal_scores, dict):
        # Treat >0.5 anomaly score as flagged.
        ml_flagged = [k for (k, v) in ml_signal_scores.items() if isinstance(v, (int, float)) and float(v) > 0.5]

    prompt = f"""You are a Fraud Investigation Agent. Analyze the following claim signals 
and provide an explainable investigation report.

Important policy:
- The base decision is already computed from a deterministic fraud score.
- You may ONLY change the decision to ESCALATE (human review) if the evidence is ambiguous.
- Do NOT change the fraud score or invent any numbers.

## Claim Context
- Worker ID: {context.get('worker_id', 'unknown')}
- Claim Type: {context.get('claim_type', 'unknown')}
- Zone Code: {context.get('zone_code', 'unknown')}
- Disruption Hours: {context.get('disruption_hours', 0)}

## ML Fraud Score (Source Of Truth)
- Fraud Score: {fraud_score}/100
- Base Decision: {base_decision}
- Base Confidence: {base_confidence}
- Base Risk Level: {base_risk_level}
- ML Flagged Signals: {ml_flagged}

## ML Signal Scores (0..1 anomaly indicators)
{format_context(ml_signal_scores) if ml_signal_scores else 'No ML signal scores available.'}

## Supporting Rule-Based Analysis (7-Signal)
- Overall Fraud Score (rule-based): {analysis.get('fraud_score', 0)}/100
- Current Tier: {analysis.get('fraud_tier', 'unknown')}
- Confidence Score: {analysis.get('confidence_score', 0)}%

## Individual Signal Breakdown
{format_context(analysis.get('signals', {}))}

## Flagged Signals
{analysis.get('flagged_signals', [])}

Based on ALL signals, explain why the base decision was reached.
If you think a human review is required, set decision=ESCALATE and explain exactly what is ambiguous.
Be specific about which signals are concerning and why."""

    result = invoke_with_structure(FraudInvestigation, SYSTEM_PREAMBLE, prompt)

    if result is None:
        # Fallback: deterministic response.
        result = FraudInvestigation(
            decision=base_decision,
            reasoning=analysis.get("recommendation", "Decision computed from deterministic fraud score"),
            suspicious_signals=ml_flagged or analysis.get("flagged_signals", []),
            confidence=float(base_confidence),
            explanation_for_worker="Your claim is being processed." if base_decision == "APPROVE" else "Your claim requires additional verification.",
            risk_level=base_risk_level,
        )

    # Enforce policy: LLM can only escalate, never change the numeric basis.
    final_decision = base_decision
    try:
        if str(getattr(result, "decision", "")).upper().strip() == "ESCALATE":
            final_decision = "ESCALATE"
    except Exception:
        pass

    try:
        # Rewrite fields to reflect the deterministic basis.
        result.decision = final_decision
        result.confidence = float(base_confidence)
        result.risk_level = base_risk_level
        # Ensure suspicious_signals includes ML flagged signals.
        if ml_flagged and (not result.suspicious_signals):
            result.suspicious_signals = ml_flagged
    except Exception:
        pass

    return {"result": result.model_dump()}


# ─── Graph Builder ───────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("gather_signals", gather_signals)
    builder.add_node("llm_reason", llm_reason)
    builder.set_entry_point("gather_signals")
    builder.add_edge("gather_signals", "llm_reason")
    builder.add_edge("llm_reason", END)
    return builder.compile()


# ─── Public API ──────────────────────────────────────────────────────────────

class FraudInvestigatorAgent:
    """Fraud Investigation Agent — explains why something is suspicious and decides."""

    _graph = None

    @classmethod
    def get_graph(cls):
        if cls._graph is None:
            cls._graph = build_graph()
        return cls._graph

    @classmethod
    async def investigate(
        cls,
        worker_id: str,
        claim_type: str = "HEAVY_RAIN",
        zone_code: str = "CHN-VEL-4B",
        disruption_hours: float = 4.0,
        location_data: dict | None = None,
        device_data: dict | None = None,
        platform_data: dict | None = None,
    ) -> dict:
        """Run a full fraud investigation on a claim."""
        graph = cls.get_graph()

        initial_state = {
            "messages": [],
            "context": {
                "worker_id": worker_id,
                "claim_type": claim_type,
                "zone_code": zone_code,
                "disruption_hours": disruption_hours,
                "worker_data": {"tenure_weeks": 24},
                "location_data": location_data or {
                    "velocity_kmh": 25, "max_velocity_kmh": 45,
                    "zone_match_30d": True, "days_in_zone_30d": 22,
                    "altitude_variance": 8.5, "gps_cell_distance_km": 0.8,
                },
                "device_data": device_data or {
                    "is_rooted": False, "mock_gps_detected": False,
                    "is_emulator": False, "motion_level": 0.72,
                },
                "platform_data": platform_data or {
                    "has_orders_in_zone": True, "order_count_today": 8,
                },
            },
            "result": {},
        }

        result = await graph.ainvoke(initial_state)
        return result["result"]
