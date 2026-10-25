"""Business rules, case facts, thresholds, and industry terminology for RIOT RADAR.

All strategic figures are calibrated to Pulp Riot Juice Co. case facts.
"""

from dataclasses import dataclass
from typing import Dict, List, Any

# ==============================================================================
# CASE FACTS & CORE FINANCIAL CONSTANTS (Source of Truth)
# ==============================================================================
ANNUAL_REVENUE_INR_CR = 1200.00
CONTRIBUTION_MARGIN_PCT = 32.0  # 32%
SUMMER_REVENUE_INR_CR = 576.00  # 48% of annual (March - June)
SUMMER_VOLUME_BOTTLES = 96_000_000  # ~9.6 Cr bottles
BOTTLE_PRICE_INR = 60.00  # ₹60 per bottle

# Plant & Production constraints
PLANT_COUNT = 2
MONTHLY_CAPACITY_BOTTLES = 25_000_000  # 2.5 Cr bottles/month combined
SUMMER_UTILIZATION_PCT = 95.0

# Co-packer constraints
COPACKER_MAX_VOLUME_PCT = 10.0  # Up to 10% additional volume
COPACKER_COST_PREMIUM_PCT = 25.0  # +25% production cost premium
COPACKER_LEAD_TIME_DAYS = 14  # 2 weeks notice required

# Distribution network
DEPOT_COUNT = 9
GT_DISTRIBUTORS_COUNT = 600

# Channel mix
CHANNEL_MIX = {
    "GT": 0.55,  # General Trade: 55%
    "MT": 0.25,  # Modern Trade: 25%
    "QC": 0.20,  # Quick Commerce: 20%
}

# Shelf life rules
FINISHED_GOODS_SHELF_LIFE_DAYS = 90
MT_QC_MIN_SHELF_LIFE_DAYS = 60  # MT/QC reject stock with < 60 days remaining
GT_ACCEPT_BELOW_60_DAYS = True  # GT can accept stock with < 60 days remaining
FROZEN_PULP_SHELF_LIFE_MONTHS = 6

# Inventory & Rebalancing parameters
DEFAULT_TARGET_COVER_DAYS = 21  # 21 days target cover
DEFAULT_APPROVAL_LATENCY_DAYS = 1  # 1 day planner/executive approval
MIN_TRANSIT_DAYS = 2
MAX_TRANSIT_DAYS = 4
DEFAULT_TRANSIT_DAYS = 3
TRANSFER_COST_PER_BOTTLE_INR = 1.50  # ₹1.50 per bottle

# 67-Day Near-Cliff Threshold Formula:
# 60-day MT/QC threshold + 4-day max transfer + 1-day approval latency + 2-day safety buffer = 67 days
NEAR_CLIFF_WARNING_DAYS = (
    MT_QC_MIN_SHELF_LIFE_DAYS + MAX_TRANSIT_DAYS + DEFAULT_APPROVAL_LATENCY_DAYS + 2
)  # 67 days

# Supply disruption facts
PASSIONFRUIT_ROAD_TRANSIT_DAYS = 3
PASSIONFRUIT_HIGHWAY_CLOSURE_WEEKS = 3  # 3 weeks May closure
PASSIONFRUIT_STARTING_PULP_COVER_DAYS = 14  # ~2 weeks cover
EMERGENCY_AIR_FREIGHT_INR_CR = 3.20  # ₹3.20 Cr (~5x road cost)
DRAGONFRUIT_IMPORTED_SHARE_PCT = 40.0  # 40% imported dragonfruit pulp for PR-DB
DRAGONFRUIT_IMPORT_LEAD_TIME_WEEKS_MIN = 6
DRAGONFRUIT_IMPORT_LEAD_TIME_WEEKS_MAX = 8

# Historical Loss Attribution (Separate, Non-Overlapping Categories)
HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR = 46.08
HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR = 14.75  # 32% of 46.08 Cr
HISTORICAL_WRITEOFFS_DISCOUNTS_INR_CR = 6.00
HISTORICAL_AIR_FREIGHT_INR_CR = 3.20
HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR = 23.95  # 14.75 + 6.00 + 3.20 Cr

# System Budget & Hurdle
YEAR_1_SYSTEM_BUDGET_CAP_INR_CR = 2.50
BREAK_EVEN_RECOVERY_HURDLE_PCT = round(
    (YEAR_1_SYSTEM_BUDGET_CAP_INR_CR / HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR) * 100, 1
)  # ~10.4%

