# Viva Q&A — Drift Guard

One-line answers. If they ask deeper, show the file.

1. **What problem?** Deployed models rot as live data shifts; accuracy drops are
   visible only weeks later via delayed labels. We alarm on distribution shift first.
2. **Why PSI?** Industry-standard banding for score monitoring (<0.1 none,
   0.1–0.25 watch, >0.25 act). KS backs it for sudden shifts; KL is supplementary.
   See `shared/config.py`.
3. **Why max-PSI, not mean?** Mean dilutes: one rotting feature (PSI 0.15) across
   5 features reads 0.03 = missed. Max fires. (`detector/drift_engine.py`)
4. **False alarms?** Three guards: batches <500 refused, 2-consecutive-breach
   confirmation, Bonferroni-corrected KS p-values. Proof: 30/30 normal batches → none.
5. **Covariate vs concept drift?** `gradual` moves inputs, same fraud rule —
   accuracy survives. `spike` changes the rule itself — accuracy collapses while
   the model stays confident. Dashboard shows both charts. (`simulation/test_model.py`)
6. **Why not alibi-detect?** Hand-rolled scipy keeps deps light and every formula
   explainable in viva. Alibi is the right call for production scale, not for this demo.
7. **Why SQLite?** Zero-setup rolling time-series store; `DRIFT_DB` env swaps it out.
   Postgres when you need concurrency.
8. **Threshold justification?** PSI bands are the credit-risk industry rule of thumb;
   0.50 severe cut and 500-row floor are ours, validated by the 30-batch no-alarm run.
9. **What triggers retraining?** `severe` writes `retrain_trigger.json`
   (batch, feature, accuracy, confirmed flag) — a pipeline hook, not a pipeline.
10. **Limitations?** Synthetic data, immediate labels (real labels lag weeks),
    single-model/single-table scope, no seasonality handling. Say all three upfront.
