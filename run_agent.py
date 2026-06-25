#!/usr/bin/env python3
"""
Standalone test runner for the Coding Agent.

Usage:
    cd scriptor_backend
    python run_agent.py                                     # built-in example
    python run_agent.py "write a bubble sort"               # plain text task
    python run_agent.py '{"task": "...", "version": "3.13"}'  # JSON input

Requires OPENAI_API_KEY in .env or environment.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from coding_agent import run_agent


EXAMPLES = [
    {
        "task": "Write a Binary Search implementation",
        "version": "3.13",
        "dependencies": [],
        "constraints": ["Readable for beginners", "Include a demo in __main__"],
    },
    {
        "task": (
            "Write a function that finds all prime numbers up to N "
            "using the Sieve of Eratosthenes"
        ),
        "version": "3.13",
        "constraints": ["Handle edge cases (N < 2)"],
    },
    {
        "task": "Parse a CSV string and return a list of dicts (one per row)",
        "version": "3.13",
        "constraints": ["No external packages"],
    },
    {
        "task": "Implement a stack with push, pop, peek, and is_empty operations",
        "version": "3.13",
        "constraints": ["Use a class", "Raise ValueError on pop/peek of empty stack"],
    },
]


def _print_section(title: str, content: str) -> None:
    bar = "─" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)
    print(content)


def main() -> None:
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        try:
            task_input = json.loads(arg)
        except json.JSONDecodeError:
            # Treat bare string as task description
            task_input = {"task": arg}
    else:
        task_input = EXAMPLES[0]

    print("\n" + "═" * 60)
    print("  CODING AGENT")
    print("═" * 60)
    print(f"  Task:        {task_input.get('task', '')[:72]}")
    print(f"  Python:      {task_input.get('version', '3.13')}")
    print(f"  Constraints: {task_input.get('constraints', [])}")
    print(f"  Deps:        {task_input.get('dependencies', [])}")
    print("═" * 60)

    try:
        result = run_agent(
            task=task_input.get("task", ""),
            language=task_input.get("language", "python"),
            version=task_input.get("version", "3.13"),
            dependencies=task_input.get("dependencies", []),
            constraints=task_input.get("constraints", []),
            expected_output=task_input.get("expected_output", ""),
        )
    except ValueError as e:
        # Handle version validation error
        print(f"\n✗  VERSION ERROR\n")
        print(f"{str(e)}\n")
        return

    # ── Output ────────────────────────────────────────────────────────────────
    if result["status"] == "success":
        _print_section("GENERATED CODE  (main.py)", result["code"])

        if result["tests"]:
            _print_section("GENERATED TESTS  (test_main.py)", result["tests"])

        if result["requirements_txt"]:
            _print_section("REQUIREMENTS.TXT", result["requirements_txt"])

        if result["review_notes"]:
            _print_section("CODE REVIEW", result["review_notes"])

        if result["execution_output"].strip():
            _print_section("EXECUTION OUTPUT", result["execution_output"].strip())

    else:
        print(f"\n✗  FAILED\n{result['error_message'][:600]}")

    print(f"\n  Execution : {'✓' if result['execution_passed'] else '✗'}")
    print(f"  Tests     : {'✓' if result['tests_passed'] else '✗'}")
    print(f"  Sandbox   : {result['sandbox_dir']}")
    print()


if __name__ == "__main__":
    main()
