"""
The Ten Eligibility Gates — deterministic rules engine.

Design principles (from the technical implementation plans):
  1. Each gate is an independent pure function: (Tier1Intake) -> GateResult
  2. Gates are evaluated in order. A fail_structural status short-circuits
     all remaining gates — the brief explicitly says asking 20 more questions
     after gate 1 fails is a bad UX.
  3. The LLM NEVER calls or overrides these functions. Verdict is set only
     by run_gates.py using these results.
  4. All thresholds are read from methodologies.yaml (via config), never
     hardcoded here — they change.

Gate reference: §3.1 of the Carbon Market Eligibility Chatbot Brief.
"""

from __future__ import annotations
from datetime import date
from typing import Optional
import yaml
import os

from .schemas import Tier1Intake, GateResult, GateStatus, TenureType, LandLegalClass, PlantingStatus


# ── Load config (thresholds, never hardcoded) ─────────────────────────────────
def _load_config():
    config_path = os.environ.get(
        "METHODOLOGIES_CONFIG_PATH",
        os.path.join(os.path.dirname(__file__), "../config/methodologies.yaml"),
    )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

_cfg = _load_config()
_land = _cfg["land_eligibility"]
_scale = _cfg["scale_economics"]


# ══════════════════════════════════════════════════════════════════════════════
# GATE 1 — Land-use history
# The land must not have been classified as "forest" (≥15% canopy) for the
# applicable baseline period, OR must be forested but NOT managed for wood.
# ══════════════════════════════════════════════════════════════════════════════
def gate_1_land_use_history(intake: Tier1Intake) -> GateResult:
    """
    Tests whether the land's historical tree cover creates a forest-definition
    conflict. Uses India's CDM/Kyoto forest threshold (15% canopy, 0.05 ha, 2m).
    """
    if intake.existing_tree_cover_pct is None and intake.land_use_10yr_ago is None:
        return GateResult(
            gate_id="gate_1",
            status=GateStatus.insufficient_info,
            reason=(
                "We need to know your land's current tree cover percentage "
                "(or land-use 10 years ago) to check the forest-history gate."
            ),
        )

    threshold = _land["cdm_forest_threshold_canopy_pct"]  # 15%

    # Recorded Forest Area — already a hard redirect regardless of cover
    if intake.land_legal_class == LandLegalClass.recorded_forest:
        return GateResult(
            gate_id="gate_1",
            status=GateStatus.fail_structural,
            reason=(
                "Land legally classified as Recorded Forest Area cannot be registered "
                "under a private carbon project. The route for this land is through "
                "the State Forest Department, JFM committees, or the Green Credit Programme."
            ),
            redirect="State Forest Department / Green Credit Programme",
        )

    # Open Natural Ecosystem detected — ecological caution flag
    if intake.land_legal_class == LandLegalClass.grassland_scrub:
        return GateResult(
            gate_id="gate_1",
            status=GateStatus.flag,
            reason=(
                "The land appears to be a grassland, scrubland, or open natural ecosystem. "
                "Afforesting these areas can damage biodiversity and pastoral livelihoods. "
                "An ecological assessment is recommended before considering a tree-planting project."
            ),
            flags=["ecological_caution", "open_natural_ecosystem"],
        )

    cover = intake.existing_tree_cover_pct or 0
    if cover > threshold:
        # High existing canopy — potential forest-status issue
        # Block plantation specifically hits this; census-based agroforestry is more resilient
        return GateResult(
            gate_id="gate_1",
            status=GateStatus.flag,
            reason=(
                f"Existing tree cover of ~{cover:.0f}% is above India's CDM forest definition "
                f"threshold of {threshold}%. This may mean the land already qualifies as "
                f"'forest', which could affect eligibility for new afforestation credits. "
                f"A forest-status check by a qualified assessor is recommended."
            ),
            flags=["forest_status_risk"],
        )

    return GateResult(
        gate_id="gate_1",
        status=GateStatus.pass_,
        reason=(
            f"Existing tree cover (~{cover:.0f}%) is below the {threshold}% CDM forest "
            f"definition threshold. Land-use history appears compatible with an "
            f"afforestation/reforestation project."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 2 — No recent ecosystem conversion
# No clearing of native ecosystem within 10 years before project start.
# ══════════════════════════════════════════════════════════════════════════════
def gate_2_no_recent_conversion(intake: Tier1Intake) -> GateResult:
    lookback = _land["no_conversion_lookback_years"]  # 10
    current_year = date.today().year
    cutoff_year = current_year - lookback

    if intake.recent_clearing is None and intake.last_clearing_year is None:
        return GateResult(
            gate_id="gate_2",
            status=GateStatus.insufficient_info,
            reason=(
                "We need to know whether any natural vegetation was cleared on this "
                "land in the last 10 years. This is one of the most important eligibility tests."
            ),
        )

    cleared_recently = intake.recent_clearing or (
        intake.last_clearing_year is not None and intake.last_clearing_year >= cutoff_year
    )

    if cleared_recently:
        return GateResult(
            gate_id="gate_2",
            status=GateStatus.fail_structural,
            reason=(
                f"Natural vegetation appears to have been cleared on or after {cutoff_year}. "
                f"Carbon standards do not allow crediting plantations that replaced "
                f"native ecosystems within the last {lookback} years — this prevents a "
                f"perverse incentive to cut and replant. This project is unlikely to be "
                f"eligible for carbon credits under current rules."
            ),
        )

    return GateResult(
        gate_id="gate_2",
        status=GateStatus.pass_,
        reason=(
            f"No recent conversion of native ecosystem detected (within the last {lookback} years). "
            f"Gate 2 passed."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 3 — Start date and vintage
# Planting must be recent enough to register. CCTS requires start ≥ 1 Jan 2025.
# ══════════════════════════════════════════════════════════════════════════════
def gate_3_start_date_vintage(intake: Tier1Intake) -> GateResult:
    max_age = _land["max_planting_age_years_for_registration"]  # 5 years
    ccts_min = _land["ccts_project_start_min"]                 # "2025-01-01"

    if intake.planting_status is None:
        return GateResult(
            gate_id="gate_3",
            status=GateStatus.insufficient_info,
            reason="Please tell us when the trees were (or will be) planted.",
        )

    if intake.planting_status == PlantingStatus.planted_gt_5yrs:
        return GateResult(
            gate_id="gate_3",
            status=GateStatus.fail_structural,
            reason=(
                f"Trees planted more than {max_age} years ago are unlikely to be eligible "
                f"for new registration under voluntary standards, which require listing within "
                f"a limited window after the project start date. "
                f"The CCTS Offset Mechanism also requires a project start date no earlier "
                f"than {ccts_min}. Retroactive crediting of established plantations is not permitted."
            ),
        )

    if intake.planting_status == PlantingStatus.planted_2_5yrs:
        return GateResult(
            gate_id="gate_3",
            status=GateStatus.flag,
            reason=(
                "Trees planted 2–5 years ago may still be registrable, but the window "
                "is narrowing. Prompt action is recommended — check the registration "
                "deadline for your chosen standard. CCTS requires start date ≥ 1 Jan 2025."
            ),
            flags=["vintage_risk"],
        )

    return GateResult(
        gate_id="gate_3",
        status=GateStatus.pass_,
        reason="Planting timeline is compatible with current registration windows.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 4 — Additionality
# The project must not be the business-as-usual outcome.
# ══════════════════════════════════════════════════════════════════════════════
def gate_4_additionality(intake: Tier1Intake) -> GateResult:
    flags = []
    reasons = []

    if intake.would_plant_anyway is None:
        return GateResult(
            gate_id="gate_4",
            status=GateStatus.insufficient_info,
            reason=(
                "To check additionality, we need to know: if there were no carbon payment "
                "at all, would you still plant these trees?"
            ),
        )

    # Financial additionality
    if intake.would_plant_anyway:
        reasons.append(
            "You indicated you would plant trees even without carbon revenue. "
            "This raises an additionality concern — credits must represent a genuine change "
            "from what would have happened anyway."
        )
        flags.append("additionality_financial_risk")

    # Regulatory additionality
    if intake.planting_legally_mandated:
        reasons.append(
            "If planting is legally mandated (compensatory afforestation, environmental clearance "
            "condition, mine reclamation obligation), it cannot also be sold as a carbon credit."
        )
        flags.append("additionality_regulatory_fail")

    # Already profitable without carbon
    if intake.already_profitable_without_carbon:
        reasons.append(
            "Commercial plantations already profitable from timber, fruit or fodder "
            "(e.g., eucalyptus, mango orchards) routinely fail the financial additionality test."
        )
        flags.append("additionality_commercial_risk")

    # Hard knockout: legally mandated
    if intake.planting_legally_mandated:
        return GateResult(
            gate_id="gate_4",
            status=GateStatus.fail_structural,
            reason=" | ".join(reasons),
            flags=flags,
        )

    if flags:
        return GateResult(
            gate_id="gate_4",
            status=GateStatus.flag,
            reason=(
                "One or more additionality concerns were flagged. "
                "A project developer would need to construct a strong additionality argument. "
                "Details: " + " | ".join(reasons)
            ),
            flags=flags,
        )

    return GateResult(
        gate_id="gate_4",
        status=GateStatus.pass_,
        reason="No immediate additionality concerns flagged.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 5 — Land tenure and rights
# Clear, documented, uncontested right to the land for the full crediting period.
# ══════════════════════════════════════════════════════════════════════════════
def gate_5_tenure(intake: Tier1Intake) -> GateResult:
    if intake.tenure_type is None:
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.insufficient_info,
            reason="Do you own this land, lease it, or is it held by a community or government?",
        )

    if intake.tenure_type == TenureType.disputed:
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.fail_structural,
            reason=(
                "Registries will not issue carbon credits over disputed land. "
                "The tenure conflict must be resolved and title confirmed before "
                "a carbon project can proceed."
            ),
        )

    if intake.tenure_type == TenureType.government:
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.fail_structural,
            reason=(
                "Government-owned land cannot be registered as a private carbon project. "
                "Routes for government / RFA land go through the State Forest Department "
                "or the Green Credit Programme."
            ),
            redirect="State Forest Department / Green Credit Programme",
        )

    if intake.tenure_type == TenureType.leased:
        if intake.lease_years_remaining is not None and intake.lease_years_remaining < 25:
            return GateResult(
                gate_id="gate_5",
                status=GateStatus.flag,
                reason=(
                    f"Your lease has approximately {intake.lease_years_remaining:.0f} years remaining. "
                    "The lease must run at least as long as the crediting period (typically 25–40 years) "
                    "and must explicitly cover tree ownership and carbon rights. "
                    "A short or silent lease is a common knockout — have a lawyer review it."
                ),
                flags=["tenure_lease_short"],
            )
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.flag,
            reason=(
                "Leased land is eligible in principle, but the lease agreement must "
                "explicitly grant carbon rights, cover the full crediting period, and "
                "address what happens on early termination. Please have this reviewed."
            ),
            flags=["tenure_lease_review_needed"],
        )

    if intake.tenure_type == TenureType.community:
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.flag,
            reason=(
                "Community land is eligible in principle but requires a formal community "
                "institution, a panchayat or gram sabha resolution, and a benefit-sharing "
                "agreement that protects existing users. Timelines are typically longer."
            ),
            flags=["tenure_community_complexity"],
        )

    # Owned — check FRA flag
    if intake.fra_claim_flag:
        return GateResult(
            gate_id="gate_5",
            status=GateStatus.flag,
            reason=(
                "A Forest Rights Act claim or recognised forest right exists over or near "
                "this parcel. Rights-holder consent and participation are mandatory. "
                "Projects that fence off or displace rights-holders are both unethical "
                "and unbankable under any credible standard."
            ),
            flags=["fra_claim_risk"],
        )

    return GateResult(
        gate_id="gate_5",
        status=GateStatus.pass_,
        reason="Land tenure type is compatible with a carbon project (subject to document verification).",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 6 — Carbon rights and consent
# Right to sell sequestered carbon; consent of co-owners, tenants, users.
# ══════════════════════════════════════════════════════════════════════════════
def gate_6_carbon_rights(intake: Tier1Intake) -> GateResult:
    flags = []
    reasons = []

    if intake.grazing_use:
        flags.append("grazing_displacement_risk")
        reasons.append("Grazing displacement risk.")

    if intake.fuelwood_collection:
        flags.append("fuelwood_collection_risk")
        reasons.append("Fuelwood collection by local users.")
        
    if intake.ntfp_collection:
        flags.append("ntfp_collection_risk")
        reasons.append("Non-timber forest product (NTFP) collection.")
        
    if intake.tenant_present_flag:
        flags.append("tenant_consent_required")
        reasons.append("Tenant farmers are present and require consent/compensation.")
        
    if intake.co_owners_count and intake.co_owners_count > 1:
        flags.append("co_owner_consent_required")
        reasons.append(f"Consent required from all {intake.co_owners_count} co-owners.")

    if flags:
        return GateResult(
            gate_id="gate_6",
            status=GateStatus.flag,
            reason=(
                "The land appears to have existing uses or shared ownership. "
                "All users and co-owners must give free, prior and informed consent, "
                "and be fairly compensated or included in the project. "
                "Details: " + " | ".join(reasons)
            ),
            flags=flags,
        )

    return GateResult(
        gate_id="gate_6",
        status=GateStatus.pass_,
        reason="No immediate carbon rights or consent conflicts flagged.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 7 — Permanence
# Commitment to maintain carbon for the full crediting/monitoring period.
# ══════════════════════════════════════════════════════════════════════════════
def gate_7_permanence(intake: Tier1Intake) -> GateResult:
    flags = ["permanence_commitment_required"]
    reasons = [
        "Carbon projects require you to keep the trees standing and healthy for 30–40 years. "
        "A share of your credits (typically 10–25%) will be withheld to a buffer pool as "
        "insurance against fire, disease or early harvesting. "
        "This commitment will constrain future land-use options, resale and inheritance planning."
    ]

    if intake.fire_history:
        flags.append("fire_risk")
        reasons.append(f"Fire history noted: {intake.fire_history}.")
        
    if intake.flood_exposure:
        flags.append("flood_risk")
        reasons.append(f"Flood exposure noted: {intake.flood_exposure}.")
        
    if intake.grazing_pressure:
        flags.append("grazing_pressure_risk")
        reasons.append(f"Grazing pressure noted: {intake.grazing_pressure}. Saplings may need fencing.")

    return GateResult(
        gate_id="gate_7",
        status=GateStatus.flag,
        reason=" ".join(reasons),
        flags=flags,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 8 — Leakage
# Displaced activity must be accounted for or shown not to occur.
# ══════════════════════════════════════════════════════════════════════════════
def gate_8_leakage(intake: Tier1Intake) -> GateResult:
    flags = []
    reasons = []

    if intake.grazing_use:
        flags.append("leakage_grazing_risk")
        reasons.append("Grazing activity may shift elsewhere, causing emissions (leakage).")
        
    if intake.cultivation_displacement:
        flags.append("leakage_cultivation_risk")
        reasons.append("Agricultural cultivation may be displaced elsewhere, causing emissions (leakage).")

    if flags:
        return GateResult(
            gate_id="gate_8",
            status=GateStatus.flag,
            reason=(
                "If existing activities (like grazing or cultivation) are stopped under "
                "the project, the methodology requires demonstrating where that activity moves. "
                "Details: " + " | ".join(reasons)
            ),
            flags=flags,
        )

    return GateResult(
        gate_id="gate_8",
        status=GateStatus.pass_,
        reason="No significant leakage risk flagged based on available information.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 9 — No double counting
# Not registered under another crediting programme.
# ══════════════════════════════════════════════════════════════════════════════
def gate_9_double_counting(intake: Tier1Intake) -> GateResult:
    if intake.existing_scheme_registration is None:
        return GateResult(
            gate_id="gate_9",
            status=GateStatus.insufficient_info,
            reason=(
                "Is this land already registered in a government scheme, CSR plantation "
                "programme, or another carbon registry? Double-registration is not permitted."
            ),
        )

    if intake.existing_scheme_registration:
        return GateResult(
            gate_id="gate_9",
            status=GateStatus.fail_structural,
            reason=(
                "The land or project appears to be already registered under another scheme. "
                "Carbon standards prohibit double-counting — one tonne, one claim. "
                "The existing registration must be checked before proceeding."
            ),
        )

    return GateResult(
        gate_id="gate_9",
        status=GateStatus.pass_,
        reason="No existing scheme registration detected.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GATE 10 — Scale and economics
# Enough tonnes over enough years to cover fixed transaction costs.
# ══════════════════════════════════════════════════════════════════════════════
def gate_10_scale_economics(intake: Tier1Intake) -> GateResult:
    if intake.area_ha is None:
        return GateResult(
            gate_id="gate_10",
            status=GateStatus.insufficient_info,
            reason="How many hectares of land do you have? This determines project economics.",
        )

    standalone_min = _scale["standalone_feasible_min_ha"]   # 500
    aggregation_preferred = _scale["aggregation_preferred_max_ha"]  # 200
    aggregation_required = _scale["aggregation_required_max_ha"]  # 2

    if intake.area_ha < aggregation_required:
        return GateResult(
            gate_id="gate_10",
            status=GateStatus.flag,
            reason=(
                f"At {intake.area_ha:.1f} ha, the land area is very small for a carbon credit "
                f"project. Fixed costs (project design, validation, verification) are typically "
                f"USD 30,000–80,000+, which would not amortise at this scale. "
                f"Non-credit environmental incentives (state agroforestry subsidies, Green Credit "
                f"Programme, CSR payments) may be a better fit."
            ),
            flags=["scale_too_small_likely_uneconomic"],
        )

    if intake.area_ha < aggregation_preferred:
        return GateResult(
            gate_id="gate_10",
            status=GateStatus.flag,
            reason=(
                f"At {intake.area_ha:.1f} ha, a standalone project may not be economically viable. "
                f"Joining a grouped / aggregated project is strongly recommended — a developer or FPO "
                f"aggregates many landholders so fixed costs are shared."
            ),
            flags=["aggregation_required"],
        )

    if intake.area_ha < standalone_min:
        return GateResult(
            gate_id="gate_10",
            status=GateStatus.flag,
            reason=(
                f"At {intake.area_ha:.1f} ha, aggregation with other landholders will improve "
                f"project economics. A standalone project is possible but borderline — "
                f"a full feasibility study is recommended."
            ),
            flags=["aggregation_preferred"],
        )

    return GateResult(
        gate_id="gate_10",
        status=GateStatus.pass_,
        reason=(
            f"At {intake.area_ha:.1f} ha, scale is sufficient for a standalone carbon project "
            f"economics analysis."
        ),
    )


# ── Ordered gate list (evaluation sequence) ──────────────────────────────────
GATES = [
    gate_1_land_use_history,
    gate_2_no_recent_conversion,
    gate_3_start_date_vintage,
    gate_4_additionality,
    gate_5_tenure,
    gate_6_carbon_rights,
    gate_7_permanence,
    gate_8_leakage,
    gate_9_double_counting,
    gate_10_scale_economics,
]
