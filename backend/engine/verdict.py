"""
Verdict assembly — maps gate results to the 6 verdict categories
and computes indicative carbon yield / revenue ranges.

CRITICAL RULE: This is the ONLY module allowed to set the verdict field.
The LLM receives the verdict as read-only context to explain in plain language.
"""

from __future__ import annotations
from typing import List, Optional
import yaml, os

from .schemas import (
    GateResult, GateStatus, VerdictCategory, Verdict, IndicativeNumbers,
    Tier1Intake, PlantingSystem, LandLegalClass,
)


# ── Load config ───────────────────────────────────────────────────────────────
def _load_config():
    path = os.environ.get(
        "METHODOLOGIES_CONFIG_PATH",
        os.path.join(os.path.dirname(__file__), "../config/methodologies.yaml"),
    )
    with open(path) as f:
        return yaml.safe_load(f)

_cfg = _load_config()
_yields = _cfg["sequestration_yields"]
_prices = _cfg["price_bands"]
_scale  = _cfg["scale_economics"]


# ══════════════════════════════════════════════════════════════════════════════
# Verdict assembly
# ══════════════════════════════════════════════════════════════════════════════

def assemble_verdict(gate_results: List[GateResult], intake: Tier1Intake) -> Verdict:
    """
    Convert a list of GateResult objects into a structured Verdict.
    Implements the 6 verdict categories from §7.1 of the brief.
    """

    all_flags: List[str] = []
    for r in gate_results:
        all_flags.extend(r.flags)
    all_flags = list(set(all_flags))

    knockout = next((r for r in gate_results if r.status == GateStatus.fail_structural), None)
    has_insufficient = any(r.status == GateStatus.insufficient_info for r in gate_results)
    structural_flags = [f for f in all_flags if "structural" in f or "fail" in f]

    # ── Ecological caution — special verdict (overrides others if ONE detected)
    if "ecological_caution" in all_flags or "open_natural_ecosystem" in all_flags:
        return Verdict(
            verdict=VerdictCategory.ecological_caution,
            confidence=_confidence(all_flags),
            confidence_reason=(
                "Land characteristics suggest an open natural ecosystem (grassland, scrubland). "
                "Afforestation here may cause ecological harm and is likely to fail integrity checks."
            ),
            flags=all_flags,
            gate_results=[_gate_to_dict(r) for r in gate_results],
            what_we_could_not_check=[
                "Official ecological classification of the land",
                "Presence of biodiversity-sensitive habitat",
            ],
            next_steps=[
                "Commission an ecological assessment before any planting plan.",
                "Consult NRSC Wasteland Atlas and FSI ISFR classification for this parcel.",
                "Consider alternative income sources (pastoral development, NTFP) rather than tree planting.",
            ],
            alternatives=[
                "Grassland conservation payments (emerging in some states)",
                "Pastoral development support",
                "NTFP collection formalisation",
            ],
            methodology_note=(
                "Open natural ecosystems in India are frequently mis-classified as 'wasteland'. "
                "Planting trees on them damages distinct habitats and is increasingly an integrity risk."
            ),
        )

    # ── Hard knockout → NOT_ELIGIBLE_STRUCTURAL
    if knockout:
        return Verdict(
            verdict=VerdictCategory.not_eligible_structural,
            confidence=95,
            confidence_reason=(
                f"Gate '{knockout.gate_id}' produced a structural disqualification. "
                "One or more foundational eligibility requirements are not met."
            ),
            knockout_gate=knockout.gate_id,
            flags=all_flags,
            gate_results=[_gate_to_dict(r) for r in gate_results],
            what_we_could_not_check=_what_we_could_not_check(intake),
            next_steps=_structural_next_steps(knockout),
            alternatives=_alternatives(intake),
            redirect=knockout.redirect,
        )

    # ── Insufficient information to proceed
    if has_insufficient:
        return Verdict(
            verdict=VerdictCategory.insufficient_information,
            confidence=0,
            confidence_reason="One or more required fields are missing. Verdict cannot be determined.",
            flags=all_flags,
            gate_results=[_gate_to_dict(r) for r in gate_results],
            what_we_could_not_check=_what_we_could_not_check(intake),
            next_steps=["Please answer the remaining questions so we can complete your eligibility screen."],
        )

    # ── Economics — scale too small
    if "scale_too_small_likely_uneconomic" in all_flags:
        return Verdict(
            verdict=VerdictCategory.unlikely_economic,
            confidence=_confidence(all_flags),
            confidence_reason=(
                "The land area is very small relative to fixed carbon project transaction costs. "
                "Carbon credits are unlikely to be economically viable at this scale."
            ),
            flags=all_flags,
            gate_results=[_gate_to_dict(r) for r in gate_results],
            what_we_could_not_check=_what_we_could_not_check(intake),
            next_steps=[
                "Explore non-credit environmental incentives for small parcels.",
                "Check whether a local FPO or aggregator accepts very small parcels.",
            ],
            alternatives=_alternatives(intake),
        )

    # ── Aggregation required
    if "aggregation_required" in all_flags or "aggregation_preferred" in all_flags:
        indicative = _compute_indicative(intake)
        return Verdict(
            verdict=VerdictCategory.possible_needs_aggregation,
            confidence=_confidence(all_flags),
            confidence_reason=(
                "The land appears potentially eligible but the area is below the threshold for "
                "a standalone project. Aggregation with other landholders is strongly recommended."
            ),
            flags=all_flags,
            gate_results=[_gate_to_dict(r) for r in gate_results],
            indicative_numbers=indicative,
            what_we_could_not_check=_what_we_could_not_check(intake),
            next_steps=[
                "Contact a carbon project developer or Farmer Producer Organisation (FPO) "
                "that runs grouped/aggregated projects in your region.",
                "Ask about revenue share, contract terms, and which standard they use.",
            ],
            alternatives=_alternatives(intake),
            questions_to_ask_developer=_developer_questions(),
        )

    # ── Promising — no structural issues, adequate scale
    indicative = _compute_indicative(intake)
    return Verdict(
        verdict=VerdictCategory.promising_proceed_feasibility,
        confidence=_confidence(all_flags),
        confidence_reason=(
            "No structural eligibility disqualifications found. "
            "A full feasibility study is the recommended next step."
        ),
        flags=all_flags,
        gate_results=[_gate_to_dict(r) for r in gate_results],
        indicative_numbers=indicative,
        what_we_could_not_check=_what_we_could_not_check(intake),
        next_steps=[
            "Engage a VCS/Gold Standard accredited project developer for a full feasibility study.",
            "Gather land tenure documents (7/12 extract, RTC, patta) for due diligence.",
            "Confirm 10-year land-use history with satellite or documentary evidence.",
        ],
        alternatives=_alternatives(intake),
        questions_to_ask_developer=_developer_questions(),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gate_to_dict(r: GateResult) -> dict:
    return {
        "gate_id": r.gate_id,
        "status": r.status.value,
        "reason": r.reason,
        "redirect": r.redirect,
        "flags": r.flags,
    }


def _confidence(flags: List[str]) -> int:
    score = 90
    for flag in set(flags):
        if "additionality" in flag:
            score -= 40
        elif "ecological" in flag or "permanence" in flag or "leakage" in flag:
            score -= 20
        else:
            score -= 10
    return max(0, min(100, score))


def _compute_indicative(intake: Tier1Intake) -> Optional[IndicativeNumbers]:
    if intake.area_ha is None:
        return None

    system = intake.planting_system or PlantingSystem.unknown
    yield_key_map = {
        PlantingSystem.block_plantation: "fast_growing_block_plantation",
        PlantingSystem.agroforestry: "agroforestry_boundary_scattered",
        PlantingSystem.mangrove: "mangrove_restoration",
        PlantingSystem.bamboo: "bamboo_plantation",
        PlantingSystem.assisted_natural_regen: "assisted_natural_regeneration",
        PlantingSystem.commercial_timber: "fast_growing_block_plantation",
        PlantingSystem.unknown: "mixed_native_restoration",
    }
    yield_key = yield_key_map.get(system, "mixed_native_restoration")
    y = _yields.get(yield_key, _yields["mixed_native_restoration"])

    buffer = _cfg["scale_economics"]["buffer_rate"]["default"]  # 0.15
    price = _prices["nature_based_arr"]

    gross_low = intake.area_ha * y["low"]
    gross_high = intake.area_ha * y["high"]
    net_low = round(gross_low * (1 - buffer), 1)
    net_high = round(gross_high * (1 - buffer), 1)

    revenue_low = round(net_low * price["low"])
    revenue_high = round(net_high * price["high"])

    fv = y.get("first_verification_years", {"min": 4, "max": 6})

    return IndicativeNumbers(
        annual_credits_low=net_low,
        annual_credits_high=net_high,
        revenue_usd_low=revenue_low,
        revenue_usd_high=revenue_high,
        first_issuance_year_min=fv["min"],
        first_issuance_year_max=fv["max"],
    )


def _what_we_could_not_check(intake: Tier1Intake) -> List[str]:
    missing = []
    if not intake.land_use_10yr_ago:
        missing.append("10-year land-use history (satellite verification)")
    if intake.existing_tree_cover_pct is None:
        missing.append("Current tree cover (remote-sensing measurement)")
    
    tenure_val = getattr(intake.tenure_type, "value", intake.tenure_type) if intake.tenure_type else None
    if tenure_val in ("leased", "community"):
        missing.append("Lease agreement review for carbon rights clauses")
    missing.append("Title documents (7/12 extract, RTC, patta)")
    missing.append("Overlap with registered projects in Verra / CCTS registry")
    return missing


def _structural_next_steps(knockout: GateResult) -> List[str]:
    steps = [f"The specific issue: {knockout.reason}"]
    if knockout.redirect:
        steps.append(f"Recommended route: {knockout.redirect}")
    steps.append("Consult a qualified carbon project developer for a professional assessment.")
    return steps


def _alternatives(intake: Tier1Intake) -> List[str]:
    alts = [
        "State government agroforestry subsidies (National Agroforestry Policy)",
        "Green Credit Programme participation (non-tradable green credits)",
        "CSR-funded plantation contracts with local corporates",
        "Timber and NTFP revenue from legally permitted species",
    ]
    if intake.area_ha and intake.area_ha < 5:
        alts.insert(0, "For small parcels: non-carbon value (timber, fruit, NTFPs) is often the best financial answer")
    return alts


def _developer_questions() -> List[str]:
    return [
        "What percentage of carbon revenue do I receive?",
        "Who pays for project design, validation, and verification?",
        "Who legally owns the carbon credits — me or the developer?",
        "What happens if trees fail, burn, or I need to sell the land?",
        "Can I exit the contract? What are the exit terms and penalties?",
        "What is the minimum price you guarantee, and what is the contract term?",
        "Which standard and methodology will you use, and why?",
    ]
