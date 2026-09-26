import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detector.drift_engine import compare, confirmed, severity_of
from detector.metrics import kl, ks, psi, psi_categorical
from simulation.fraud_gen import get_batch


@pytest.fixture(scope="module")
def base():
    return get_batch(5000, "baseline", seed=1)


def test_identical_is_zero(base):
    assert compare(base, base)["psi_global"] == 0.0


def test_gradual_detected(base):
    r = compare(base, get_batch(800, "gradual", seed=2))
    assert r["psi_global"] > 0.10, r
    assert r["top_feature"] == "amount", r


def test_spike_blames_location(base):
    r = compare(base, get_batch(800, "spike", seed=2))
    assert r["top_feature"] == "location", r
    assert r["severity"] == "severe", r


def test_small_batch_no_decision(base):
    assert compare(base, get_batch(100, "spike", seed=3))["severity"] == "no-decision"


def test_missing_column_raises(base):
    with pytest.raises(ValueError, match="missing columns"):
        compare(base, base.drop(columns=["amount"]))


def test_nan_tolerant(base):
    batch = get_batch(800, "normal", seed=9).copy()
    batch.loc[batch.sample(50, random_state=1).index, "amount"] = np.nan
    r = compare(base, batch)
    assert r["severity"] in ("none", "mild"), r  # noise, not drift


def test_constant_series_no_crash():
    s = pd.Series([5.0] * 1000)
    assert psi(s, s) == 0.0
    assert kl(s, s) == 0.0


def test_bonferroni_keys_present(base):
    per = compare(base, get_batch(800, "normal", seed=4))["per_feature"]
    assert set(per["amount"]) >= {"psi", "ks_D", "ks_p", "ks_p_adj", "ks_sig"}
    assert per["amount"]["ks_p_adj"] >= per["amount"]["ks_p"]


def test_psi_categorical_symmetric():
    a = pd.Series(["x", "y", "x"])
    assert psi_categorical(a, a) == 0.0
    assert psi_categorical(a, pd.Series(["z"] * 3)) > 0.25


def test_severity_bands():
    assert severity_of(0.0) == "none"
    assert severity_of(0.15) == "mild"
    assert severity_of(0.3) == "moderate"
    assert severity_of(0.9) == "severe"


def test_confirmed_rule():
    assert confirmed(["none", "severe"]) is False  # lone spike: log, don't page
    assert confirmed(["severe", "severe"]) is True
    assert confirmed(["mild", "moderate"]) is False
    assert confirmed(["moderate", "severe"]) is True
    assert confirmed(["severe"]) is False
