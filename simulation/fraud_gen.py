"""Role 1 — simulation: fake fraud data generator.
Usage:
  python simulation/fraud_gen.py --n 10000 --mode baseline --out simulation/baseline.csv
  python simulation/fraud_gen.py --n 800 --mode normal|gradual|spike
Modes: baseline/normal = training distribution,
       gradual = amount mean slowly shifts (+40%, covariate shift only),
       spike = new fraud ring: location concentrates on FL AND the fraud
               rule itself changes (real concept drift — old model goes blind).
Labels: with_label=True adds `is_fraud`. The rule differs by mode on purpose:
  normal rule = online merchant + amount > 40  (what the model learns)
  spike rule  = FL location                    (fraudsters moved; model misses)
5% label noise keeps it honest.
"""
import argparse
import numpy as np
import pandas as pd

LOCATIONS = ["NY", "CA", "TX", "FL"]
MERCHANTS = ["grocery", "gas", "online", "restaurant"]
LABEL_COL = "is_fraud"


def get_batch(n: int, mode: str = "normal", seed: int | None = None,
              with_label: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    if mode in ("baseline", "normal"):
        amount = rng.lognormal(mean=3.0, sigma=0.8, size=n)  # ~$20 avg
        location = rng.choice(LOCATIONS, size=n, p=[0.4, 0.3, 0.2, 0.1])
    elif mode == "gradual":
        amount = rng.lognormal(mean=3.0 + 0.34, sigma=0.8, size=n)  # ~+40% shift
        location = rng.choice(LOCATIONS, size=n, p=[0.4, 0.3, 0.2, 0.1])
    elif mode == "spike":
        amount = rng.lognormal(mean=3.0, sigma=0.8, size=n)
        location = rng.choice(LOCATIONS, size=n, p=[0.1, 0.1, 0.2, 0.6])  # FL spike
    else:
        raise ValueError(f"unknown mode {mode}")
    hour = rng.integers(0, 24, size=n)
    merchant = rng.choice(MERCHANTS, size=n)
    device_age = rng.exponential(scale=365, size=n)
    df = pd.DataFrame({
        "amount": np.round(amount, 2), "hour": hour,
        "location": location, "merchant": merchant,
        "device_age": np.round(device_age, 1),
    })
    if with_label:
        if mode == "spike":
            fraud = df["location"] == "FL"  # new ring: model never saw this
        else:
            fraud = (df["merchant"] == "online") & (df["amount"] > 40)
        flip = rng.random(n) < 0.05
        df[LABEL_COL] = (fraud ^ flip).astype(int)
    return df


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--mode", type=str, default="baseline")
    p.add_argument("--out", type=str, default="simulation/baseline.csv")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    df = get_batch(a.n, a.mode, a.seed)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df)} rows mode={a.mode} -> {a.out} "
          f"(fraud_rate={df[LABEL_COL].mean():.3f})")
