# Architecture

## Pipeline

1. Generate deterministic public-safe multi-level depth snapshots.
2. Compute per-level bid/ask pressure vectors.
3. Aggregate weighted depth pressure.
4. Score persistence across multiple event horizons.
5. Compare shallow top-of-book pressure with deeper HLOB-style pressure.
6. Render an ablation report with limitations.

## Review Contract

The narrow claim is that this package can measure deep-level persistence features and compare them against shallow top-of-book features in a deterministic study.
