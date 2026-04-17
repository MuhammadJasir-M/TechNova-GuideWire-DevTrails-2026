"""
Agent 5: Fraud Ring Detective Agent (VERY STRONG)
Investigates DBSCAN clusters, connects patterns across time, explains coordination.
"""

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from backend.agents.base import (
    AgentState, invoke_with_structure, SYSTEM_PREAMBLE, format_context,
)
from backend.services.ring_detector import RingDetector
from backend.ml.ring_model import ring_model


# ─── Pydantic Output Schema ─────────────────────────────────────────────────

class RingInvestigation(BaseModel):
    """Structured output for fraud ring investigation."""
    is_fraud_ring: bool = Field(description="Whether a coordinated fraud ring is confirmed")
    confidence: float = Field(description="Confidence in the determination from 0.0 to 1.0")
    reasoning: str = Field(description="Detailed narrative explaining the investigation findings")
    connection_patterns: list[str] = Field(description="Specific patterns connecting the members")
    members_involved: int = Field(description="Total number of members in the ring")
    recommended_action: str = Field(description="Action to take: FREEZE_ALL, INVESTIGATE_FURTHER, FALSE_ALARM")
    evidence_summary: str = Field(description="Concise evidence summary for the legal/compliance team")
    estimated_fraud_amount: float = Field(description="Estimated total fraudulent amount in rupees")


# ─── LangGraph Nodes ─────────────────────────────────────────────────────────

def load_clusters(state: AgentState) -> dict:
    """Node 1: Load clusters from deterministic clustering model.

    Source-of-truth cluster generation uses backend/ml/ring_model.py (Option A).
    Falls back to services/RingDetector demo clustering on error.
    """
    context = state["context"]

    # If upstream already passed detected rings, use them.
    detected_rings = context.get("detected_rings", [])
    if detected_rings:
        return {"context": context}

    # Otherwise build clusters from claims data.
    claims_data = context.get("raw_claims")
    if not claims_data:
        claims_data = RingDetector._generate_demo_claims()
        context["raw_claims"] = claims_data

    try:
        ml_out = ring_model.fit_predict(claims_data)
        rings = []
        for c in ml_out.get("clusters", []):
            # Convert RingModel cluster into the shape expected by the LLM prompt.
            methods = c.get("detection_methods", [])
            rings.append(
                {
                    "ring_id": f"ML_{c.get('cluster_id', '?')}",
                    "detection_method": "+".join(methods) if methods else "DBSCAN",
                    "member_count": c.get("member_count", 0),
                    "member_worker_ids": c.get("member_ids", []),
                    "center_latitude": c.get("center_latitude"),
                    "center_longitude": c.get("center_longitude"),
                    "radius_meters": c.get("radius_meters"),
                    "shared_signals": {
                        "type": "DBSCAN clustering",
                        "detail": f"methods={methods}, timing_spread={c.get('timing_spread_seconds')}s, ip_subnets={c.get('unique_ip_subnets')}",
                        "home_zones": c.get("home_zones", []),
                    },
                    "severity": c.get("severity", "MEDIUM"),
                    "confidence": c.get("confidence", 0),
                }
            )

        context["detected_rings"] = rings
        context["ring_ml"] = {"summary": {"rings_detected": ml_out.get("rings_detected"), "noise_points": ml_out.get("noise_points")}}
    except Exception:
        # Fallback to existing detector behaviors.
        spatial = RingDetector._detect_spatial_clusters(claims_data)
        timing = RingDetector._detect_timing_sync(claims_data)
        device = RingDetector._detect_device_correlation(claims_data)
        context["detected_rings"] = spatial + timing + device
        context["ring_ml"] = None

    return {"context": context}


def llm_investigate(state: AgentState) -> dict:
    """Node 2: LLM investigates the clusters and explains coordination."""
    context = state["context"]
    rings = context.get("detected_rings", [])

    ring_summaries = []
    total_members = 0
    for ring in rings:
        total_members += ring.get("member_count", 0)
        ring_summaries.append(
            f"- Ring {ring.get('ring_id', '?')}: {ring.get('member_count', 0)} members, "
            f"method: {ring.get('detection_method', '?')}, "
            f"severity: {ring.get('severity', '?')}\n"
            f"  Signals: {ring.get('shared_signals', {}).get('detail', 'N/A')}"
        )

    prompt = f"""You are a Fraud Ring Detective Agent. Analyze these detected clusters 
and determine if they represent coordinated fraud.

## Detected Clusters
{chr(10).join(ring_summaries) if ring_summaries else "No clusters detected."}

## Statistics
- Total Clusters Found: {len(rings)}
- Total Members Across Clusters: {total_members}
- Detection Methods Used: DBSCAN spatial clustering, timing synchronization, IP/device correlation

## Detection Details
For each cluster, analyze:
1. Is the spatial proximity suspicious (e.g., workers from different home zones claiming from same spot)?
2. Is the timing synchronization too precise to be coincidence (claims within 30 seconds)?
3. Are IP addresses correlated (same subnet)?

Provide a detailed investigation narrative. Connect the dots across evidence types.
If this is a fraud ring, estimate the potential fraud amount (assume ₹1,200 avg claim)."""

    result = invoke_with_structure(RingInvestigation, SYSTEM_PREAMBLE, prompt)

    if result is None:
        has_ring = len(rings) > 0
        result = RingInvestigation(
            is_fraud_ring=has_ring,
            confidence=0.85 if has_ring else 0.1,
            reasoning=f"Detected {len(rings)} suspicious clusters with {total_members} total members.",
            connection_patterns=[r.get("detection_method", "unknown") for r in rings],
            members_involved=total_members,
            recommended_action="FREEZE_ALL" if has_ring else "FALSE_ALARM",
            evidence_summary=f"{len(rings)} clusters detected via DBSCAN + timing + IP analysis.",
            estimated_fraud_amount=total_members * 1200 if has_ring else 0,
        )

    return {"result": result.model_dump()}


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("load_clusters", load_clusters)
    builder.add_node("llm_investigate", llm_investigate)
    builder.set_entry_point("load_clusters")
    builder.add_edge("load_clusters", "llm_investigate")
    builder.add_edge("llm_investigate", END)
    return builder.compile()


class RingDetectiveAgent:
    """Fraud Ring Detective — investigates DBSCAN clusters with LLM reasoning."""

    _graph = None

    @classmethod
    def get_graph(cls):
        if cls._graph is None:
            cls._graph = build_graph()
        return cls._graph

    @classmethod
    async def investigate(cls, detected_rings: list[dict] | None = None) -> dict:
        graph = cls.get_graph()
        initial_state = {
            "messages": [],
            "context": {"detected_rings": detected_rings or []},
            "result": {},
        }
        result = await graph.ainvoke(initial_state)
        return result["result"]
