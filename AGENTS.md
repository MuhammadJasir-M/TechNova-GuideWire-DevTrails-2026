# 🤖 GigPulse Sentinel Agent API Reference

Complete documentation for all seven AI agents in the GigPulse Sentinel system.

## Table of Contents

1. [Agent Architecture](#agent-architecture)
2. [Agent 1: Fraud Investigator](#agent-1-fraud-investigator)
3. [Agent 2: Smart Trigger Validator](#agent-2-smart-trigger-validator)
4. [Agent 3: Earnings Intelligence](#agent-3-earnings-intelligence)
5. [Agent 4: Risk Pricing](#agent-4-risk-pricing)
6. [Agent 5: Fraud Ring Detective](#agent-5-fraud-ring-detective)
7. [Agent 6: Worker Assistant](#agent-6-worker-assistant)
8. [Agent 7: Appeal Handler](#agent-7-appeal-handler)
9. [Authentication & Error Handling](#authentication--error-handling)
10. [Testing Agents](#testing-agents)

---

## Agent Architecture

### Two-Node Pattern

All agents follow a consistent two-node architecture:

```
Request
   │
   ├─→ [Gather Node]
   │   - Load data from database
   │   - Call deterministic ML models
   │   - Build feature vectors
   │   - Run rule-based logic
   │
   └─→ [LLM Node]
       - LLM reasoning with context
       - Structured JSON response
       - Safety guardrails + enforcement
       - Human-readable explanation
```

### Base Agent Class

All agents inherit from [backend/agents/base.py](backend/agents/base.py):

```python
class BaseAgent:
    """Base class for all AI agents"""
    
    async def execute(self, context: dict) -> dict:
        """Main execution method"""
        pass
    
    @node("gather")
    async def gather_node(self, context: dict) -> dict:
        """Data gathering phase"""
        pass
    
    @node("reason")
    async def reason_node(self, context: dict) -> dict:
        """LLM reasoning phase"""
        pass
```

The `@node` decorator handles error handling, logging, and state management.

### Response Schema

Every agent returns:

```json
{
  "agent_id": "fraud_investigator_v1",
  "execution_time_ms": 1200,
  "nodes_executed": ["gather", "reason"],
  "status": "success",
  "result": {
    "decision": "ESCALATE",
    "confidence": 0.85,
    "explanation": "...",
    "metadata": {}
  },
  "error": null
}
```

---

## Agent 1: Fraud Investigator

### Endpoint

```
POST /api/agents/investigate/{claim_id}
Authorization: Bearer <admin_token>
```

### Purpose

Evaluates fraud risk for an insurance claim and returns a decision (APPROVE/ESCALATE/REJECT) with detailed reasoning.

### File

[backend/agents/fraud_investigator.py](backend/agents/fraud_investigator.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `claim_id` | string | ✅ | UUID of the claim to investigate |

### Request Example

```bash
curl -X POST http://localhost:8000/api/agents/investigate/claim-uuid-here \
  -H "Authorization: Bearer admin_token_here" \
  -H "Content-Type: application/json"
```

### Response Schema

```json
{
  "agent_id": "fraud_investigator_v1",
  "status": "success",
  "result": {
    "fraud_score": 42,
    "base_decision": "ESCALATE",
    "ml_signal_analysis": {
      "movement_velocity": { "score": 15, "flag": false },
      "location_history_match": { "score": 8, "flag": false },
      "device_fingerprint": { "score": 12, "flag": true },
      "gps_altitude_consistency": { "score": 3, "flag": false },
      "cell_tower_gps_match": { "score": 2, "flag": false },
      "accelerometer_gyroscope": { "score": 0, "flag": false },
      "platform_order_logs": { "score": 2, "flag": false }
    },
    "rule_based_evidence": "Device flagged for mock GPS app. However, location history matches claimed zone for past 30 days.",
    "reasoning": "Fraud score of 42 places this in ESCALATE tier. Device anomaly detected, but contextual evidence suggests genuine claim. Recommend manual verification with one-tap confirm.",
    "recommended_action": "SOFT_VERIFY",
    "confidence": 0.78,
    "trust_score_impact": -5,
    "suggested_next_steps": [
      "Send one-tap confirmation request",
      "Cross-check with order logs from Zomato",
      "If confirmed, auto-approve. If not, reject."
    ]
  },
  "execution_time_ms": 1240,
  "nodes_executed": ["gather_signals", "llm_reason"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Fraud investigation completed successfully |
| 400 | Invalid claim_id or missing required data |
| 401 | Unauthorized (admin token required) |
| 404 | Claim not found |
| 500 | Agent execution error |

### Decision Rules

| Fraud Score | Base Decision | Payout Action |
|-------------|---------------|---------------|
| 0–30 | APPROVE | Instant payout |
| 31–60 | ESCALATE | Soft verification |
| 61–100 | REJECT | Hold for review |

### ML Model Used

- **Model:** Isolation Forest (Scikit-learn)
- **File:** [backend/ml/fraud_model.py](backend/ml/fraud_model.py)
- **Features:** 7 signals (movement, location, device, GPS, accelerometer, order logs)
- **Deterministic:** Yes (score is immutable by LLM)

### Enforcement Rules

✋ **Safety Guardrails:**
- LLM **cannot modify** the numeric fraud_score
- LLM **cannot downgrade** risk level
- LLM may only suggest ESCALATE (human review) as override
- If LLM requests APPROVE on high fraud_score → Code enforces ESCALATE

---

## Agent 2: Smart Trigger Validator

### Endpoint

```
POST /api/agents/validate-trigger/{trigger_id}
Authorization: Bearer <admin_token>
```

### Purpose

Validates whether a parametric trigger event (flood, heatwave, etc.) is trustworthy based on data source agreement.

### File

[backend/agents/trigger_validator.py](backend/agents/trigger_validator.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `trigger_id` | string | ✅ | UUID of the trigger event to validate |

### Request Example

```bash
curl -X POST http://localhost:8000/api/agents/validate-trigger/trigger-uuid \
  -H "Authorization: Bearer admin_token_here"
```

### Response Schema

```json
{
  "agent_id": "trigger_validator_v1",
  "status": "success",
  "result": {
    "trigger_type": "HEAVY_RAINFALL",
    "is_valid": true,
    "recommendation": "FIRE",
    "sources_agreement": 3,
    "source_breakdown": {
      "primary_source": {
        "name": "OpenWeatherMap API",
        "data": "85mm/hr rainfall detected",
        "confidence": 0.94,
        "timestamp": "2026-04-17T14:30:00Z"
      },
      "secondary_source": {
        "name": "IMD Alert API",
        "data": "Red alert issued for Velachery zone",
        "confidence": 0.98,
        "timestamp": "2026-04-17T14:15:00Z"
      },
      "tertiary_source": {
        "name": "Zomato Platform API",
        "data": "Orders suspended in zone 4B for 2.5 hours",
        "confidence": 0.87,
        "timestamp": "2026-04-17T14:45:00Z"
      }
    },
    "source_conflicts": [],
    "reasoning": "All three independent data sources confirm heavy rainfall event. High confidence trigger. No conflicting data. Recommend immediate FIRE decision to process payouts.",
    "coverage_recommendations": {
      "affected_worker_count_estimated": 287,
      "estimated_total_payout": "₹85,000–₹120,000",
      "liquidity_check": "✅ Sufficient"
    },
    "confidence": 0.95
  },
  "execution_time_ms": 890,
  "nodes_executed": ["gather_sources", "llm_evaluate"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Trigger validation completed |
| 400 | Invalid trigger_id or missing data |
| 401 | Unauthorized |
| 404 | Trigger not found |
| 500 | Agent execution error |

### Recommendation Mapping

| Sources Agreeing | Recommendation | Payout Action |
|------------------|----------------|---------------|
| 3 | FIRE | Auto-approve all claims |
| 2 | SOFT_VERIFY | Minor delay, cross-check |
| ≤1 | DISMISS / HOLD | Manual review required |

### Fallback Logic

If LLM fails:
```
is_valid = sources_agreeing >= 2
├─ True → FIRE
└─ False → HOLD
```

### ML Model Used

- **Model:** None (rule-based + LLM)
- **Logic:** Source agreement matrix + conflict analysis

---

## Agent 3: Earnings Intelligence

### Endpoint

```
GET /api/agents/earnings-insight/{worker_id}
Authorization: Bearer <worker_token>
```

### Purpose

Recommends an adjusted payout based on the worker's earnings patterns and time-of-day disruption loss.

### File

[backend/agents/earnings_intelligence.py](backend/agents/earnings_intelligence.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `worker_id` | string | ✅ | UUID of worker requesting insight |
| `claim_amount` | number | ✅ | Base claim amount (₹) |
| `disruption_hours` | number | ✅ | Duration of disruption (hours) |
| `disruption_day_hour` | string | ✅ | ISO timestamp of disruption start |

### Request Example

```bash
curl -X GET "http://localhost:8000/api/agents/earnings-insight/worker-uuid?claim_amount=500&disruption_hours=3&disruption_day_hour=2026-04-17T18:30:00Z" \
  -H "Authorization: Bearer worker_token_here"
```

### Response Schema

```json
{
  "agent_id": "earnings_intelligence_v1",
  "status": "success",
  "result": {
    "worker_id": "worker-uuid",
    "base_claim": ₹500,
    "earnings_dna_profile": {
      "avg_earnings_per_day": ₹680,
      "peak_hours": ["17:00–22:00", "11:30–14:00"],
      "peak_hour_rate": ₹189,
      "off_peak_hour_rate": ₹95,
      "days_worked": 156,
      "consistency_score": 0.82
    },
    "disruption_analysis": {
      "time_of_day": "Friday 18:30 (Peak)",
      "historical_earnings_this_time": ₹1890,
      "time_multiplier": 2.1,
      "disruption_duration": 3,
      "earnings_lost_estimate": ₹945
    },
    "adjusted_payout": ₹945,
    "adjustment_details": {
      "base_to_adjusted_ratio": 1.89,
      "reasoning": "Friday evening disruption. Historical data shows you earn 2.1x your daily average during this time slot. Loss calculated accordingly.",
      "factors": [
        "Peak time detected (18:30)",
        "Friday (high demand day)",
        "3-hour disruption",
        "Consistent worker pattern (82% consistency)"
      ]
    },
    "suggested_actions": [
      "Accept adjusted payout of ₹945",
      "Appeal if you believe loss estimate is inaccurate",
      "Check earnings history under Account → Earnings DNA"
    ],
    "comparable_payouts": {
      "if_monday_morning": ₹320,
      "if_wednesday_afternoon": ₹420,
      "this_time_friday": ₹945
    },
    "confidence": 0.87
  },
  "execution_time_ms": 640,
  "nodes_executed": ["load_earnings_dna", "llm_interpret"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Earnings insight generated |
| 400 | Missing required parameters |
| 401 | Unauthorized (worker token required) |
| 404 | Worker not found |
| 500 | Agent execution error |

### Data Sources

- **Earnings DNA:** Historical worker earnings patterns (14-day average)
- **Peak Hours:** Identified from last 90 days of activity
- **Demand Multiplier:** Zone + time-based surge pricing history
- **Note:** Does NOT call [backend/ml/earnings_dna.py](backend/ml/earnings_dna.py) directly

### ML Model Used

- **Model:** None (Heuristic-based + LLM)
- **Logic:** Time-of-day multiplier + historical average matching

---

## Agent 4: Risk Pricing

### Endpoint

```
GET /api/agents/price-risk/{worker_id}
Authorization: Bearer <worker_token>
```

### Purpose

Suggests weekly premium and explains pricing given zone risk and worker information.

### File

[backend/agents/risk_pricing.py](backend/agents/risk_pricing.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `worker_id` | string | ✅ | UUID of worker |
| `zone_id` | string | ✅ | Zone UUID (optional if on file) |
| `plan_type` | string | ✅ | Basic / Standard / Premium |

### Request Example

```bash
curl -X GET "http://localhost:8000/api/agents/price-risk/worker-uuid?zone_id=zone-uuid&plan_type=Standard" \
  -H "Authorization: Bearer worker_token_here"
```

### Response Schema

```json
{
  "agent_id": "risk_pricing_v1",
  "status": "success",
  "result": {
    "worker_id": "worker-uuid",
    "week_starting": "2026-04-21",
    "zone_risk_profile": {
      "zone_id": "zone-uuid",
      "zone_name": "Velachery Zone 4B",
      "flood_risk_score": 78,
      "heat_risk_score": 45,
      "pollution_risk_score": 52,
      "combined_risk": 0.67,
      "risk_tier": "HIGH"
    },
    "ml_suggested_premium": ₹59,
    "premium_by_plan": {
      "basic": {
        "weekly_premium": ₹35,
        "coverage_amount": ₹1000,
        "payout_cap": ₹2000
      },
      "standard": {
        "weekly_premium": ₹59,
        "coverage_amount": ₹2000,
        "payout_cap": ₹4000
      },
      "premium": {
        "weekly_premium": ₹89,
        "coverage_amount": ₹3500,
        "payout_cap": ₹7000
      }
    },
    "recommended_plan": "Standard",
    "premium_breakdown": {
      "base_premium": ₹35,
      "risk_surcharge_flood": ₹15,
      "risk_surcharge_pollution": ₹8,
      "tenure_discount": ₹0,
      "claim_history_premium": ₹1,
      "final_premium": ₹59
    },
    "live_conditions": {
      "current_weather": "Partly cloudy, 34°C",
      "24hr_forecast": "Heavy rain likely after 6 PM",
      "upcoming_events": ["Red alert weather expected Friday"],
      "zone_activity": "Normal, 2,147 active orders"
    },
    "explanation": "High flood risk (78%) in Velachery + heavy rainfall forecast for this week = premium adjusted upward by ₹24. You're a tenure-2-years veteran, no claims this month (good sign). Standard plan recommended for balanced coverage.",
    "coverage_details": "Covers income loss from weather disruption (rainfall, flooding, heat, AQI), platform suspensions, and curfews. Does NOT cover personal injury or equipment damage.",
    "suggested_actions": [
      "Select Standard plan and renew by Monday 9 AM",
      "Coverage active until next Sunday 11:59 PM",
      "Check real-time zone alerts under Triggers → Live"
    ],
    "confidence": 0.91
  },
  "execution_time_ms": 1120,
  "nodes_executed": ["check_live_conditions", "llm_price"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Risk pricing generated |
| 400 | Invalid parameters |
| 401 | Unauthorized |
| 404 | Worker or zone not found |
| 500 | Agent execution error |

### Premium Factors

| Factor | Weight | Impact |
|--------|--------|--------|
| Zone flood risk | High | ±₹20 |
| Zone heat risk | Medium | ±₹8 |
| Zone pollution risk | Low | ±₹3 |
| Tenure (years) | Low | -₹0–5 |
| Claim history (30d) | High | +₹1–10 |
| Worker trust score | Low | -₹0–3 |

### ML Model Used

- **Model:** XGBoost Regression
- **File:** [backend/ml/premium_model.py](backend/ml/premium_model.py)
- **Input Features:** Zone risk scores, weather forecast, tenure, claim history
- **Output:** `ml_suggested_premium` (deterministic, immutable)

### Enforcement Rules

✋ **Safety Guardrails:**
- LLM **cannot override** the ml_suggested_premium
- If LLM suggests different premium → Code enforces ml_suggested_premium
- All explanations must reference actual ML calculation

---

## Agent 5: Fraud Ring Detective

### Endpoint

```
POST /api/agents/investigate-ring
Authorization: Bearer <admin_token>
Content-Type: application/json
```

### Purpose

Detects coordinated fraud clusters and produces an investigation narrative with actionable insights.

### File

[backend/agents/ring_detective.py](backend/agents/ring_detective.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `claims_data` | array | ❌ | Array of claim UUIDs to analyze. If empty, uses recent claims or generates demo data |
| `detection_mode` | string | ❌ | "STRICT" or "MODERATE" (default: STRICT) |

### Request Example

```bash
curl -X POST http://localhost:8000/api/agents/investigate-ring \
  -H "Authorization: Bearer admin_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "claims_data": ["claim-1", "claim-2", ..., "claim-50"],
    "detection_mode": "STRICT"
  }'
```

Or with auto-generated demo data:
```bash
curl -X POST http://localhost:8000/api/agents/investigate-ring \
  -H "Authorization: Bearer admin_token_here"
```

### Response Schema

```json
{
  "agent_id": "ring_detective_v1",
  "status": "success",
  "result": {
    "analysis_timestamp": "2026-04-17T15:45:00Z",
    "claims_analyzed": 287,
    "rings_detected": 2,
    "suspicious_claim_count": 47,
    "detection_confidence": 0.94,
    "detected_rings": [
      {
        "ring_id": "RING_001",
        "cluster_size": 17,
        "members": [
          "worker-uuid-1",
          "worker-uuid-2",
          "..."
        ],
        "anomaly_patterns": [
          {
            "pattern": "Spatio-temporal clustering",
            "description": "50+ claims from exact 100m radius despite diverse zone histories",
            "severity": "CRITICAL",
            "evidence": "GPS coordinates within 90m of each other"
          },
          {
            "pattern": "Device IP correlation",
            "description": "Multiple accounts from same IP subnet (10.5.47.0/24)",
            "severity": "CRITICAL",
            "evidence": "IMEI prefix 35089 shared across 8 accounts"
          },
          {
            "pattern": "Claim timing synchronization",
            "description": "Claims filed within 2–4 seconds of each other",
            "severity": "HIGH",
            "evidence": "Timestamp deltas: 2s, 3s, 2s, 4s"
          }
        ],
        "pre_event_behavior": {
          "registration_surge": "14 new accounts registered 5 days before red-alert weather",
          "suspicious_activity": true
        },
        "earn_claim_ratio": {
          "typical_earn_month": ₹15000,
          "typical_claim_month": 0,
          "this_month": {
            "earnings": ₹340,
            "claims_filed": 4,
            "claims_value": ₹2100,
            "ratio": "4:1 (Anomalous)"
          }
        },
        "recommendation": "SUSPEND + FLAG FOR LEGAL REVIEW",
        "suggested_actions": [
          "Suspend all 17 accounts immediately",
          "Freeze payouts (₹31,500 at risk)",
          "File police complaint for coordinated fraud",
          "Revoke Zomato Worker IDs with partner platform"
        ]
      },
      {
        "ring_id": "RING_002",
        "cluster_size": 8,
        "members": ["worker-uuid-18", "worker-uuid-19", "..."],
        "anomaly_patterns": [
          {
            "pattern": "Device fingerprint batch",
            "description": "Devices manufactured in same batch (Serial 89XXX range)",
            "severity": "HIGH"
          }
        ],
        "recommendation": "SOFT_SUSPEND + DEVICE_RE_SCAN",
        "confidence": 0.81
      }
    ],
    "pool_impact_analysis": {
      "total_pool_at_risk": ₹48600,
      "if_immediate_action": "₹48,600 protected",
      "if_payouts_processed": "₹48,600 loss (unrecoverable)"
    },
    "investigation_summary": "Detected two coordinated fraud rings using spatio-temporal clustering + device fingerprinting. Ring 001 shows CRITICAL severity (organized syndicate behavior). Ring 002 shows HIGH severity (coordinated but smaller scale). Recommend immediate suspension of all 25 members and escalation to compliance + legal teams. Estimated fraud attempt: ₹48,600.",
    "evidence_summary": [
      "Ring 001: 17 workers, 100m GPS cluster, shared IP, synchronized claims (2-4s apart)",
      "Ring 002: 8 workers, device batch correlation, pre-event registration surge",
      "Combined patterns indicate organized fraud network, not organic user behavior"
    ],
    "confidence": 0.94
  },
  "execution_time_ms": 2340,
  "nodes_executed": ["load_clusters", "llm_investigate"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Ring analysis completed |
| 400 | Invalid request parameters |
| 401 | Unauthorized |
| 500 | Agent execution error |

### Detection Algorithms

| Algorithm | Purpose | Sensitivity |
|-----------|---------|-------------|
| Isolation Forest | Anomaly detection per claim | Medium |
| DBSCAN | Spatial clustering of fraud claims | High |
| Device fingerprint correlation | IP/IMEI/hardware pattern matching | High |
| Temporal analysis | Claim filing timing synchronization | Critical for ring detection |

### ML Model Used

- **Model:** Isolation Forest + DBSCAN
- **File:** [backend/ml/ring_model.py](backend/ml/ring_model.py)
- **Fallback:** [backend/services/ring_detector.py](backend/services/ring_detector.py)
- **Features:** GPS coordinates, device fingerprints, claim timestamps, earnings ratios

---

## Agent 6: Worker Assistant

### Endpoint

```
POST /api/agents/chat
Authorization: Bearer <worker_token>
Content-Type: application/json
```

### Purpose

Worker-facing chatbot that answers questions about claims, payouts, policies, and trust score in plain language.

### File

[backend/agents/worker_assistant.py](backend/agents/worker_assistant.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | ✅ | Worker's question in natural language |
| `worker_id` | string | ✅ | UUID of worker asking |
| `conversation_history` | array | ❌ | Previous messages (for context) |

### Request Example

```bash
curl -X POST http://localhost:8000/api/agents/chat \
  -H "Authorization: Bearer worker_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Why was my claim rejected?",
    "worker_id": "worker-uuid"
  }'
```

### Response Schema

```json
{
  "agent_id": "worker_assistant_v1",
  "status": "success",
  "result": {
    "worker_id": "worker-uuid",
    "question_category": "CLAIM",
    "extracted_entities": {
      "claim_id": "claim-uuid",
      "entity_type": "claim"
    },
    "answer": "Your claim (Claim #12345) was flagged because we detected a mock GPS app on your device. This is a security measure to prevent location spoofing. The good news: it's fixable! Here's what to do:\n\n1. Uninstall any 'GPS spoof' or 'fake location' apps\n2. Restart your phone\n3. File an appeal within 48 hours\n4. We'll re-check your location signals\n\nMost workers who uninstall and reapply get approved. You've got this!",
    "suggested_actions": [
      {
        "action": "UNINSTALL_APPS",
        "description": "Uninstall any GPS spoofing apps",
        "priority": "IMMEDIATE"
      },
      {
        "action": "FILE_APPEAL",
        "description": "Tap the Appeal button in your claim details",
        "priority": "HIGH",
        "deadline": "48 hours from claim time"
      },
      {
        "action": "CONTACT_SUPPORT",
        "description": "Chat with support if you need help",
        "priority": "MEDIUM"
      }
    ],
    "sentiment": "Helpful",
    "urgency": "HIGH",
    "follow_up_questions": [
      "Do you need help uninstalling the GPS app?",
      "Do you want to file an appeal right now?"
    ],
    "resources": [
      {
        "title": "Claim Appeal Guide",
        "url": "/help/appeal-guide",
        "relevant": true
      },
      {
        "title": "Security Best Practices",
        "url": "/help/security",
        "relevant": false
      }
    ]
  },
  "execution_time_ms": 520,
  "nodes_executed": ["understand_question", "llm_explain"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Chat response generated |
| 400 | Invalid parameters |
| 401 | Unauthorized |
| 500 | Agent execution error |

### Question Categories

| Category | Keywords | Scope |
|----------|----------|-------|
| PAYOUT | payout, money, payment, UPI, received | Payout-related questions |
| CLAIM | claim, rejected, approved, status | Claim status & decisions |
| POLICY | coverage, plan, premium, what's covered | Policy & coverage |
| TRIGGER | trigger, event, fired, weather | Trigger events |
| ACCOUNT | profile, trust score, history | Account & history |
| GENERAL | hello, help, how to | General assistance |

### ML Model Used

- **Model:** None (Keyword classification + LLM)
- **Logic:** Intent detection + entity extraction + LLM response generation

### No Safety Guardrails

This agent is conversational and informational only. It does not:
- Approve/reject claims
- Modify payouts
- Change account settings
- Access sensitive PII (masks claim amounts when appropriate)

---

## Agent 7: Appeal Handler

### Endpoint

```
POST /api/agents/handle-appeal/{claim_id}
Authorization: Bearer <admin_token>
Content-Type: application/json
```

### Purpose

Re-evaluates a claim appeal and produces final decision: APPROVE / REJECT / NEEDS_HUMAN.

### File

[backend/agents/appeal_handler.py](backend/agents/appeal_handler.py)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `claim_id` | string | ✅ | UUID of the claim being appealed |
| `appeal_reason` | string | ✅ | Worker's reason for appeal |
| `additional_evidence` | object | ❌ | Additional photos/documents (base64) |

### Request Example

```bash
curl -X POST http://localhost:8000/api/agents/handle-appeal/claim-uuid \
  -H "Authorization: Bearer admin_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "appeal_reason": "I uninstalled the GPS app. Can you recheck?",
    "additional_evidence": {
      "device_screenshot": "base64_encoded_data"
    }
  }'
```

### Response Schema

```json
{
  "agent_id": "appeal_handler_v1",
  "status": "success",
  "result": {
    "claim_id": "claim-uuid",
    "appeal_decision": "NEEDS_HUMAN",
    "worker_id": "worker-uuid",
    "original_claim": {
      "claim_status": "REJECTED",
      "fraud_score": 67,
      "reason": "Mock GPS app detected"
    },
    "appeal_context": {
      "appeal_filed_time": "2026-04-17T16:22:00Z",
      "time_since_rejection": "3 hours",
      "worker_trust_score": 64,
      "worker_history": {
        "total_claims": 8,
        "approved_claims": 6,
        "rejected_claims": 2,
        "average_claim_value": ₹680,
        "dispute_rate": 0.25
      }
    },
    "recheck_signals": {
      "device_fingerprint": {
        "status": "RECHECKED",
        "original_finding": "Mock GPS app (Critical)",
        "new_finding": "No mock GPS app detected",
        "change": "✅ Resolved",
        "confidence_improvement": "+0.18"
      },
      "location_consistency": {
        "status": "CONFIRMED",
        "finding": "Worker in zone during claimed time",
        "device_data": "Accelerometer shows movement patterns consistent with delivery work"
      },
      "order_logs": {
        "status": "CONFIRMED",
        "zomato_orders": 4,
        "orders_in_zone": 4,
        "timestamps": "Match claim window exactly"
      }
    },
    "evidence_update": {
      "updated": true,
      "previous_score": 67,
      "recalculated_score": 28,
      "change": "-39 points (critical improvement)"
    },
    "reasoning": "Worker has successfully addressed the primary fraud signal (removed mock GPS app). Device re-scan confirms clean state. Order logs and accelerometer data support genuine delivery activity during claim window. Worker's trust score is moderate (64) but not problematic. Recommend approval pending one final manual verification step.",
    "recommendation": "APPROVE_WITH_CAUTION",
    "final_decision_rationale": "Evidence overwhelmingly supports genuine claim. However, trust score (64) puts worker in probation tier. Recommend: Auto-approve this appeal, but flag account for 2-week observation period.",
    "suggested_next_steps": [
      "Senior team reviews device screenshots",
      "If confirmed clean, auto-approve ₹945 payout",
      "Add worker to 2-week observation list (extra fraud checks)",
      "Send notification: 'Your appeal was approved. Thank you for working with us!'"
    ],
    "confidence": 0.87,
    "override_reason": null
  },
  "execution_time_ms": 1680,
  "nodes_executed": ["load_claim_history", "recheck_signals", "llm_judge"]
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Appeal decision generated |
| 400 | Invalid claim_id or request |
| 401 | Unauthorized |
| 404 | Claim or appeal not found |
| 500 | Agent execution error |

### Decision Mapping

| LLM Proposal | Code Override | Final Decision |
|--------------|---------------|----------------|
| APPROVE | ✋ Override to NEEDS_HUMAN | NEEDS_HUMAN |
| REJECT | ✅ Accept | REJECT |
| NEEDS_HUMAN | ✅ Accept | NEEDS_HUMAN |
| (LLM fails) | Default to | NEEDS_HUMAN |

**Reasoning:** APPROVE decisions require human co-sign for risk management.

### ML Model Used

- **Model:** None (Rule-based re-analysis + LLM)
- **Logic:** Device fingerprint re-scan + order log cross-check + Fraud Detector service call
- **Note:** Does NOT use [backend/ml/fraud_model.py](backend/ml/fraud_model.py) — uses rule-based rechecking only

### Safety Enforcement

✋ **Critical Guardrails:**
- LLM cannot directly APPROVE appeals
- Code forces all APPROVE → NEEDS_HUMAN for manual review
- LLM failure → Default to NEEDS_HUMAN (never auto-approve on error)
- All override reasons are logged for audit trail

---

## Authentication & Error Handling

### JWT Token Requirements

All agent endpoints require Bearer token in `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Expiry:**
- Worker tokens: 24 hours
- Admin tokens: 8 hours

**Refresh:**
```bash
POST /api/auth/refresh
Authorization: Bearer old_token_here
```

### Error Response Schema

```json
{
  "agent_id": "fraud_investigator_v1",
  "status": "error",
  "result": null,
  "error": {
    "code": "INVALID_CLAIM_ID",
    "message": "Claim not found in database",
    "details": "Claim ID provided does not exist: claim-uuid-invalid",
    "timestamp": "2026-04-17T16:45:00Z",
    "request_id": "req-abc123"
  },
  "execution_time_ms": 120
}
```

### Common Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| INVALID_TOKEN | 401 | JWT token invalid or expired |
| UNAUTHORIZED | 401 | Insufficient permissions |
| NOT_FOUND | 404 | Resource (claim, worker, trigger) not found |
| INVALID_REQUEST | 400 | Malformed request parameters |
| MODEL_ERROR | 500 | ML model execution failed |
| LLM_ERROR | 500 | LLM API call failed (uses fallback) |
| DATABASE_ERROR | 500 | Database query failed |
| RATE_LIMIT | 429 | Too many requests |

### Fallback Behavior

If LLM fails (timeout, API error):

| Agent | Fallback |
|-------|----------|
| Fraud Investigator | Return fraud_score only, no LLM reasoning |
| Trigger Validator | Use rule-based source agreement logic |
| Earnings Intelligence | Return base claim amount, no adjustment |
| Risk Pricing | Return ML premium only, no explanation |
| Ring Detective | Use rule-based clustering from fraud_detector.py |
| Worker Assistant | Return generic help message |
| Appeal Handler | Default to NEEDS_HUMAN |

---

## Testing Agents

### Mock API Usage

All agents use mock external APIs for testing:

- **Weather:** [mock-apis/weather_api.py](mock-apis/weather_api.py)
- **IMD Alerts:** [mock-apis/imd_api.py](mock-apis/imd_api.py)
- **AQI:** [mock-apis/aqicn_api.py](mock-apis/aqicn_api.py)
- **Zomato Platform:** [mock-apis/zomato_api.py](mock-apis/zomato_api.py)
- **Razorpay:** [mock-apis/razorpay_api.py](mock-apis/razorpay_api.py)

### Test Suite

Run all agent tests:
```bash
pytest tests/ -v
```

Run specific agent test:
```bash
pytest tests/test_api.py::test_fraud_investigator -v
```

### Demo Script

Run fraud ring simulation:
```bash
python demo/fraud_ring_simulation.py
```

---

_Built for Guidewire DEVTrails University Hackathon 2026 🚀_
