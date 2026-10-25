"""Loss Attribution & Financial Guardrails Service for RIOT RADAR.

Maintains strict SCM financial discipline:
1. Strict separation of Non-Overlapping Categories (Never adds lost revenue to foregone contribution).
2. Bottom-Line Exposure = Foregone Contribution (₹14.75 Cr) + Write-offs (₹6.00 Cr) + Emergency Air Freight (₹3.20 Cr) = ₹23.95 Cr.
3. Year-1 System Budget Hurdle: ₹2.50 Cr is a 10.4% Break-Even Recovery Hurdle.
4. Interactive, range-constrained deterministic root-cause redistribution model for the ₹46.08 Cr lost revenue.
"""

from typing import Dict, Any, Tuple
from config.business_rules import (
    HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR,
    HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR,
    HISTORICAL_WRITEOFFS_DISCOUNTS_INR_CR,
    HISTORICAL_AIR_FREIGHT_INR_CR,
    HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR,
    YEAR_1_SYSTEM_BUDGET_CAP_INR_CR,
    BREAK_EVEN_RECOVERY_HURDLE_PCT,
    ROOT_CAUSE_CONFIG,
    CONTRIBUTION_MARGIN_PCT,
)


def get_loss_categories() -> Dict[str, Any]:
    """Return the authoritative, non-overlapping historical loss categories.
    
    CRITICAL RULE:
    Never sum Lost Revenue (₹46.08 Cr) and Foregone Contribution (₹14.75 Cr).
    Lost revenue is top-line gross transaction value.
    Foregone contribution is the 32% margin component within lost revenue.
    """
    return {
        "stockout_lost_revenue_inr_cr": HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR,
        "foregone_contribution_inr_cr": HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR,
        "writeoffs_and_discounts_inr_cr": HISTORICAL_WRITEOFFS_DISCOUNTS_INR_CR,
        "emergency_air_freight_inr_cr": HISTORICAL_AIR_FREIGHT_INR_CR,
        "competitive_shelf_space_impact": "UNQUANTIFIED (Brand presence & listing loss)",
        "bottom_line_exposure_inr_cr": HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR,
        "year_1_system_budget_cap_inr_cr": YEAR_1_SYSTEM_BUDGET_CAP_INR_CR,
        "break_even_recovery_hurdle_pct": BREAK_EVEN_RECOVERY_HURDLE_PCT,
        "margin_pct": CONTRIBUTION_MARGIN_PCT,
    }


def redistribute_root_causes(
    changed_cause_key: str,
    new_value_pct: float,
    current_shares: Dict[str, float],
) -> Tuple[Dict[str, float], bool, str]:
    """Deterministically redistribute root-cause percentages to maintain sum == 100%.
    
    Enforces configured ranges:
    - late_demand_detection: [30.0, 40.0]
    - stale_allocation_censored_loop: [35.0, 45.0]
    - single_source_pulp_rationing: [20.0, 30.0]
    """
    shares = {k: float(v) for k, v in current_shares.items()}
    
    # Check if changed key exists
    if changed_cause_key not in ROOT_CAUSE_CONFIG:
        return shares, False, f"Unknown root cause: {changed_cause_key}"

    cfg = ROOT_CAUSE_CONFIG[changed_cause_key]
    min_val, max_val = cfg["min_pct"], cfg["max_pct"]
    clamped_val = max(min_val, min(max_val, round(new_value_pct, 1)))
    shares[changed_cause_key] = clamped_val

    # Other keys to adjust
    other_keys = [k for k in ROOT_CAUSE_CONFIG.keys() if k != changed_cause_key]
    target_remainder = round(100.0 - clamped_val, 1)

    # Check bounds of remainder
    min_other_sum = sum(ROOT_CAUSE_CONFIG[k]["min_pct"] for k in other_keys)
    max_other_sum = sum(ROOT_CAUSE_CONFIG[k]["max_pct"] for k in other_keys)

    if target_remainder < min_other_sum or target_remainder > max_other_sum:
        return shares, False, (
            f"Infeasible combination: Remainder {target_remainder}% cannot fit within "
            f"the other causes' configured ranges [{min_other_sum}%, {max_other_sum}%]."
        )

    # Proportional redistribution across other causes
    current_other_sum = sum(shares[k] for k in other_keys)
    if current_other_sum <= 0:
        # Equal split
        for k in other_keys:
            shares[k] = target_remainder / len(other_keys)
    else:
        # Scale proportionally then clamp iteratively
        ratio = target_remainder / current_other_sum
        for k in other_keys:
            candidate = round(shares[k] * ratio, 1)
            k_min = ROOT_CAUSE_CONFIG[k]["min_pct"]
            k_max = ROOT_CAUSE_CONFIG[k]["max_pct"]
            shares[k] = max(k_min, min(k_max, candidate))

        # Re-check and adjust 0.1 rounding drift on first other key if within bounds
        diff = round(100.0 - sum(shares.values()), 1)
        if abs(diff) > 0.001:
            for k in other_keys:
                k_min = ROOT_CAUSE_CONFIG[k]["min_pct"]
                k_max = ROOT_CAUSE_CONFIG[k]["max_pct"]
                adjusted = shares[k] + diff
                if k_min <= adjusted <= k_max:
                    shares[k] = round(adjusted, 1)
                    break

    is_valid = abs(sum(shares.values()) - 100.0) < 0.05
    msg = "Valid attribution (sums to 100.0%)" if is_valid else "Could not resolve exact 100% split."
    return shares, is_valid, msg


def calculate_root_cause_exposures(shares: Dict[str, float]) -> Dict[str, Any]:
    """Calculate allocated revenue exposure and contribution exposure for root causes."""
    total_rev = HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR
    margin = CONTRIBUTION_MARGIN_PCT / 100.0

    breakdown = {}
    for key, cfg in ROOT_CAUSE_CONFIG.items():
        share_pct = shares.get(key, cfg["default_pct"])
        rev_exposure = round(total_rev * (share_pct / 100.0), 2)
        contrib_exposure = round(rev_exposure * margin, 2)
        breakdown[key] = {
            "label": cfg["label"],
            "share_pct": share_pct,
            "allocated_revenue_exposure_inr_cr": rev_exposure,
            "allocated_contribution_exposure_inr_cr": contrib_exposure,
            "min_pct": cfg["min_pct"],
            "max_pct": cfg["max_pct"],
        }

    return {
        "title": "Illustrative Root-Cause Attribution — Model-Estimated Range",
        "total_stockout_lost_revenue_inr_cr": total_rev,
        "total_foregone_contribution_inr_cr": HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR,
        "shares_sum_pct": round(sum(shares.values()), 1),
        "breakdown": breakdown,
        "disclaimer": (
            "Note: This root-cause attribution is an illustrative model estimate calibrated to case constraints, "
            "not an audited accounting fact. Exposure percentages represent strategic sensitivity ranges."
        ),
    }
