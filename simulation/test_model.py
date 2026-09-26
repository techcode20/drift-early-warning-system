"""Model tests: the dummy classifier learns the old fraud pattern and goes
blind when fraudsters change tactics (spike) — genuine concept drift."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation.fraud_gen import get_batch
from simulation.model import featurize, score_batch, train


def test_model_learns_baseline():
    base = get_batch(5000, "baseline", seed=1)
    model, cols, out = train(base)
    assert out["acc"] > 0.85, out
    assert 0.01 < out["true_fraud_rate"] < 0.15, out


def test_covariate_shift_keeps_accuracy():
    # gradual = same fraud rule, shifted inputs: model should mostly survive
    base = get_batch(5000, "baseline", seed=1)
    model, cols, out = train(base)
    r = score_batch(model, cols, get_batch(800, "gradual", seed=2))
    assert r["acc"] > out["acc"] - 0.15, (out, r)


def test_concept_drift_kills_accuracy():
    # spike = new fraud rule: same model, collapsing accuracy
    base = get_batch(5000, "baseline", seed=1)
    model, cols, out = train(base)
    r = score_batch(model, cols, get_batch(800, "spike", seed=2))
    assert r["acc"] < out["acc"] - 0.20, (out, r)
    assert r["true_fraud_rate"] > r["pred_fraud_rate"] + 0.20, r  # blind to the ring


def test_no_labels_no_accuracy():
    base = get_batch(2000, "baseline", seed=1)
    model, cols, _ = train(base)
    r = score_batch(model, cols, get_batch(600, "normal", seed=3, with_label=False))
    assert r["acc"] is None and r["true_fraud_rate"] is None
    assert 0.0 <= r["pred_fraud_rate"] <= 1.0


def test_featurize_columns_stable():
    a = featurize(get_batch(100, "normal", seed=1))
    b = featurize(get_batch(100, "spike", seed=2))
    assert list(a.columns) == list(b.columns)
