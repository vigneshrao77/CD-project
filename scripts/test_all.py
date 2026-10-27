"""Run every unit/negative/golden test, then the complete differential corpus."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    for arguments in (['-m', 'unittest', 'discover', '-v'], ['-m', 'tests.e2e']):
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
