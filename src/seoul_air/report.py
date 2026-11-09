"""Key figures that the notebooks save and the README quotes.

Each notebook writes the numbers it supports to reports/metrics/<notebook>_key_figures.json,
and tests/test_readme_numbers.py checks that the README quotes them correctly.
"""
import json

import numpy as np

from seoul_air import config


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def key_figures_path(notebook):
    return config.METRICS / f"{notebook}_key_figures.json"


def save_key_figures(notebook, figures):
    """Write the key figures of one notebook, with plain JSON types and sorted keys."""
    path = key_figures_path(notebook)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_plain(figures), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_key_figures(notebook):
    return json.loads(key_figures_path(notebook).read_text(encoding="utf-8"))
