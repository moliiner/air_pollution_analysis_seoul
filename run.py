"""Run the project on any system (Windows, macOS, Linux) without make.

    python run.py install        install the pinned dependencies
    python run.py lint           check src, tests, tools and this file with pyflakes
    python run.py test           run the test suite
    python run.py notebooks      execute every notebook in order, in fresh kernels
    python run.py notebooks 03   execute from notebook 03 onward
    python run.py all            lint, notebooks, then tests (the full check)
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))
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
    for path in NOTEBOOKS:
        if path.name[:2] < start:
            continue
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
