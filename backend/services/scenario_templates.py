"""
GigPulse Sentinel — Scenario Templates

Defines realistic, timed insurance-event scenarios that the
MockDataSimulator cycles through.  Each template is a sequence of
steps with relative delays and event-generation callables.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any

# Zone pool for random selection
ZONE_POOL = [
    ("CHN-VEL-4B", "Chennai", "Velachery"),
    ("CHN-VEL-4A", "Chennai", "Velachery"),
    ("CHN-ANN-2A", "Chennai", "Anna Nagar"),
    ("CHN-TNR-1A", "Chennai", "T. Nagar"),
    ("CHN-ADY-3A", "Chennai", "Adyar"),
    ("CHN-MYL-5A", "Chennai", "Mylapore"),
    ("CHN-SHN-6A", "Chennai", "Sholinganallur"),
    ("BLR-KOR-1A", "Bengaluru", "Koramangala"),
    ("BLR-IND-2A", "Bengaluru", "Indiranagar"),
    ("BLR-WHT-3A", "Bengaluru", "Whitefield"),
    ("MUM-AND-1A", "Mumbai", "Andheri"),
    ("MUM-BAN-2A", "Mumbai", "Bandra"),
    ("MUM-DAD-3A", "Mumbai", "Dadar"),
    ("HYD-HIB-1A", "Hyderabad", "HITEC City"),
    ("DEL-CON-1A", "Delhi", "Connaught Place"),
    ("DEL-SAK-2A", "Delhi", "Saket"),
]

# Mock worker IDs
WORKER_POOL = [
    f"wrk_{i:03d}" for i in range(1, 20)
]


def _pick_zone():
    return random.choice(ZONE_POOL)


def _pick_worker():
    return random.choice(WORKER_POOL)


# ─────────────────── Data Classes ─────────────────────────────────

@dataclass
class ScenarioStep:
    """One timed step inside a scenario."""
    delay_seconds: int       # wait this long before emitting
    event_type: str
    priority: str            # LOW | MEDIUM | HIGH | CRITICAL
    data_fn: Callable[..., dict]  # sync callable returning event data

    def generate_data(self, ctx: dict) -> dict:
        return self.data_fn(ctx)


@dataclass
class ScenarioTemplate:
    """A named multi-step scenario."""
    name: str
    description: str
    steps: list[ScenarioStep]
    weight: float = 1.0      # selection probability weight


# ──────────────────── Helper data generators ──────────────────────

def _heavy_rain_trigger(ctx: dict) -> dict:
    rainfall = round(random.uniform(85, 160), 1)
    ctx["rainfall"] = rainfall
    ctx["zone"] = _pick_zone()
    ctx["worker"] = _pick_worker()
    return {
        "trigger_type": "HEAVY_RAIN",
        "rainfall_mm": rainfall,
        "zone_code": ctx["zone"][0],
        "city": ctx["zone"][1],
        "area": ctx["zone"][2],
        "severity": "CRITICAL" if rainfall > 120 else "HIGH",
        "sources_agreeing": 3,
    }


def _heavy_rain_zone_alert(ctx: dict) -> dict:
    return {
        "zone_code": ctx["zone"][0],
        "city": ctx["zone"][1],
        "alert_level": "RED" if ctx.get("rainfall", 100) > 120 else "ORANGE",
        "message": f"Heavy Rainfall Warning — {ctx['zone'][2]}, {ctx['zone'][1]}",
        "active_riders_affected": random.randint(8, 35),
    }


def _auto_claim_filed(ctx: dict) -> dict:
    amount = round(random.uniform(400, 2200), 0)
    ctx["claim_amount"] = amount
    ctx["claim_id"] = f"clm_{random.randint(10000, 99999)}"
    return {
        "claim_id": ctx["claim_id"],
        "claim_type": ctx.get("trigger_type", "HEAVY_RAIN"),
        "worker_id": ctx["worker"],
        "zone_code": ctx["zone"][0],
        "amount": amount,
        "disruption_hours": round(random.uniform(2, 6), 1),
        "auto_filed": True,
    }


def _investigation_started(ctx: dict) -> dict:
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "method": random.choice(["GPS_VERIFY", "MULTI_SOURCE", "EARNINGS_DNA"]),
        "confidence_score": round(random.uniform(55, 95), 1),
    }


def _investigation_completed(ctx: dict) -> dict:
    confidence = round(random.uniform(65, 98), 1)
    ctx["confidence"] = confidence
    ctx["approved"] = confidence > 50  # almost always approved
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "result": "VERIFIED" if ctx["approved"] else "FLAGGED",
        "confidence_score": confidence,
        "fraud_signals": random.randint(0, 2),
    }


def _claim_approved(ctx: dict) -> dict:
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "amount": ctx.get("claim_amount", 800),
        "zone_code": ctx["zone"][0],
    }


def _claim_rejected(ctx: dict) -> dict:
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "reason": random.choice([
            "GPS mismatch detected",
            "Earnings anomaly detected",
            "Multiple claims from same device",
        ]),
    }


def _payout_initiated(ctx: dict) -> dict:
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "amount": ctx.get("claim_amount", 800),
        "method": "UPI",
        "upi_id": f"worker{ctx['worker'][-3:]}@upi",
    }


def _payout_completed(ctx: dict) -> dict:
    return {
        "claim_id": ctx.get("claim_id", "clm_00000"),
        "worker_id": ctx["worker"],
        "amount": ctx.get("claim_amount", 800),
        "transaction_id": f"UPI_{random.randint(100000000, 999999999)}",
        "method": "UPI",
    }


def _heat_aqi_trigger(ctx: dict) -> dict:
    temp = round(random.uniform(43, 48), 1)
    aqi = random.randint(410, 500)
    ctx["temperature"] = temp
    ctx["aqi"] = aqi
    ctx["zone"] = _pick_zone()
    ctx["worker"] = _pick_worker()
    ctx["trigger_type"] = "HEAT"
    return {
        "trigger_type": "COMPOUND_HEAT_AQI",
        "temperature_c": temp,
        "aqi": aqi,
        "zone_code": ctx["zone"][0],
        "city": ctx["zone"][1],
        "severity": "CRITICAL",
        "sources_agreeing": 3,
    }


def _fraud_ring_detected(ctx: dict) -> dict:
    ctx["zone"] = _pick_zone()
    members = random.sample(WORKER_POOL, k=random.randint(3, 5))
    ctx["worker"] = members[0]
    return {
        "ring_id": f"ring_{random.randint(1000, 9999)}",
        "member_count": len(members),
        "member_ids": members,
        "zone_code": ctx["zone"][0],
        "detection_method": random.choice([
            "GPS_CLUSTERING", "DEVICE_FINGERPRINT", "TIMING_CORRELATION",
        ]),
        "shared_signals": {
            "same_wifi": random.random() < 0.6,
            "gps_overlap_pct": round(random.uniform(70, 95), 1),
        },
        "frozen_amount": round(random.uniform(3000, 12000), 0),
    }


def _new_worker_event(ctx: dict) -> dict:
    ctx["zone"] = _pick_zone()
    ctx["worker"] = f"wrk_{random.randint(100, 999)}"
    return {
        "worker_id": ctx["worker"],
        "zone_code": ctx["zone"][0],
        "city": ctx["zone"][1],
        "platform": random.choice(["zomato", "swiggy"]),
        "event": "REGISTRATION_COMPLETE",
    }


def _normal_ops_trigger(ctx: dict) -> dict:
    ctx["zone"] = _pick_zone()
    ctx["worker"] = _pick_worker()
    ctx["trigger_type"] = "HEAVY_RAIN"
    rainfall = round(random.uniform(30, 70), 1)
    ctx["rainfall"] = rainfall
    return {
        "zone_code": ctx["zone"][0],
        "city": ctx["zone"][1],
        "weather": "Partly cloudy",
        "rainfall_mm": rainfall,
        "temperature_c": round(random.uniform(28, 36), 1),
        "aqi": random.randint(50, 150),
        "status": "NORMAL",
    }


# ──────────────────── Template Definitions ────────────────────────

HEAVY_RAIN_SCENARIO = ScenarioTemplate(
    name="Heavy Rain Event",
    description="Monsoon downpour triggers claims in a high-risk zone",
    weight=3.0,
    steps=[
        ScenarioStep(0, "TRIGGER_DETECTED", "HIGH", _heavy_rain_trigger),
        ScenarioStep(3, "ZONE_ALERT", "HIGH", _heavy_rain_zone_alert),
        ScenarioStep(6, "CLAIM_AUTO_FILED", "MEDIUM", _auto_claim_filed),
        ScenarioStep(10, "INVESTIGATION_STARTED", "MEDIUM", _investigation_started),
        ScenarioStep(15, "INVESTIGATION_COMPLETED", "MEDIUM", _investigation_completed),
        ScenarioStep(18, "CLAIM_APPROVED", "HIGH", _claim_approved),
        ScenarioStep(22, "PAYOUT_INITIATED", "HIGH", _payout_initiated),
        ScenarioStep(28, "PAYOUT_COMPLETED", "HIGH", _payout_completed),
    ],
)

HEAT_AQI_SCENARIO = ScenarioTemplate(
    name="Heat + AQI Compound Event",
    description="Extreme heat combined with hazardous air quality",
    weight=2.0,
    steps=[
        ScenarioStep(0, "TRIGGER_DETECTED", "CRITICAL", _heat_aqi_trigger),
        ScenarioStep(3, "ZONE_ALERT", "CRITICAL", _heavy_rain_zone_alert),
        ScenarioStep(7, "CLAIM_AUTO_FILED", "HIGH", _auto_claim_filed),
        ScenarioStep(12, "INVESTIGATION_STARTED", "MEDIUM", _investigation_started),
        ScenarioStep(18, "INVESTIGATION_COMPLETED", "MEDIUM", _investigation_completed),
        ScenarioStep(22, "CLAIM_APPROVED", "HIGH", _claim_approved),
        ScenarioStep(25, "PAYOUT_INITIATED", "HIGH", _payout_initiated),
        ScenarioStep(30, "PAYOUT_COMPLETED", "MEDIUM", _payout_completed),
    ],
)

FRAUD_RING_SCENARIO = ScenarioTemplate(
    name="Fraud Ring Detection",
    description="AI detects coordinated fraudulent claims from multiple workers",
    weight=1.0,
    steps=[
        ScenarioStep(0, "FRAUD_RING_DETECTED", "CRITICAL", _fraud_ring_detected),
        ScenarioStep(5, "INVESTIGATION_STARTED", "HIGH", _investigation_started),
        ScenarioStep(15, "CLAIM_REJECTED", "HIGH", _claim_rejected),
    ],
)

NEW_WORKER_SCENARIO = ScenarioTemplate(
    name="New Worker Lifecycle",
    description="A new gig worker registers and gets their first policy",
    weight=1.5,
    steps=[
        ScenarioStep(0, "TRIGGER_DETECTED", "LOW", _new_worker_event),
        ScenarioStep(5, "ZONE_ALERT", "LOW", _normal_ops_trigger),
    ],
)

NORMAL_OPS_SCENARIO = ScenarioTemplate(
    name="Normal Operations",
    description="Regular monitoring — no significant events",
    weight=2.5,
    steps=[
        ScenarioStep(0, "ZONE_ALERT", "LOW", _normal_ops_trigger),
        ScenarioStep(8, "TRIGGER_DETECTED", "LOW", _normal_ops_trigger),
    ],
)

# Master list
ALL_SCENARIOS: list[ScenarioTemplate] = [
    HEAVY_RAIN_SCENARIO,
    HEAT_AQI_SCENARIO,
    FRAUD_RING_SCENARIO,
    NEW_WORKER_SCENARIO,
    NORMAL_OPS_SCENARIO,
]


def pick_scenario() -> ScenarioTemplate:
    """Weighted-random selection of a scenario template."""
    weights = [s.weight for s in ALL_SCENARIOS]
    return random.choices(ALL_SCENARIOS, weights=weights, k=1)[0]
