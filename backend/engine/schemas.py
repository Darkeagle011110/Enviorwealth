"""
Pydantic schemas for the eligibility rules engine.
These are the canonical data structures passed into gates.py and returned
by verdict.py.  All field names mirror the intake schema from §6 of the brief.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from datetime import date


# ──────────────────────────────────────────────────────────────────────────────
# Tier 1 Intake Schema  (§6.1 of the brief — rapid screen, 6 questions)
# ──────────────────────────────────────────────────────────────────────────────

class TenureType(str, Enum):
    owned = "owned"
    leased = "leased"
    community = "community"
    government = "government"
    disputed = "disputed"


class LandLegalClass(str, Enum):
    revenue_agricultural = "revenue_agricultural"
    revenue_fallow = "revenue_fallow"
    recorded_forest = "recorded_forest"
    community = "community"
    coastal = "coastal"
    urban = "urban"
    mined_industrial = "mined_industrial"
    grassland_scrub = "grassland_scrub"   # Open Natural Ecosystem risk


class PlantingStatus(str, Enum):
    not_started = "not_started"
    planned_this_year = "planned_this_year"
    planted_lt_2yrs = "planted_lt_2yrs"       # < 2 years ago
    planted_2_5yrs = "planted_2_5yrs"         # 2–5 years ago
    planted_gt_5yrs = "planted_gt_5yrs"       # > 5 years ago → likely ineligible


class PlantingSystem(str, Enum):
    block_plantation = "block_plantation"
    agroforestry = "agroforestry"
    mangrove = "mangrove"
    bamboo = "bamboo"
    assisted_natural_regen = "assisted_natural_regen"
    commercial_timber = "commercial_timber"
    orchard = "orchard"
    unknown = "unknown"


class Tier1Intake(BaseModel):
    """
    Tier 1 rapid screen — 6 core questions. Under 2 minutes to complete.
    All fields optional to support progressive collection (gate evaluation
    returns insufficient_info if a required field is missing).
    """
    area_ha: Optional[float] = Field(None, ge=0, description="Total land area in hectares")
    tenure_type: Optional[TenureType] = None
    land_legal_class: Optional[LandLegalClass] = None
    existing_tree_cover_pct: Optional[float] = Field(None, ge=0, le=100,
        description="Estimated existing canopy cover as a percentage")
    planting_status: Optional[PlantingStatus] = None
    would_plant_anyway: Optional[bool] = Field(None,
        description="Would you plant trees without any carbon payment?")

    # Additionality helpers (auto-derived or asked in conversation)
    planting_legally_mandated: Optional[bool] = None
    already_profitable_without_carbon: Optional[bool] = None

    # Land-use history helpers (Tier 2 — optional at Tier 1)
    land_use_10yr_ago: Optional[str] = None
    last_clearing_year: Optional[int] = None
    recent_clearing: Optional[bool] = None         # True = clearing in last 10 yrs

    # Tenure helpers
    lease_years_remaining: Optional[float] = None  # for leased land
    fra_claim_flag: Optional[bool] = None
    existing_scheme_registration: Optional[bool] = None  # Gate 9

    # Planting details
    planting_system: Optional[PlantingSystem] = None
    grazing_use: Optional[bool] = None             # affects ecological caution

    # Tier-2 fields (P1 Quality & Brief Compliance)
    fuelwood_collection: Optional[bool] = None
    ntfp_collection: Optional[bool] = None
    co_owners_count: Optional[int] = None
    tenant_present_flag: Optional[bool] = None
    fire_history: Optional[str] = None
    flood_exposure: Optional[str] = None
    grazing_pressure: Optional[str] = None
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    cultivation_displacement: Optional[bool] = None

    @field_validator("area_ha")
    @classmethod
    def area_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("area_ha must be positive")
        return v


# ──────────────────────────────────────────────────────────────────────────────
# Gate Result
# ──────────────────────────────────────────────────────────────────────────────

class GateStatus(str, Enum):
    pass_ = "pass"              # gate passed — continue
    fail_structural = "fail_structural"   # hard knockout — stop evaluation
    flag = "flag"               # soft flag — continue but note the risk
    insufficient_info = "insufficient_info"  # need more data


@dataclass
class GateResult:
    gate_id: str                           # e.g. "gate_1"
    status: GateStatus
    reason: str                            # human-readable explanation
    redirect: Optional[str] = None        # e.g. "Contact state forest department"
    flags: List[str] = field(default_factory=list)  # named risk flags


# ──────────────────────────────────────────────────────────────────────────────
# Verdict
# ──────────────────────────────────────────────────────────────────────────────

class VerdictCategory(str, Enum):
    not_eligible_structural = "NOT_ELIGIBLE_STRUCTURAL"
    unlikely_economic = "UNLIKELY_ECONOMIC"
    possible_needs_aggregation = "POSSIBLE_NEEDS_AGGREGATION"
    promising_proceed_feasibility = "PROMISING_PROCEED_FEASIBILITY"
    insufficient_information = "INSUFFICIENT_INFORMATION"
    ecological_caution = "ECOLOGICAL_CAUTION"


class IndicativeNumbers(BaseModel):
    annual_credits_low: Optional[float] = None   # net tCO2e/yr
    annual_credits_high: Optional[float] = None
    revenue_usd_low: Optional[float] = None
    revenue_usd_high: Optional[float] = None
    first_issuance_year_min: Optional[int] = None
    first_issuance_year_max: Optional[int] = None
    note: str = "Indicative screening figures only — not for project documentation"
    disclaimer: str = (
        "Net of buffer withholding (15% default). Revenue before aggregator/developer fees. "
        "Verify against primary methodology before any financial decision."
    )


class Verdict(BaseModel):
    verdict: VerdictCategory
    confidence: int
    confidence_reason: str
    knockout_gate: Optional[str] = None
    flags: List[str] = []
    gate_results: List[dict] = []
    indicative_numbers: Optional[IndicativeNumbers] = None
    what_we_could_not_check: List[str] = []
    next_steps: List[str] = []
    alternatives: List[str] = []
    questions_to_ask_developer: List[str] = []
    methodology_note: Optional[str] = None
    disclaimer: str = (
        "Screening only — not a legal, financial or investment determination. "
        "Only a VVB and the standard body can decide whether a project is eligible."
    )
