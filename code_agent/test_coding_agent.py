#!/usr/bin/env python3
"""
Standalone test script for the Coding Agent.

Usage:
    python test_coding_agent.py
"""

import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from coding_agent import coding_agent


def test_binary_search():
    """Test 1: Generate a simple Binary Search implementation."""
    print("=" * 80)
    print("TEST 1: Binary Search Implementation")
    print("=" * 80)

    initial_state = {
        "language": "python",
        "version": "3.11",
        "task": "Write a binary search function that takes a sorted list and a target value, returns the index if found or -1 if not found.",
        "dependencies": [],
        "constraints": ["Readable for beginners", "Include docstring"],
        "expected_output": None,
        # Processing fields
        "understood_task": {},
        "generated_code": "",
        "detected_dependencies": [],
        "all_dependencies": [],
        # Sandbox fields
        "sandbox_path": None,
        "venv_path": None,
        "requirements_txt": "",
        # Execution fields
        "execution_logs": "",
        "exit_code": None,
        "execution_time": None,
        "runtime_errors": "",
        # Testing fields
        "generated_tests": "",
        "test_results": {},
        "tests_passed": False,
        # Control
        "retry_count": 0,
        "status": "initialized",
        "error": None,
        # Output
        "final_code": "",
        "final_review": {},
    }

    result = coding_agent.invoke(initial_state)

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Status: {result['status']}")
    print(f"Retry Count: {result['retry_count']}")
    print(f"Tests Passed: {result.get('tests_passed', False)}")

    if result["status"] == "success":
        print("\n--- FINAL CODE ---")
        print(result["final_code"])
        print("\n--- DEPENDENCIES ---")
        print(result["requirements_txt"] or "None")
        print("\n--- REVIEW ---")
        review = result.get("final_review", {})
        print(f"Overall Score: {review.get('overall', 'N/A')}")
        print(f"Passed Review: {review.get('pass', 'N/A')}")
    else:
        print(f"\n--- ERROR ---")
        print(result.get("error", "Unknown error"))
        print(f"\n--- RUNTIME ERRORS ---")
        print(result.get("runtime_errors", "None"))

    return result


def test_data_processing():
    """Test 2: Generate a data processing script with dependencies."""
    print("\n" + "=" * 80)
    print("TEST 2: Data Processing with Pandas")
    print("=" * 80)

    initial_state = {
        "language": "python",
        "version": "3.11",
        "task": """
Write a script that:
1. Creates a sample DataFrame with columns: name, age, salary
2. Filters rows where age > 30
3. Calculates the average salary
4. Prints the result
        """.strip(),
        "dependencies": ["pandas"],
        "constraints": ["Use pandas", "Print clear output"],
        "expected_output": None,
        # Processing fields
        "understood_task": {},
        "generated_code": "",
        "detected_dependencies": [],
        "all_dependencies": [],
        # Sandbox fields
        "sandbox_path": None,
        "venv_path": None,
        "requirements_txt": "",
        # Execution fields
        "execution_logs": "",
        "exit_code": None,
        "execution_time": None,
        "runtime_errors": "",
        # Testing fields
        "generated_tests": "",
        "test_results": {},
        "tests_passed": False,
        # Control
        "retry_count": 0,
        "status": "initialized",
        "error": None,
        # Output
        "final_code": "",
        "final_review": {},
    }

    result = coding_agent.invoke(initial_state)

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Status: {result['status']}")
    print(f"Retry Count: {result['retry_count']}")

    if result["status"] == "success":
        print("\n--- FINAL CODE ---")
        print(result["final_code"])
        print("\n--- DEPENDENCIES ---")
        print(result["requirements_txt"])
        print("\n--- EXECUTION OUTPUT ---")
        print(result.get("execution_logs", ""))
    else:
        print(f"\n--- ERROR ---")
        print(result.get("error", "Unknown error"))

    return result


def test_simple_hello():
    """Test 3: Simplest possible test - Hello World."""
    print("\n" + "=" * 80)
    print("TEST 3: Hello World")
    print("=" * 80)

    initial_state = {
        "language": "python",
        "version": "3.11",
        "task": "Write a script that prints 'Hello, Coding Agent!' to the console.",
        "dependencies": [],
        "constraints": [],
        "expected_output": "Hello, Coding Agent!",
        # Processing fields
        "understood_task": {},
        "generated_code": "",
        "detected_dependencies": [],
        "all_dependencies": [],
        # Sandbox fields
        "sandbox_path": None,
        "venv_path": None,
        "requirements_txt": "",
        # Execution fields
        "execution_logs": "",
        "exit_code": None,
        "execution_time": None,
        "runtime_errors": "",
        # Testing fields
        "generated_tests": "",
        "test_results": {},
        "tests_passed": False,
        # Control
        "retry_count": 0,
        "status": "initialized",
        "error": None,
        # Output
        "final_code": "",
        "final_review": {},
    }

    result = coding_agent.invoke(initial_state)

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Status: {result['status']}")
    print(f"Output matches expected: {'Hello, Coding Agent!' in result.get('execution_logs', '')}")

    if result["status"] == "success":
        print("\n--- FINAL CODE ---")
        print(result["final_code"])
    else:
        print(f"\n--- ERROR ---")
        print(result.get("error", "Unknown error"))

    return result


if __name__ == "__main__":
    print("\n🤖 CODING AGENT TEST SUITE\n")

    # Run tests
    test_simple_hello()
    test_binary_search()
    # test_data_processing()  # Uncomment to test with pandas

    print("\n" + "=" * 80)
    print("✅ TEST SUITE COMPLETE")
    print("=" * 80)
