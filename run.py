"""Run the project on any system (Windows, macOS, Linux) without make.

    python run.py install        install the pinned dependencies
    python run.py lint           check src, tests, tools and this file with pyflakes
    python run.py test           run the test suite
    python run.py notebooks      execute every notebook in dependency order, in fresh kernels
    python run.py notebooks 03   execute notebook 03 and every notebook after it in that order
    python run.py all            lint, notebooks, then tests (the full check)
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Notebooks are numbered by topic; this is the order their inputs require:
# 00-01 Kaggle data -> 07 official data 2015-2025 -> 08 weather -> 02-04 analyses
# of 2015-2025 -> 05 forecast (Kaggle data) -> 06 summary
ORDER = ["00", "01", "07", "08", "02", "03", "04", "09", "10", "05", "06"]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"), key=lambda p: ORDER.index(p.name[:2]))
# One thread per numerical library keeps memory low on small machines; results do not change
ENV = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "2"}


def call(*args):
    print(">", " ".join(str(a) for a in args), flush=True)
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT, env=ENV).returncode


def install():
    return call("pip", "install", "-r", "requirements.txt", "-c", "constraints.txt")


def lint():
    return call("pyflakes", "src", "tests", "tools", "run.py")


def test():
    return call("pytest", "-q")


def notebooks(start="00"):
    for path in [p for p in NOTEBOOKS if ORDER.index(p.name[:2]) >= ORDER.index(start)]:
        code = call("jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
                    "--ExecutePreprocessor.timeout=3600", str(path.relative_to(ROOT)))
        if code:
            print(f"Stopped: {path.name} failed", flush=True)
            return code
    return 0


def run_all():
    for step in (lint, notebooks, test):
        code = step()
        if code:
            return code
    return 0


COMMANDS = {"install": install, "lint": lint, "test": test, "notebooks": notebooks, "all": run_all}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 1 if argv else 0
    return COMMANDS[argv[0]](*argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
