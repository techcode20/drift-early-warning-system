import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation.fraud_gen import get_batch
from detector.drift_engine import compare


def test_identical_is_zero():
    base = get_batch(2000, "baseline", seed=1)
    assert compare(base, base)["psi_global"] == 0.0


def test_gradual_detected():
    base = get_batch(5000, "baseline", seed=1)
    drifted = get_batch(800, "gradual", seed=2)
    r = compare(base, drifted)
    assert r["psi_global"] > 0.10, r
    assert r["top_feature"] == "amount", r


def test_small_batch_no_decision():
    base = get_batch(5000, "baseline", seed=1)
    small = get_batch(100, "spike", seed=3)
    assert compare(base, small)["severity"] == "no-decision"
