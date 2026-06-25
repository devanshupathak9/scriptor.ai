from typing import TypedDict, Optional


class PipelineState(TypedDict):
    brief: dict              # Original instructor brief
    validation_errors: list  # Input validation errors — empty list means valid
    plan: list               # Planner output: list of segment specs
    segments: list           # Generated + evaluated segments
    script: dict             # Merged complete script object
    script_id: str           # UUID for this script
    rule_report: dict        # Deterministic validation results
    eval_report: dict        # LLM evaluation results
    script_retried: bool     # Whether we already did the whole-script regen pass
    error: Optional[str]     # Fatal error message (pipeline aborts if set)
