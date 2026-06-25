"""State definition for the Coding Agent."""

from typing import TypedDict, Optional, List, Dict


class CodingAgentState(TypedDict):
    # Input fields
    language: str                    # Programming language (e.g., "python")
    version: str                     # Language version (e.g., "3.11")
    task: str                        # User's problem statement
    dependencies: List[str]          # Optional explicit dependencies
    constraints: List[str]           # Optional constraints (e.g., "beginner-friendly")
    expected_output: Optional[str]   # Optional expected output for validation

    # Processing fields
    understood_task: Dict            # Parsed task understanding
    generated_code: str              # Current version of generated code
    detected_dependencies: List[str] # Auto-detected imports
    all_dependencies: List[str]      # Combined dependencies list

    # Sandbox fields
    sandbox_path: Optional[str]      # Path to isolated workspace
    venv_path: Optional[str]        # Path to virtual environment
    requirements_txt: str            # Generated requirements.txt content

    # Execution fields
    execution_logs: str              # Combined stdout/stderr
    exit_code: Optional[int]         # Execution exit code
    execution_time: Optional[float]  # Time taken to execute
    runtime_errors: str              # Error messages and stack traces

    # Testing fields
    generated_tests: str             # Test code
    test_results: Dict               # Test execution results
    tests_passed: bool               # Whether all tests passed

    # Control flow
    retry_count: int                 # Number of repair attempts
    status: str                      # Current status (generating, executing, testing, success, failed)
    error: Optional[str]             # Fatal error message

    # Final output
    final_code: str                  # Verified code ready for delivery
    final_review: Dict               # Code quality review results
