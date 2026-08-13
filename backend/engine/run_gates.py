"""
run_gates.py — orchestrates the sequential gate evaluation with short-circuit.

This is the single entry point for the rules engine.
The LLM orchestrator calls this function and receives a Verdict object.
It is NEVER allowed to modify the Verdict object's verdict field.
"""

from __future__ import annotations
from typing import List, Optional, Any

from .schemas import Tier1Intake, GateResult, GateStatus, Verdict
from .verdict import assemble_verdict

# Define dynamic rule operator evaluation
def _evaluate_condition(value: Any, operator: str, target: Any) -> bool:
    if value is None:
        return False
    try:
        if operator == "eq": return value == target
        if operator == "neq": return value != target
        if operator == "gt": return float(value) > float(target)
        if operator == "lt": return float(value) < float(target)
        if operator == "gte": return float(value) >= float(target)
        if operator == "lte": return float(value) <= float(target)
        if operator == "in": return value in target
        if operator == "not_in": return value not in target
    except (ValueError, TypeError):
        pass
    return False

def run_gates(intake: Tier1Intake, rules: List[Any] = []) -> tuple[Verdict, List[GateResult]]:
    """
    Evaluate dynamic gates based on the admin's evaluation rules.
    """
    results: List[GateResult] = []
    
    intake_dict = intake.model_dump(exclude_unset=True)

    for rule in rules:
        # Check condition
        target_field = rule.target_field
        value = intake_dict.get(target_field)
        
        # If field is not present, we can either skip or mark as insufficient. 
        # But for dynamic rules, if it's required it should be in intake.
        if value is None:
            continue
            
        condition_met = _evaluate_condition(value, rule.operator.value, rule.target_value)
        
        if condition_met:
            result = GateResult(
                gate_id=rule.rule_id,
                status=GateStatus(rule.action.value),
                reason=rule.reason,
                flags=rule.flags
            )
            results.append(result)
            
            if result.status == GateStatus.fail_structural:
                break
                
    # If no rules failed or flagged, we add a pass result to ensure verdict works
    if not any(r.status == GateStatus.fail_structural for r in results):
        if not results:
            results.append(GateResult(gate_id="pass_all", status=GateStatus.pass_, reason="All checks passed."))

    verdict = assemble_verdict(results, intake)
    return verdict, results
