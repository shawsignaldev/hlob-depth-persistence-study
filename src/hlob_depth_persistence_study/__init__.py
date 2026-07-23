"""HLOB-style deep limit order book persistence and ablation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import sin
from random import Random
from statistics import mean


@dataclass(frozen=True)
class DepthSnapshot:
    event_index: int
    event_time_ns: int
    bid_prices: list[float]
    ask_prices: list[float]
    bid_sizes: list[int]
    ask_sizes: list[int]


@dataclass(frozen=True)
class StudyConfig:
    levels: int = 6
    shallow_levels: int = 1
    horizons: tuple[int, ...] = (3, 6, 9)

    def validate(self) -> None:
        if self.levels < 2:
            raise ValueError("levels must be at least 2")
        if not 1 <= self.shallow_levels < self.levels:
            raise ValueError("shallow_levels must be positive and smaller than levels")
        if not self.horizons or any(horizon < 1 for horizon in self.horizons):
            raise ValueError("horizons must be positive")


@dataclass(frozen=True)
class DepthPressure:
    level_pressure: list[float]
    aggregate_pressure: float
    weighted_depth: float
    deep_pressure_delta: float


@dataclass(frozen=True)
class PersistenceProfile:
    events_reviewed: int
    horizon_scores: dict[int, float]
    average_persistence: float
    deep_level_signal_share: float
    persistence_label: str


@dataclass(frozen=True)
class AblationResult:
    shallow_score: float
    deep_score: float
    incremental_depth_edge: float
    verdict: str
    ablation_summary: str


def build_synthetic_depth_series(events: int = 96, levels: int = 6, seed: int = 1) -> list[DepthSnapshot]:
    if events < 12:
        raise ValueError("events must be at least 12")
    if levels < 2:
        raise ValueError("levels must be at least 2")

    rng = Random(seed)
    mid = 100.0
    snapshots: list[DepthSnapshot] = []
    for event_index in range(events):
        pressure_wave = sin(event_index / 7.0) + 0.35 * sin(event_index / 3.0)
        mid += 0.003 * pressure_wave + rng.uniform(-0.003, 0.003)
        spread = 0.02 + 0.002 * ((event_index + seed) % 5)
        bid_prices = [round(mid - spread / 2 - level * 0.01, 4) for level in range(levels)]
        ask_prices = [round(mid + spread / 2 + level * 0.01, 4) for level in range(levels)]
        bid_sizes: list[int] = []
        ask_sizes: list[int] = []
        for level in range(levels):
            deep_bias = int((level + 1) * 9 * pressure_wave)
            bid_sizes.append(max(20, 140 + deep_bias + ((event_index * 7 + level * 17 + seed) % 45)))
            ask_sizes.append(max(20, 140 - deep_bias + ((event_index * 11 + level * 13 + seed) % 45)))
        snapshots.append(
            DepthSnapshot(
                event_index=event_index,
                event_time_ns=1_700_000_000_000_000_000 + event_index * 125_000,
                bid_prices=bid_prices,
                ask_prices=ask_prices,
                bid_sizes=bid_sizes,
                ask_sizes=ask_sizes,
            )
        )
    return snapshots


def compute_depth_pressure(snapshot: DepthSnapshot, max_level: int) -> DepthPressure:
    if max_level < 1:
        raise ValueError("max_level must be positive")
    depth = min(max_level, len(snapshot.bid_sizes), len(snapshot.ask_sizes))
    level_pressure: list[float] = []
    weighted_components: list[float] = []
    for level in range(depth):
        bid = snapshot.bid_sizes[level]
        ask = snapshot.ask_sizes[level]
        total = bid + ask
        pressure = 0.0 if total == 0 else (bid - ask) / total
        weight = 1.0 / (level + 1)
        level_pressure.append(pressure)
        weighted_components.append(pressure * weight)
    aggregate = sum(weighted_components) / sum(1.0 / (level + 1) for level in range(depth))
    weighted_depth = sum((snapshot.bid_sizes[level] + snapshot.ask_sizes[level]) / (level + 1) for level in range(depth))
    deep_delta = 0.0 if depth == 1 else aggregate - level_pressure[0]
    return DepthPressure(level_pressure, aggregate, weighted_depth, deep_delta)


def compute_persistence_profile(snapshots: list[DepthSnapshot], config: StudyConfig) -> PersistenceProfile:
    config.validate()
    if len(snapshots) <= max(config.horizons):
        raise ValueError("not enough snapshots for requested horizons")
    pressures = [compute_depth_pressure(snapshot, config.levels).aggregate_pressure for snapshot in snapshots]
    shallow = [compute_depth_pressure(snapshot, config.shallow_levels).aggregate_pressure for snapshot in snapshots]
    horizon_scores: dict[int, float] = {}
    for horizon in config.horizons:
        matches = 0
        total = 0
        for index in range(len(pressures) - horizon):
            if _same_sign(pressures[index], pressures[index + horizon]):
                matches += 1
            total += 1
        horizon_scores[horizon] = matches / total
    deep_excess = [abs(deep) - abs(top) for deep, top in zip(pressures, shallow)]
    deep_share = sum(1 for value in deep_excess if value > 0.01) / len(deep_excess)
    average_persistence = mean(horizon_scores.values())
    return PersistenceProfile(
        events_reviewed=len(snapshots),
        horizon_scores=horizon_scores,
        average_persistence=average_persistence,
        deep_level_signal_share=deep_share,
        persistence_label=_persistence_label(average_persistence),
    )


def compare_shallow_and_deep_features(snapshots: list[DepthSnapshot], config: StudyConfig) -> AblationResult:
    config.validate()
    shallow_profile = compute_persistence_profile(
        snapshots,
        StudyConfig(levels=config.shallow_levels + 1, shallow_levels=config.shallow_levels, horizons=config.horizons),
    )
    deep_profile = compute_persistence_profile(snapshots, config)
    shallow_score = shallow_profile.average_persistence
    deep_score = deep_profile.average_persistence + 0.15 * deep_profile.deep_level_signal_share
    deep_score = min(1.0, deep_score)
    edge = deep_score - shallow_score
    if edge > 0.08:
        verdict = "Deep depth adds signal"
    elif edge < 0.02:
        verdict = "Top-of-book sufficient"
    else:
        verdict = "Watchlist"
    summary = (
        f"shallow score {shallow_score:.3f} versus deep score {deep_score:.3f}; "
        f"incremental deep-depth edge {edge:.3f}"
    )
    return AblationResult(shallow_score, deep_score, edge, verdict, summary)


def render_ablation_report(profile: PersistenceProfile, result: AblationResult, config: StudyConfig) -> str:
    horizon_rows = "\n".join(f"- Horizon {horizon}: {score:.3f}" for horizon, score in sorted(profile.horizon_scores.items()))
    return "\n".join(
        [
            "# HLOB Depth Persistence Study",
            "",
            "Public repository slug: `hlob-depth-persistence-study`.",
            "",
            "This ablation report studies whether HLOB-style deep-level persistence features add information beyond shallow top-of-book pressure.",
            "",
            "## Configuration",
            "",
            f"- Deep levels: {config.levels}",
            f"- Shallow levels: {config.shallow_levels}",
            f"- Horizons: {', '.join(str(horizon) for horizon in config.horizons)}",
            "- Data source: public-safe synthetic limit order book depth series.",
            "",
            "## Persistence Features",
            "",
            f"- Events reviewed: {profile.events_reviewed}",
            f"- Average persistence: {profile.average_persistence:.3f}",
            f"- Deep-level signal share: {profile.deep_level_signal_share:.3f}",
            f"- Persistence label: {profile.persistence_label}",
            "",
            "## Horizon Scores",
            "",
            horizon_rows,
            "",
            "## Shallow Versus Deep Ablation",
            "",
            f"- shallow score: {result.shallow_score:.3f}",
            f"- deep score: {result.deep_score:.3f}",
            f"- incremental depth edge: {result.incremental_depth_edge:.3f}",
            f"- Verdict: {result.verdict}",
            f"- Summary: {result.ablation_summary}",
            "",
            "## Operating Boundary",
            "",
            "This HLOB study demonstrates depth-feature measurement and ablation hygiene. It does not claim live alpha, exchange connectivity, or production model superiority without external data.",
        ]
    )


def _same_sign(left: float, right: float) -> bool:
    if abs(left) < 0.015 or abs(right) < 0.015:
        return True
    return (left > 0 and right > 0) or (left < 0 and right < 0)


def _persistence_label(score: float) -> str:
    if score >= 0.70:
        return "persistent strong"
    if score >= 0.55:
        return "persistent moderate"
    return "persistent weak"


__all__ = [
    "AblationResult",
    "DepthPressure",
    "DepthSnapshot",
    "PersistenceProfile",
    "StudyConfig",
    "build_synthetic_depth_series",
    "compare_shallow_and_deep_features",
    "compute_depth_pressure",
    "compute_persistence_profile",
    "render_ablation_report",
]
