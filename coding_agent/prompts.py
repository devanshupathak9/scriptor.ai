# All LLM prompt templates.
# Use .format(**kwargs) — escape literal braces as {{ and }}.

UNDERSTAND_TASK_PROMPT = """\
Analyze this coding task and return a structured breakdown.

Task: {task}
Language: {language} {version}
User-specified dependencies: {dependencies}
Constraints: {constraints}
Expected output: {expected_output}

IMPORTANT: Code will be generated specifically for Python {version}.
This is NOT a suggestion - it's a hard requirement. Only use syntax and features
available in Python {version}. Supported versions are: 3.10, 3.11, 3.12, 3.13.

Return ONLY valid JSON — no markdown fences:
{{
  "summary": "one-line summary of what to build",
  "key_components": ["function or class names to implement"],
  "algorithms": ["relevant algorithms or data structures"],
  "edge_cases": ["edge cases to handle"],
  "complexity": "simple|medium|complex",
  "version_notes": "Python {version}-specific considerations or features to use/avoid"
}}"""


GENERATE_CODE_PROMPT = """\
Write complete, working Python {version} code for this task.

Task: {task}
Analysis: {task_analysis}
Constraints: {constraints}
Required dependencies: {dependencies}

CRITICAL VERSION REQUIREMENT:
The code MUST be compatible with Python {version} ONLY.
- Check syntax compatibility with {version}
- Use only stdlib modules available in {version}
- If using f-strings, match expressions, or other version-specific features, verify they exist in {version}
- This is a HARD requirement - code that doesn't run in {version} will fail validation

Rules:
- All logic must live in named functions or classes — no bare top-level script code
- Include a working `if __name__ == "__main__":` block that demonstrates usage and prints output
- Use only Python {version}-compatible syntax and features
- Handle the edge cases listed in the analysis
- Keep inline comments minimal — only where non-obvious

Return ONLY valid JSON — no markdown fences. Use \\n for newlines inside the "code" string:
{{
  "code": "import ...\\n\\ndef my_function(...):\\n    ...",
  "requirements": ["pip-package-name-1", "pip-package-name-2"]
}}"""


REPAIR_EXECUTION_PROMPT = """\
A Python {version} script failed at runtime. Fix the error.

=== CURRENT CODE ===
{code}

=== ERROR OUTPUT ===
{error}

Context:
- Task: {task}
- Installed packages: {requirements}
- Repair attempt: {attempt} of {max_attempts}

Fix the specific error without restructuring working code:
- ModuleNotFoundError → add the missing package to requirements
- SyntaxError / NameError → fix the offending line
- TypeError / ValueError → fix the logic or add input validation
- ImportError → correct the import or add the package

Return ONLY valid JSON — no markdown fences. Use \\n for newlines:
{{
  "code": "fixed Python source",
  "requirements": ["updated", "package", "list"],
  "explanation": "what you changed and why"
}}"""


REPAIR_TEST_PROMPT = """\
Pytest tests are failing. Fix the implementation code (not the tests) so tests pass.

=== CURRENT CODE (main.py) ===
{code}

=== TEST FAILURE OUTPUT ===
{error}

Context:
- Task: {task}
- Python version: {version}
- Installed packages: {requirements}
- Repair attempt: {attempt} of {max_attempts}

Read the failure output carefully:
- If a test calls a function that doesn't exist, add that function
- If a test asserts a wrong return value, fix the logic
- If there's an import error, fix the module structure
- Do NOT change function signatures that the tests already call correctly

Return ONLY valid JSON — no markdown fences. Use \\n for newlines:
{{
  "code": "fixed Python source",
  "requirements": ["updated", "package", "list"],
  "explanation": "what you changed"
}}"""


GENERATE_TESTS_PROMPT = """\
Write pytest tests for the following Python {version} code.

=== CODE (saved as main.py, importable as `main`) ===
{code}

Task: {task}
Available packages: {requirements}

Write tests that:
- Import from the `main` module: `from main import <function_name>` or `import main`
- Use pytest conventions: `test_` prefix, plain `assert` statements
- Cover: happy path, boundary/edge cases, invalid inputs (use `pytest.raises` where relevant)
- Are self-contained — no external files, no shared mutable state between tests

Return ONLY valid JSON — no markdown fences. Use \\n for newlines:
{{
  "tests": "import pytest\\nfrom main import ...\\n\\ndef test_..."
}}"""


CODE_REVIEW_PROMPT = """\
Review this Python {version} code for quality.

=== CODE ===
{code}

Task: {task}
Test results: {test_results}
Constraints: {constraints}

Evaluate on:
1. Readability — clear names, logical structure
2. Correctness — handles edge cases from the task
3. Python {version} best practices
4. Beginner friendliness (if the task targets beginners)

Return ONLY valid JSON — no markdown fences:
{{
  "approved": true,
  "score": 4.2,
  "notes": "brief overall quality summary",
  "suggestions": ["optional improvement 1", "optional improvement 2"]
}}"""
