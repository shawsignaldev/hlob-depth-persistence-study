from hlob_depth_persistence_study import (
    AblationResult,
    StudyConfig,
    build_synthetic_depth_series,
    compute_depth_pressure,
    compute_persistence_profile,
    compare_shallow_and_deep_features,
    render_ablation_report,
)


def test_synthetic_depth_series_has_ordered_multi_level_snapshots():
    snapshots = build_synthetic_depth_series(events=42, levels=6, seed=5)

    assert len(snapshots) == 42
    assert snapshots[0].event_index == 0
    assert snapshots[-1].event_index == 41
    assert all(left.event_time_ns < right.event_time_ns for left, right in zip(snapshots, snapshots[1:]))
    assert all(len(snapshot.bid_sizes) == 6 and len(snapshot.ask_sizes) == 6 for snapshot in snapshots)
    assert all(snapshot.ask_prices[0] > snapshot.bid_prices[0] for snapshot in snapshots)


def test_depth_pressure_uses_all_levels_and_top_of_book_subset():
    snapshots = build_synthetic_depth_series(events=20, levels=5, seed=8)

    full = compute_depth_pressure(snapshots[3], max_level=5)
    shallow = compute_depth_pressure(snapshots[3], max_level=1)

    assert len(full.level_pressure) == 5
    assert len(shallow.level_pressure) == 1
    assert -1.0 <= full.aggregate_pressure <= 1.0
    assert full.weighted_depth != shallow.weighted_depth
    assert full.deep_pressure_delta != 0.0


def test_persistence_profile_scores_stability_across_horizons():
    snapshots = build_synthetic_depth_series(events=64, levels=6, seed=13)
    config = StudyConfig(levels=6, shallow_levels=1, horizons=(3, 6, 9))

    profile = compute_persistence_profile(snapshots, config)

    assert profile.events_reviewed == 64
    assert set(profile.horizon_scores) == {3, 6, 9}
    assert all(0.0 <= score <= 1.0 for score in profile.horizon_scores.values())
    assert 0.0 <= profile.average_persistence <= 1.0
    assert profile.deep_level_signal_share > 0.0
    assert "persistent" in profile.persistence_label


def test_ablation_compares_shallow_against_deep_features():
    snapshots = build_synthetic_depth_series(events=72, levels=6, seed=21)
    result = compare_shallow_and_deep_features(snapshots, StudyConfig(levels=6, shallow_levels=1, horizons=(4, 8)))

    assert isinstance(result, AblationResult)
    assert 0.0 <= result.shallow_score <= 1.0
    assert 0.0 <= result.deep_score <= 1.0
    assert result.incremental_depth_edge == result.deep_score - result.shallow_score
    assert result.verdict in {"Deep depth adds signal", "Top-of-book sufficient", "Watchlist"}
    assert "shallow" in result.ablation_summary
    assert "deep" in result.ablation_summary


def test_markdown_report_mentions_hlob_depth_persistence_and_limitations():
    snapshots = build_synthetic_depth_series(events=70, levels=6, seed=34)
    config = StudyConfig(levels=6, shallow_levels=1, horizons=(3, 7, 11))
    profile = compute_persistence_profile(snapshots, config)
    result = compare_shallow_and_deep_features(snapshots, config)

    report = render_ablation_report(profile, result, config)

    assert "# HLOB Depth Persistence Study" in report
    assert "hlob-depth-persistence-study" in report
    assert "HLOB" in report
    assert "deep-level persistence" in report
    assert "ablation report" in report
    assert "shallow" in report
    assert "deep" in report
    assert "persistence features" in report
    assert "public-safe synthetic" in report
