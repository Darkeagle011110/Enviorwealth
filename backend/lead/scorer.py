from enum import Enum
from typing import Optional
from engine.schemas import VerdictCategory, Verdict

class LeadScore(str, Enum):
    HOT = "Hot"
    QUALIFIED = "Qualified"
    COLD = "Cold"
    UNKNOWN = "Unknown"

def calculate_lead_score(verdict: Verdict, area_ha: Optional[float], has_contact: bool = False) -> LeadScore:
    """
    Deterministically scores a lead based on verdict and scale.
    """
    if not verdict:
        return LeadScore.UNKNOWN
        
    area = area_ha or 0
    cat = verdict.verdict
    
    # Hot: Proceed feasibility + Large scale + no structural knockouts
    if cat == VerdictCategory.promising_proceed_feasibility and area >= 50:
        return LeadScore.HOT
        
    # Qualified: Possible aggregation + minimum scale + contact given
    if cat == VerdictCategory.possible_needs_aggregation and area >= 5:
        # If we demand contact for qualified:
        # if has_contact: return LeadScore.QUALIFIED
        return LeadScore.QUALIFIED
        
    # Cold: Everything else (knockouts, ecological cautions, too small)
    return LeadScore.COLD
