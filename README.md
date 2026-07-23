# HLOB Depth Persistence Study

Public repository slug: `hlob-depth-persistence-study`.

HLOB-style deep-level persistence and ablation study with public-safe synthetic depth fixtures, persistence features, shallow-versus-deep comparison, and Markdown reports.

## Why This Exists

Top-of-book imbalance is useful but incomplete. HLOB-style research asks whether deeper order-book levels carry persistent structure that survives across forecast horizons. This repository turns that question into a deterministic, test-backed study.

## Implemented Capabilities

- Public-safe synthetic multi-level order-book depth series.
- Per-level pressure vectors and aggregate depth pressure.
- Persistence scores across configurable horizons.
- Deep-level signal-share estimate.
- Shallow top-of-book versus deep-depth ablation.
- Markdown ablation report with explicit limitations.

## Example

```python
from hlob_depth_persistence_study import (
    StudyConfig,
    build_synthetic_depth_series,
    compute_persistence_profile,
    compare_shallow_and_deep_features,
    render_ablation_report,
)

snapshots = build_synthetic_depth_series(events=70, levels=6, seed=34)
config = StudyConfig(levels=6, shallow_levels=1, horizons=(3, 7, 11))
profile = compute_persistence_profile(snapshots, config)
result = compare_shallow_and_deep_features(snapshots, config)
report = render_ablation_report(profile, result, config)
```

## Research Anchor

HLOB motivates hierarchical and deeper limit order book features rather than relying only on the best bid and ask. This package isolates the persistence and ablation layer of that idea.

## Verification

```powershell
python -m pytest -q -p no:cacheprovider
```

Expected result:

```text
5 passed
```

## Operating Boundary

This repository demonstrates HLOB-style feature measurement and ablation hygiene on deterministic public fixtures. It does not claim live alpha, exchange connectivity, or production model superiority without external data.
