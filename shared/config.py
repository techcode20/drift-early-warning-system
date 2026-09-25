# Shared thresholds — single source of truth. Everyone imports this, nobody hardcodes.
PSI_NONE = 0.10
PSI_MILD = 0.25  # >=0.25 = severe (industry standard)
BATCH_MIN_N = 500
ROLLING_WINDOW = 7
CONSECUTIVE_BREACHES = 2
NUMERIC_FEATURES = ["amount", "hour", "device_age"]
CATEGORICAL_FEATURES = ["location", "merchant"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