# Historical planner baseline context
SPREADSHEET_PLANNERS_COUNT = 15
HISTORICAL_FORECAST_ERROR_WAPE_PCT = 30.0

# Data freshness reference lags
FRESHNESS_LAGS = {
    "qc_daily_sell_through": 1,  # 1 day lag
    "depot_dispatches": 7,      # 7 days weekly reporting
    "distributor_orders": 7,    # 7 days weekly reporting
    "sop_monthly": 30,          # 30 days monthly consolidated
}


# ==============================================================================
# STABLE SKUs & DEPOTS (45 Operational Grain)
# ==============================================================================
@dataclass(frozen=True)
class SKUDefinition:
    sku_id: str
    flavour: str
    summer_share_pct: float
    primary_planning_concern: str
    pulp_type: str
    pulp_kg_per_bottle: float
    contribution_margin_pct: float = CONTRIBUTION_MARGIN_PCT


SKUS: Dict[str, SKUDefinition] = {
    "PR-MPB": SKUDefinition(
        sku_id="PR-MPB",
        flavour="Mango Peach Basil",
        summer_share_pct=38.0,
        primary_planning_concern="High volume, excess stock and shelf-life cliff",
        pulp_type="Mango-Peach",
        pulp_kg_per_bottle=0.080,
    ),
    "PR-GC": SKUDefinition(
        sku_id="PR-GC",
        flavour="Guava Chilli",
        summer_share_pct=20.0,
        primary_planning_concern="Cross-depot imbalance and GT reallocation",
        pulp_type="Guava",
        pulp_kg_per_bottle=0.075,
    ),
    "PR-PP": SKUDefinition(
        sku_id="PR-PP",
        flavour="Passionfruit Punch",
        summer_share_pct=16.0,
        primary_planning_concern="Single-source pulp and highway closure",
        pulp_type="Passionfruit",
        pulp_kg_per_bottle=0.070,
    ),
    "PR-DB": SKUDefinition(
        sku_id="PR-DB",
        flavour="Dragonfruit Bloom",
        summer_share_pct=14.0,
        primary_planning_concern="40% imported pulp and long lead time",
        pulp_type="Dragonfruit",
        pulp_kg_per_bottle=0.075,
    ),
    "PR-DP": SKUDefinition(
        sku_id="PR-DP",
        flavour="Dragon Passion",
        summer_share_pct=12.0,
        primary_planning_concern="Fourfold QC spike and shared passionfruit pulp",
        pulp_type="Dragonfruit-Passionfruit",
        pulp_kg_per_bottle=0.065,  # Uses 0.035kg Passionfruit + 0.030kg Dragonfruit
    ),
}

DEPOTS: List[Dict[str, Any]] = [
    {"depot_id": "Depot-North-01", "name": "Delhi NCR Depot", "region": "North", "lead_time_days": 2},
    {"depot_id": "Depot-North-02", "name": "Lucknow Depot", "region": "North", "lead_time_days": 3},
    {"depot_id": "Depot-West-01", "name": "Mumbai Depot", "region": "West", "lead_time_days": 2},
    {"depot_id": "Depot-West-02", "name": "Ahmedabad Depot", "region": "West", "lead_time_days": 3},
    {"depot_id": "Depot-South-01", "name": "Bengaluru Depot", "region": "South", "lead_time_days": 2},
    {"depot_id": "Depot-South-02", "name": "Chennai Depot", "region": "South", "lead_time_days": 3},
    {"depot_id": "Depot-East-01", "name": "Kolkata Depot", "region": "East", "lead_time_days": 3},
    {"depot_id": "Depot-East-02", "name": "Guwahati Depot", "region": "East", "lead_time_days": 4},
    {"depot_id": "Depot-Central-01", "name": "Indore Depot", "region": "Central", "lead_time_days": 3},
]


