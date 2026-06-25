#!/usr/bin/env python3
"""
Simple test for the Coding Agent - validates core functionality.
"""

from dotenv import load_dotenv
load_dotenv()

from coding_agent import coding_agent


def test_hello_world():
    """Test basic code generation without tests."""
    print("\n" + "="*80)
    print("TEST: Hello World (Simple)")
    print("="*80)

    initial_state = {
        "language": "python",
        "version": "3.11",
        "task": "Write a function called greet(name) that returns 'Hello, {name}!'. Then call it with 'World' and print the result.",
        "dependencies": [],
        "constraints": ["Simple and clean"],
        "expected_output": "Hello, World!",
        "understood_task": {},
        "generated_code": "",
        "detected_dependencies": [],
        "all_dependencies": [],
        "sandbox_path": None,
        "venv_path": None,
        "requirements_txt": "",
        "execution_logs": "",
        "exit_code": None,
        "execution_time": None,
        "runtime_errors": "",
        "generated_tests": "",
        "test_results": {},
        "tests_passed": False,
        "retry_count": 0,
        "status": "initialized",
        "error": None,
        "final_code": "",
        "final_review": {},
    }

    result = coding_agent.invoke(initial_state)

    print("\n" + "="*80)
    print("RESULT")
    print("="*80)
    print(f"Status: {result['status']}")
    print(f"Exit Code: {result.get('exit_code', 'N/A')}")
    print(f"Retry Count: {result['retry_count']}")

    if result["status"] == "success":
        print("\n✓ Code executed successfully!")
        print("\n--- GENERATED CODE ---")
        print(result["final_code"])
        print("\n--- EXECUTION OUTPUT ---")
        print(result.get("execution_logs", ""))
        print("\n--- CODE REVIEW ---")
        review = result.get("final_review", {})
        print(f"Overall Score: {review.get('overall', 'N/A'):.1f}/5.0")
        return True
    else:
        print("\n✗ Failed")
        print(f"Error: {result.get('error', 'Unknown')}")
        print(f"\n--- RUNTIME ERRORS ---")
        print(result.get("runtime_errors", ""))
        return False


def test_fibonacci():
    """Test slightly more complex function."""
    print("\n" + "="*80)
    print("TEST: Fibonacci Function")
    print("="*80)

    initial_state = {
        "language": "python",
        "version": "3.11",
        "task": """
Write a function fibonacci(n) that returns the nth Fibonacci number.
Use iteration (not recursion) for better performance.
Then call it with n=10 and print the result.
        """.strip(),
        "dependencies": [],
        "constraints": ["Use iteration", "Include a simple example call"],
        "expected_output": None,
        "understood_task": {},
        "generated_code": "",
        "detected_dependencies": [],
        "all_dependencies": [],
        "sandbox_path": None,
        "venv_path": None,
        "requirements_txt": "",
        "execution_logs": "",
        "exit_code": None,
        "execution_time": None,
        "runtime_errors": "",
        "generated_tests": "",
        "test_results": {},
        "tests_passed": False,
        "retry_count": 0,
        "status": "initialized",
        "error": None,
        "final_code": "",
        "final_review": {},
    }

    result = coding_agent.invoke(initial_state)

    print("\n" + "="*80)
    print("RESULT")
    print("="*80)
    print(f"Status: {result['status']}")
    print(f"Retry Count: {result['retry_count']}")

    if result["status"] == "success":
        print("\n✓ Success!")
        print("\n--- CODE ---")
        print(result["final_code"])
        print("\n--- OUTPUT ---")
        print(result.get("execution_logs", ""))
        return True
    else:
        print(f"\n✗ Failed: {result.get('error', 'Unknown')}")
        return False


if __name__ == "__main__":
    print("\n🤖 CODING AGENT - SIMPLE TESTS\n")

    results = []
    results.append(("Hello World", test_hello_world()))
    results.append(("Fibonacci", test_fibonacci()))

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} passed")
