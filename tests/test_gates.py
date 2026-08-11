"""
pytest test suite — 50 golden cases for the eligibility rules engine.

CRITICAL: These tests are the regression gate. Every PR touching gates.py
or verdict.py must pass all 50 cases. No knockout regressions allowed.

Run: pytest tests/test_gates.py -v --tb=short
"""

import json
import os
import sys
import pytest
from typing import Optional

# Make sure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from engine.schemas import (
    Tier1Intake, VerdictCategory, TenureType, LandLegalClass,
    PlantingStatus, PlantingSystem,
)
from engine.run_gates import run_gates


# ── Load golden cases ─────────────────────────────────────────────────────────
CASES_PATH = os.path.join(os.path.dirname(__file__), "golden_cases/cases.json")
with open(CASES_PATH) as f:
    GOLDEN_CASES = json.load(f)


def _build_intake(d: dict) -> Tier1Intake:
    """Convert a raw dict to a Tier1Intake, handling None values gracefully."""
    filtered = {k: v for k, v in d.items() if v is not None}
    return Tier1Intake(**filtered)


# ── Parametrize all 50 cases ──────────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_case(case):
    intake_data = case["input"]
    intake = _build_intake(intake_data)
    verdict, gate_results = run_gates(intake)

    tc_id = case["id"]

    # ── Expected verdict (exact match) ───────────────────────────────────────
    if "expected_verdict" in case:
        assert verdict.verdict.value == case["expected_verdict"], (
            f"{tc_id}: Expected verdict={case['expected_verdict']}, "
            f"got={verdict.verdict.value}. Reason: {verdict.confidence_reason}"
        )

    # ── Expected verdict NOT equal (not this category) ───────────────────────
    if "expected_verdict_not" in case:
        assert verdict.verdict.value != case["expected_verdict_not"], (
            f"{tc_id}: Expected verdict to NOT be {case['expected_verdict_not']}, "
            f"but got it anyway. Reason: {verdict.confidence_reason}"
        )

    # ── Knockout gate check ───────────────────────────────────────────────────
    if "expected_knockout_gate" in case:
        assert verdict.knockout_gate == case["expected_knockout_gate"], (
            f"{tc_id}: Expected knockout at {case['expected_knockout_gate']}, "
            f"got {verdict.knockout_gate}"
        )

    # ── Short-circuit check (max gates evaluated) ─────────────────────────────
    if "max_gates_evaluated" in case:
        assert len(gate_results) <= case["max_gates_evaluated"], (
            f"{tc_id}: Short-circuit failed — expected ≤{case['max_gates_evaluated']} "
            f"gates evaluated, got {len(gate_results)}"
        )

    # ── Flags must contain ────────────────────────────────────────────────────
    if "expected_flags_contain" in case:
        for flag in case["expected_flags_contain"]:
            assert flag in verdict.flags, (
                f"{tc_id}: Expected flag '{flag}' in {verdict.flags}"
            )

    # ── Flags must NOT contain ────────────────────────────────────────────────
    if "expected_flags_not_contain" in case:
        for flag in case["expected_flags_not_contain"]:
            assert flag not in verdict.flags, (
                f"{tc_id}: Expected flag '{flag}' to NOT be in {verdict.flags}"
            )

    # ── Exact flags list ──────────────────────────────────────────────────────
    if "expected_flags" in case and case["expected_flags"] is not None:
        assert set(verdict.flags) == set(case["expected_flags"]), (
            f"{tc_id}: Expected flags={case['expected_flags']}, got={verdict.flags}"
        )

    # ── Indicative numbers present / absent ───────────────────────────────────
    if "expected_indicative_numbers" in case:
        if case["expected_indicative_numbers"]:
            assert verdict.indicative_numbers is not None, (
                f"{tc_id}: Expected indicative numbers to be present"
            )
        else:
            assert verdict.indicative_numbers is None, (
                f"{tc_id}: Expected NO indicative numbers but got {verdict.indicative_numbers}"
            )

    # ── Revenue is a range (low < high, never a point estimate) ──────────────
    if case.get("expected_indicative_is_range"):
        assert verdict.indicative_numbers is not None
        n = verdict.indicative_numbers
        assert n.annual_credits_low < n.annual_credits_high, (
            f"{tc_id}: Credits low ({n.annual_credits_low}) must be < high ({n.annual_credits_high})"
        )
        assert n.revenue_usd_low < n.revenue_usd_high, (
            f"{tc_id}: Revenue low ({n.revenue_usd_low}) must be < high ({n.revenue_usd_high})"
        )

    # ── Low < High for indicative ─────────────────────────────────────────────
    if case.get("expected_indicative_low_lt_high") and verdict.indicative_numbers:
        n = verdict.indicative_numbers
        assert n.annual_credits_low < n.annual_credits_high
        assert n.revenue_usd_low < n.revenue_usd_high

    # ── First issuance year range ─────────────────────────────────────────────
    if "expected_first_issuance_min_ge" in case and verdict.indicative_numbers:
        assert verdict.indicative_numbers.first_issuance_year_min >= case["expected_first_issuance_min_ge"]
    if "expected_first_issuance_max_le" in case and verdict.indicative_numbers:
        assert verdict.indicative_numbers.first_issuance_year_max <= case["expected_first_issuance_max_le"]

    # ── Disclaimer present ────────────────────────────────────────────────────
    if case.get("expected_disclaimer_present"):
        assert verdict.disclaimer and len(verdict.disclaimer) > 10, (
            f"{tc_id}: Disclaimer must be present and non-trivial"
        )

    # ── Next steps non-empty ──────────────────────────────────────────────────
    if case.get("expected_next_steps_non_empty"):
        assert len(verdict.next_steps) > 0, f"{tc_id}: Next steps must be non-empty"

    # ── Alternatives non-empty ────────────────────────────────────────────────
    if case.get("expected_alternatives_non_empty"):
        assert len(verdict.alternatives) > 0, f"{tc_id}: Alternatives must be non-empty"

    # ── Developer questions non-empty ─────────────────────────────────────────
    if case.get("expected_developer_questions_non_empty"):
        assert len(verdict.questions_to_ask_developer) > 0, (
            f"{tc_id}: Developer questions must be non-empty"
        )

    # ── what_we_could_not_check non-empty ────────────────────────────────────
    if case.get("expected_what_we_could_not_check_non_empty"):
        assert len(verdict.what_we_could_not_check) > 0, (
            f"{tc_id}: what_we_could_not_check must be non-empty"
        )