# ==============================================================================
# LOSS ATTRIBUTION ROOT-CAUSE RANGES
# ==============================================================================
ROOT_CAUSE_CONFIG = {
    "late_demand_detection": {
        "label": "Late Demand Detection (QC / Sell-Through Blind Spot)",
        "default_pct": 35.0,
        "min_pct": 30.0,
        "max_pct": 40.0,
    },
    "stale_allocation_censored_loop": {
        "label": "Stale Allocation & Censored-Demand Loop",
        "default_pct": 40.0,
        "min_pct": 35.0,
        "max_pct": 45.0,
    },
    "single_source_pulp_rationing": {
        "label": "Single-Source Pulp Shortage & Ad-Hoc Rationing",
        "default_pct": 25.0,
        "min_pct": 20.0,
        "max_pct": 30.0,
    },
}


# ==============================================================================
# THRESHOLDS & RISK CLASSIFICATION
# ==============================================================================
RISK_THRESHOLDS = {
    "days_of_cover_critical": 7.0,     # < 7 days = CRITICAL
    "days_of_cover_warning": 14.0,     # 7 - 14 days = WARNING
    "days_of_cover_target": 21.0,      # 21 days = HEALTHY TARGET
    "wape_warning_pct": 25.0,          # WAPE > 25% = WARNING
    "wape_critical_pct": 35.0,         # WAPE > 35% = CRITICAL
    "forecast_bias_warning_pct": 15.0, # Bias > ±15% = WARNING
    "forecast_bias_critical_pct": 25.0,# Bias > ±25% = CRITICAL
    "donor_min_post_transfer_doc": 21.0, # Donor must retain >= 21d cover
}


# ==============================================================================
# INDUSTRY TERMINOLOGY GLOSSARY
# ==============================================================================
GLOSSARY = {
    "SKU": "Stock Keeping Unit. Unique identifier for a finished juice product.",
    "SKU–Depot": "The fundamental operational planning grain combining an individual SKU and an individual regional depot.",
    "Demand Sensing": "Short-latency demand estimation using high-frequency signals (e.g. 1-day QC sell-through) to detect shifts before monthly S&OP.",
    "Censored Demand": "True consumer demand that was hidden or unrecorded because stock was zero or depleted at points of sale.",
    "WAPE": "Weighted Absolute Percentage Error. Sum of absolute forecast errors divided by total actual demand. Standard metric for intermittent FMCG demand.",
    "Forecast Bias": "Normalized systematic tendency to overforecast (positive bias) or underforecast (negative bias).",
    "Days of Cover (DoC)": "Number of days the currently usable inventory can satisfy the corrected daily forecast demand before stock-out.",
    "Inventory Rebalancing": "Optimized inter-depot physical transfers from surplus locations to shortage locations, respecting transit times, shelf life and donor safety cover.",
    "Allocation Gap": "Difference between target stock required (for 21 days cover) and projected usable stock.",
    "Service Level (Fill Rate)": "Percentage of total estimated demand fulfilled by available supply. Labeled as estimated when demand includes censored adjustments.",
    "Channel-Segmented FEFO": "First Expired, First Out inventory allocation enforcing channel rules: >=60 days remaining for MT/QC, <60 days restricted to GT.",
    "OTIF": "On Time In Full. Performance metric measuring whether inbound supplier deliveries arrive on schedule and complete.",
    "Demand Uplift": "Percentage increase in corrected true demand compared to observed historical sales due to stock-out censoring.",
    "Exception Management": "Systematic identification and algorithmic flagging of supply chain risks exceeding operational thresholds for human intervention.",
    "Forecast Vintage": "An immutable, time-stamped snapshot of forecasts generated before the operational period began, preventing hindsight bias in accuracy evaluations.",
    "Control Tower": "An integrated operational decision system providing real-time visibility, automated risk detection, and prescriptive recommendations.",
}


# ==============================================================================
# SEMANTIC COLOR TOKENS
# ==============================================================================
COLOR_TOKENS = {
    "OBSERVED_ACTUAL": "#334155",   # Solid Slate
    "VINTAGE_FORECAST": "#0284C7",  # Institutional Blue
    "CORRECTED_LATENT": "#7C3AED",  # Deep Violet
    "RISK_CRITICAL": "#DC2626",     # Crimson (<7d cover, stock-out, <60d MT/QC rejection)
    "RISK_WARNING": "#D97706",      # Amber (60-67d near-cliff, 7-14d cover)
    "HEALTHY_SURPLUS": "#0D9488",   # Muted Teal (>=21d cover, transfer donor)
    "NEUTRAL_BASELINE": "#94A3B8",  # Muted Grey (Naive benchmark)
}
