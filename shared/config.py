# Shared thresholds — single source of truth. Everyone imports this, nobody hardcodes.
# PSI bands follow the industry-standard rule of thumb (e.g. credit-risk score monitoring):
#   <0.10 no significant shift · 0.10–0.25 small shift, watch · >=0.25 large shift, act.
PSI_NONE = 0.10
PSI_MILD = 0.25
PSI_MODERATE = 0.50  # >=0.50 = severe (overrides PSI_MILD band)
ALPHA = 0.05  # significance level for KS tests (before Bonferroni correction)
BATCH_MIN_N = 500  # smaller batches are noise, not signal — refuse to judge them
ROLLING_WINDOW = 7  # batches averaged for the rolling health line
CONSECUTIVE_BREACHES = 2  # breaches in a row required before an alert is CONFIRMED
NUMERIC_FEATURES = ["amount", "hour", "device_age"]
CATEGORICAL_FEATURES = ["location", "merchant"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
ACTION_BY_SEVERITY = {
    "none": "log",
    "mild": "log",
    "moderate": "alert-human",
    "severe": "trigger-retrain",
    "no-decision": "wait",
}
