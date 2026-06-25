from typing import TypedDict, List


class CodingAgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    task: str
    language: str
    version: str
    dependencies: List[str]
    constraints: List[str]
    expected_output: str

    # ── Task analysis ──────────────────────────────────────────────────────────
    task_analysis: dict

    # ── Generated artifacts ────────────────────────────────────────────────────
    generated_code: str
    llm_requirements: List[str]   # what the LLM suggested
    all_requirements: List[str]   # merged: user + LLM + auto-detected
    generated_tests: str

    # ── Sandbox ────────────────────────────────────────────────────────────────
    sandbox_dir: str
    venv_python: str
    venv_pip: str
    venv_pytest: str

    # ── Execution ──────────────────────────────────────────────────────────────
    execution_output: str
    execution_errors: str
    execution_success: bool
    execution_time: float

    # ── Tests ──────────────────────────────────────────────────────────────────
    test_output: str
    test_errors: str
    tests_passed: bool

    # ── Repair state ───────────────────────────────────────────────────────────
    phase: str              # "execution" | "testing"
    code_retry_count: int
    test_retry_count: int

    # ── Review ─────────────────────────────────────────────────────────────────
    review_notes: str
    review_approved: bool

    # ── Final ──────────────────────────────────────────────────────────────────
    status: str             # "success" | "failure"
    error_message: str
