"""Bash script runner"""

import subprocess
from pathlib import Path


def _resolve_script(script_name: str) -> Path:
    """Resolve script path.

    Args:
        script_name: Name of the script file (e.g., "docker_build.sh")

    Returns:
        Absolute path to script

    Raises:
        FileNotFoundError: If script doesn't exist
    """
    scripts_dir = Path(__file__).parent
    script_path = scripts_dir / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    return script_path


def run_script(script_name: str, args: list[str] | None = None):
    """Run a bash script from the scripts directory

    Args:
        script_name: Name of the script file (e.g., "docker_build.sh")
        args: Optional list of arguments to pass to the script

    Raises:
        FileNotFoundError: If script doesn't exist
        subprocess.CalledProcessError: If script fails
    """
    script_path = _resolve_script(script_name)
    cmd = [str(script_path)] + (args or [])
    subprocess.run(cmd, check=True)


def run_script_capture(script_name: str, args: list[str] | None = None) -> str:
    """Run a bash script and capture its stdout.

    Args:
        script_name: Name of the script file (e.g., "docker_build.sh")
        args: Optional list of arguments to pass to the script

    Returns:
        Captured stdout as string

    Raises:
        FileNotFoundError: If script doesn't exist
        subprocess.CalledProcessError: If script fails
    """
    script_path = _resolve_script(script_name)
    cmd = [str(script_path)] + (args or [])
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()
