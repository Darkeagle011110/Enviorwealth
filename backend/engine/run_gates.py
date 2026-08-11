"""
run_gates.py — orchestrates the sequential gate evaluation with short-circuit.

This is the single entry point for the rules engine.
The LLM orchestrator calls this function and receives a Verdict object.
It is NEVER allowed to modify the Verdict object's verdict field.
"""

from __future__ import annotations
from typing import List

from .schemas import Tier1Intake, GateResult, GateStatus, Verdict
from .gates import GATES
from .verdict import assemble_verdict


def run_gates(intake: Tier1Intake) -> tuple[Verdict, List[GateResult]]:
    """
    Evaluate all 10 gates in sequence with short-circuit on fail_structural.

    Returns:
        (Verdict, List[GateResult]) — the final verdict and all gate results
        evaluated before the short-circuit (or all 10 if no knockout).
    """
    results: List[GateResult] = []

    for gate_fn in GATES:
        result = gate_fn(intake)
        results.append(result)

        # Short-circuit: the brief explicitly says "failing gate 1 makes
        # gates 4–10 irrelevant and asking twenty more questions after a
        # knockout is a bad user experience."
        if result.status == GateStatus.fail_structural:
            break

    verdict = assemble_verdict(results, intake)
    return verdict, results
