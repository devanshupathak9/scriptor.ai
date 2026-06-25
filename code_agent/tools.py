"""Tool functions for sandbox creation, execution, and file operations."""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional


SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.12"]
MAX_EXECUTION_TIME = 30  # seconds


def detect_imports(code: str, language: str) -> List[str]:
    """
    Auto-detect imports from code.
    Currently supports Python only.
    """
    if language.lower() != "python":
        return []

    imports = set()
    lines = code.split("\n")

    for line in lines:
        line = line.strip()
        # Match: import foo
        match = re.match(r"^import\s+([\w\.]+)", line)
        if match:
            pkg = match.group(1).split(".")[0]
            imports.add(pkg)

        # Match: from foo import bar
        match = re.match(r"^from\s+([\w\.]+)\s+import", line)
        if match:
            pkg = match.group(1).split(".")[0]
            imports.add(pkg)

    # Filter out stdlib modules (basic heuristic)
    stdlib = {
        "os", "sys", "re", "json", "time", "datetime", "math", "random",
        "collections", "itertools", "functools", "pathlib", "typing",
        "unittest", "logging", "subprocess", "threading", "multiprocessing",
        "io", "csv", "urllib", "http", "socket", "email", "tempfile",
    }

    external = imports - stdlib
    return sorted(external)


def map_import_to_package(import_name: str) -> str:
    """
    Map import names to pip package names.
    E.g., 'sklearn' -> 'scikit-learn'
    """
    mapping = {
        "sklearn": "scikit-learn",
        "cv2": "opencv-python",
        "PIL": "Pillow",
        "yaml": "pyyaml",
    }
    return mapping.get(import_name, import_name)


def create_sandbox(language: str, version: str) -> Tuple[str, str]:
    """
    Create an isolated sandbox with a virtual environment.
    Returns (sandbox_path, venv_path).
    """
    if language.lower() != "python":
        raise ValueError(f"Unsupported language: {language}")

    if version not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(
            f"Unsupported Python version: {version}. "
            f"Supported: {SUPPORTED_PYTHON_VERSIONS}"
        )

    # Create temporary directory
    sandbox_path = tempfile.mkdtemp(prefix="coding_agent_")
    venv_path = os.path.join(sandbox_path, ".venv")

    # Determine Python executable
    python_cmd = f"python{version}"

    # Check if the version is available
    try:
        subprocess.run(
            [python_cmd, "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to python3
        python_cmd = "python3"

    # Create virtual environment
    try:
        subprocess.run(
            [python_cmd, "-m", "venv", venv_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        shutil.rmtree(sandbox_path)
        raise RuntimeError(f"Failed to create venv: {e.stderr.decode()}")

    print(f"[create_sandbox] Created sandbox at {sandbox_path} with Python {version}")
    return sandbox_path, venv_path


def install_dependencies(
    venv_path: str,
    dependencies: List[str],
) -> Tuple[bool, str]:
    """
    Install dependencies in the virtual environment.
    Returns (success, logs).
    """
    if not dependencies:
        return True, "No dependencies to install."

    # Map import names to package names
    packages = [map_import_to_package(dep) for dep in dependencies]

    pip_path = os.path.join(venv_path, "bin", "pip")
    if not os.path.exists(pip_path):
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe")  # Windows

    try:
        result = subprocess.run(
            [pip_path, "install"] + packages,
            capture_output=True,
            timeout=120,
            text=True,
        )
        logs = result.stdout + result.stderr
        success = result.returncode == 0

        if success:
            print(f"[install_dependencies] Installed: {', '.join(packages)}")
        else:
            print(f"[install_dependencies] Failed: {logs}")

        return success, logs

    except subprocess.TimeoutExpired:
        return False, "Dependency installation timed out after 120s."
    except Exception as e:
        return False, f"Installation error: {str(e)}"


def execute_code(
    sandbox_path: str,
    venv_path: str,
    code: str,
    timeout: int = MAX_EXECUTION_TIME,
) -> Dict:
    """
    Execute code in the sandbox.
    Returns dict with exit_code, stdout, stderr, execution_time.
    """
    # Write code to file
    code_file = os.path.join(sandbox_path, "main.py")
    Path(code_file).write_text(code, encoding="utf-8")

    # Python executable in venv
    python_path = os.path.join(venv_path, "bin", "python")
    if not os.path.exists(python_path):
        python_path = os.path.join(venv_path, "Scripts", "python.exe")  # Windows

    start_time = time.time()

    try:
        result = subprocess.run(
            [python_path, code_file],
            capture_output=True,
            timeout=timeout,
            text=True,
            cwd=sandbox_path,
        )
        execution_time = time.time() - start_time

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": round(execution_time, 2),
            "timeout": False,
        }

    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "execution_time": timeout,
            "timeout": True,
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution error: {str(e)}",
            "execution_time": 0,
            "timeout": False,
        }


def execute_tests(
    sandbox_path: str,
    venv_path: str,
    test_code: str,
    main_code: str,
) -> Dict:
    """
    Execute test code in the sandbox.
    Returns dict with test results.
    """
    # Write main code
    code_file = os.path.join(sandbox_path, "main.py")
    Path(code_file).write_text(main_code, encoding="utf-8")

    # Write test code
    test_file = os.path.join(sandbox_path, "test_main.py")
    Path(test_file).write_text(test_code, encoding="utf-8")

    # Python executable
    python_path = os.path.join(venv_path, "bin", "python")
    if not os.path.exists(python_path):
        python_path = os.path.join(venv_path, "Scripts", "python.exe")

    # Try pytest first, fallback to unittest
    pip_path = os.path.join(venv_path, "bin", "pip")
    if not os.path.exists(pip_path):
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe")

    # Install pytest if not present
    subprocess.run(
        [pip_path, "install", "pytest"],
        capture_output=True,
        timeout=30,
    )

    pytest_path = os.path.join(venv_path, "bin", "pytest")
    if not os.path.exists(pytest_path):
        pytest_path = os.path.join(venv_path, "Scripts", "pytest.exe")

    try:
        result = subprocess.run(
            [pytest_path, test_file, "-v"],
            capture_output=True,
            timeout=MAX_EXECUTION_TIME,
            text=True,
            cwd=sandbox_path,
        )

        passed = result.returncode == 0
        output = result.stdout + result.stderr

        # Parse pytest output for pass/fail counts
        passed_count = len(re.findall(r"PASSED", output))
        failed_count = len(re.findall(r"FAILED", output))

        return {
            "passed": passed,
            "exit_code": result.returncode,
            "output": output,
            "passed_count": passed_count,
            "failed_count": failed_count,
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "exit_code": -1,
            "output": "Tests timed out",
            "passed_count": 0,
            "failed_count": 0,
        }
    except Exception as e:
        return {
            "passed": False,
            "exit_code": -1,
            "output": f"Test execution error: {str(e)}",
            "passed_count": 0,
            "failed_count": 0,
        }


def cleanup_sandbox(sandbox_path: str) -> None:
    """Remove the sandbox directory."""
    if sandbox_path and os.path.exists(sandbox_path):
        try:
            shutil.rmtree(sandbox_path)
            print(f"[cleanup_sandbox] Removed {sandbox_path}")
        except Exception as e:
            print(f"[cleanup_sandbox] Failed to remove {sandbox_path}: {e}")


def generate_requirements_txt(dependencies: List[str]) -> str:
    """Generate requirements.txt content from dependency list."""
    packages = [map_import_to_package(dep) for dep in dependencies]
    return "\n".join(sorted(packages))