# ── Additional unit tests for individual gates ────────────────────────────────

def test_gate_1_recorded_forest_is_structural_knockout():
    """Recorded Forest Area must always produce a structural knockout at gate_1."""
    intake = Tier1Intake(
        area_ha=50, tenure_type=TenureType.owned,
        land_legal_class=LandLegalClass.recorded_forest,
        existing_tree_cover_pct=40, planting_status=PlantingStatus.not_started,
        would_plant_anyway=False, recent_clearing=False, existing_scheme_registration=False
    )
    verdict, results = run_gates(intake)
    assert verdict.verdict == VerdictCategory.not_eligible_structural
    assert verdict.knockout_gate == "gate_1"
    assert len(results) == 1, "Short-circuit: only gate_1 should be evaluated"


def test_gate_2_short_circuit_stops_at_gate_2():
    """Recent conversion should stop evaluation at gate_2."""
    intake = Tier1Intake(
        area_ha=50, tenure_type=TenureType.owned,
        land_legal_class=LandLegalClass.revenue_fallow,
        existing_tree_cover_pct=3, planting_status=PlantingStatus.not_started,
        would_plant_anyway=False, recent_clearing=True, existing_scheme_registration=False
    )
    verdict, results = run_gates(intake)
    assert verdict.knockout_gate == "gate_2"
    assert len(results) == 2


def test_no_point_estimates_in_yield():
    """Revenue estimates must always be ranges, never point estimates."""
    intake = Tier1Intake(
        area_ha=100, tenure_type=TenureType.owned,
        land_legal_class=LandLegalClass.revenue_fallow,
        existing_tree_cover_pct=3, planting_status=PlantingStatus.not_started,
        would_plant_anyway=False, recent_clearing=False, existing_scheme_registration=False,
        planting_system=PlantingSystem.block_plantation
    )
    verdict, _ = run_gates(intake)
    if verdict.indicative_numbers:
        n = verdict.indicative_numbers
        assert n.annual_credits_low != n.annual_credits_high, "Credits must be a range"
        assert n.revenue_usd_low != n.revenue_usd_high, "Revenue must be a range"


def test_ecological_caution_never_has_indicative_numbers():
    """Ecological caution verdict should not show carbon credit estimates."""
    intake = Tier1Intake(
        area_ha=30, tenure_type=TenureType.owned,
        land_legal_class=LandLegalClass.grassland_scrub,
        existing_tree_cover_pct=2, planting_status=PlantingStatus.not_started,
        would_plant_anyway=False, recent_clearing=False, existing_scheme_registration=False
    )
    verdict, _ = run_gates(intake)
    assert verdict.verdict == VerdictCategory.ecological_caution
    assert verdict.indicative_numbers is None, (
        "Do not show carbon credit estimates on ecological caution — "
        "it would imply planting on ONEs is advisable"
    )


def test_all_verdicts_have_disclaimer():
    """Every verdict, regardless of type, must have a disclaimer."""
    test_inputs = [
        # Structural
        Tier1Intake(area_ha=50, tenure_type=TenureType.disputed, land_legal_class=LandLegalClass.revenue_fallow,
                    existing_tree_cover_pct=3, planting_status=PlantingStatus.not_started,
                    would_plant_anyway=False, recent_clearing=False, existing_scheme_registration=False),
        # Promising
        Tier1Intake(area_ha=600, tenure_type=TenureType.owned, land_legal_class=LandLegalClass.revenue_fallow,
                    existing_tree_cover_pct=2, planting_status=PlantingStatus.not_started,
                    would_plant_anyway=False, planting_legally_mandated=False,
                    already_profitable_without_carbon=False, recent_clearing=False,
                    existing_scheme_registration=False, grazing_use=False),
        # Ecological caution
        Tier1Intake(area_ha=30, tenure_type=TenureType.owned, land_legal_class=LandLegalClass.grassland_scrub,
                    existing_tree_cover_pct=2, planting_status=PlantingStatus.not_started,
                    would_plant_anyway=False, recent_clearing=False, existing_scheme_registration=False),
    ]
    for intake in test_inputs:
        verdict, _ = run_gates(intake)
        assert verdict.disclaimer and "Screening only" in verdict.disclaimer, (
            f"Missing disclaimer for verdict: {verdict.verdict}"
        )
