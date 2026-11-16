"""Write the installed development/build environment lock as portable UTF-8."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    frozen = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze", "--exclude-editable"], text=True
    )
    (root / "requirements.lock.txt").write_text(frozen, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
