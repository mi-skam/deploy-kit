"""Bash script runner"""

import subprocess
from pathlib import Path


def run_script(script_name: str, args: list[str] | None = None):
    """Run a bash script from the scripts directory

    Args:
        script_name: Name of the script file (e.g., "docker_build.sh")
        args: Optional list of arguments to pass to the script

    Raises:
        FileNotFoundError: If script doesn't exist
        subprocess.CalledProcessError: If script fails
    """
    scripts_dir = Path(__file__).parent
    script_path = scripts_dir / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    cmd = [str(script_path)] + (args or [])
    subprocess.run(cmd, check=True)
