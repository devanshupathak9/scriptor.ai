"""Prompt templates for the Coding Agent."""

TASK_UNDERSTANDING_PROMPT = """
You are an expert software engineer analyzing a coding task.

=== TASK ===
Language: {language}
Version: {version}
Task: {task}
Explicit Dependencies: {dependencies}
Constraints: {constraints}
Expected Output: {expected_output}

=== YOUR JOB ===
Analyze this task and return a structured understanding:
1. What is the core problem to solve?
2. What is the complexity level (beginner/intermediate/advanced)?
3. What are the key components needed?
4. Are there any edge cases to handle?
5. What libraries/modules will likely be needed?

Return ONLY valid JSON:
{{
  "problem_summary": "Brief description of what needs to be built",
  "complexity": "beginner|intermediate|advanced",
  "key_components": ["component1", "component2"],
  "edge_cases": ["case1", "case2"],
  "suggested_dependencies": ["dep1", "dep2"]
}}
"""

CODE_GENERATION_PROMPT = """
You are an expert {language} programmer (version {version}).

=== TASK ===
{task}

=== REQUIREMENTS ===
{requirements}

=== CONSTRAINTS ===
{constraints}

=== YOUR JOB ===
Write clean, working {language} code that:
1. Solves the problem completely
2. Works with {language} version {version}
3. Follows best practices
4. Includes helpful comments
5. Handles edge cases
6. Is {complexity}-friendly

Return ONLY valid JSON:
{{
  "code": "complete working code as a string",
  "dependencies": ["list", "of", "required", "packages"],
  "explanation": "brief explanation of the approach",
  "entry_point": "main function or entry point (e.g., 'main()' or 'if __name__ == ...')"
}}

IMPORTANT: The code must be complete and executable. Include all imports at the top.
"""

CODE_REPAIR_PROMPT = """
You are an expert {language} debugger (version {version}).

=== ORIGINAL CODE ===
{code}

=== RUNTIME ERROR ===
Exit Code: {exit_code}
Error Output:
{error_output}

Execution Logs:
{execution_logs}

=== INSTALLED DEPENDENCIES ===
{dependencies}

=== YOUR JOB ===
Fix the code to resolve the runtime error. DO NOT change the intended functionality.

Common issues to check:
1. Missing imports
2. Syntax errors for {version}
3. Incorrect function calls
4. Version-specific incompatibilities
5. Missing dependencies

Return ONLY valid JSON:
{{
  "fixed_code": "corrected code as a string",
  "changes_made": "brief description of what was fixed",
  "additional_dependencies": ["any", "new", "packages", "needed"]
}}
"""

TEST_GENERATION_PROMPT = """
You are an expert test engineer for {language}.

=== CODE TO TEST ===
{code}

=== TASK DESCRIPTION ===
{task}

=== YOUR JOB ===
Generate comprehensive test cases using pytest (for Python) or equivalent:
1. Happy path tests
2. Edge cases
3. Invalid input handling
4. Boundary conditions

CRITICAL: The test file MUST import the functions/classes from main.py.
For Python, start your test file with: `from main import *` or import specific functions.

The tests should be runnable standalone when main.py is in the same directory.

Return ONLY valid JSON:
{{
  "test_code": "complete test file as a string",
  "test_dependencies": ["pytest", "any", "other", "test", "libs"],
  "test_count": 5
}}

IMPORTANT:
- Include `from main import <function_names>` at the top of the test file
- Tests should use assert statements or pytest assertions
- All necessary imports must be present
"""

CODE_REVIEW_PROMPT = """
You are a senior code reviewer evaluating {language} code.

=== CODE ===
{code}

=== CRITERIA ===
1. Readability (1-5)
2. Correctness (1-5)
3. Best practices (1-5)
4. Comments quality (1-5)
5. Version compatibility with {version} (1-5)
6. {complexity}-friendliness (1-5)

=== YOUR JOB ===
Review the code and score it. Be critical but fair.

Return ONLY valid JSON:
{{
  "scores": {{
    "readability": 4.5,
    "correctness": 5.0,
    "best_practices": 4.0,
    "comments": 4.5,
    "version_compatibility": 5.0,
    "level_friendliness": 4.0
  }},
  "overall": 4.5,
  "pass": true,
  "feedback": "specific improvements if overall < 4.0, otherwise empty string",
  "strengths": ["what the code does well"],
  "suggestions": ["optional improvements"]
}}
"""
