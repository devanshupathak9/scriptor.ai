import re
import subprocess
import sys
from pathlib import Path


# Map common import names → pip package names when they differ
IMPORT_TO_PACKAGE: dict[str, str] = {
    "sklearn":  "scikit-learn",
    "cv2":      "opencv-python",
    "PIL":      "Pillow",
    "bs4":      "beautifulsoup4",
    "yaml":     "pyyaml",
    "dotenv":   "python-dotenv",
    "jwt":      "PyJWT",
    "dateutil": "python-dateutil",
    "Crypto":   "pycryptodome",
}

_STDLIB: set[str] = (
    set(sys.stdlib_module_names)   # Python 3.10+
    if hasattr(sys, "stdlib_module_names")
    else set()
)
_SKIP: set[str] = {"__future__", "__main__", "typing", "_typeshed"}


def run_shell(cmd: str, cwd: str | None = None, timeout: int = 60) -> dict:
    """Run a shell command. Returns {stdout, stderr, exit_code}."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return {
            "stdout":    result.stdout,
            "stderr":    result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out.", "exit_code": -1}
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "exit_code": -1}


def write_file(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def detect_imports(code: str) -> list[str]:
    """Return pip package names inferred from top-level import statements."""
    pattern = re.compile(r"^(?:import|from)\s+([a-zA-Z_]\w*)", re.MULTILINE)
    seen: set[str] = set()
    packages: list[str] = []
    for m in pattern.finditer(code):
        module = m.group(1)
        if module in _STDLIB or module in _SKIP:
            continue
        pkg = IMPORT_TO_PACKAGE.get(module, module)
        if pkg not in seen:
            seen.add(pkg)
            packages.append(pkg)
    return packages


def find_python_binary(version: str) -> str | None:
    """
    Return the binary name for the requested Python version, or None.
    Tries `python<version>` first (e.g. python3.11), then falls back
    to checking `python3` and `python`.
    """
    candidates = [f"python{version}", "python3", "python"]
    for binary in candidates:
        result = run_shell(f"{binary} --version")
        if result["exit_code"] == 0:
            output = (result["stdout"] + result["stderr"]).strip()
            if version in output:
                return binary
    return None
