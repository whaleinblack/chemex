"""Run untouched upstream tests with ChemEx's headless/scipy compatibility shims.

The vendored namespace otherwise loses to the installed modern SESAMI package.
Run from the repository root: python tests/run_vendor_sesami.py
"""
import os
import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'vendor/SESAMI_web'
os.chdir(root)
package = types.ModuleType('SESAMI')
package.__path__ = [str(root / 'SESAMI')]
sys.modules['SESAMI'] = package

import numpy as np
import scipy
import matplotlib

scipy.log = np.log
scipy.sqrt = np.sqrt
original_use = matplotlib.use
matplotlib.use = lambda backend, *args, **kwargs: original_use(
    'Agg' if backend.lower() == 'tkagg' else backend, *args, **kwargs,
)

import pytest

sys.exit(pytest.main(['tests', '-q']))
