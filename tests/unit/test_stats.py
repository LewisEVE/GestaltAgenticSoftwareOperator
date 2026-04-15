from gestalt.stats import GestaltStats, LoadLevel, MonitorSnapshot, PerformanceTier, StatsThresholds


def test_apply_monitor_snapshot_derives_scores_and_tiers() -> None:
    stats = GestaltStats()
    snapshot = MonitorSnapshot(
        queue_depth=65,
        active_cycles=4,
        avg_latency_ms=1800,
        p95_latency_ms=2500,
        error_rate=0.08,
        failure_count=8,
        success_count=92,
        cost_per_cycle=1.4,
        blackboard_consistency=0.85,
        collaboration_success_rate=0.9,
        security_open_findings=2,
    )

    stats.apply_monitor_snapshot(snapshot, StatsThresholds())

    assert stats.load_level == LoadLevel.HIGH
    assert stats.performance_tier == PerformanceTier.HIGH
    assert stats.cost_efficiency_score < 100
    assert 0 <= stats.security_risk_score <= 100
    assert 0 <= stats.gestalt_cohesion_score <= 100


def test_optimizer_trigger_detects_material_change() -> None:
    previous = GestaltStats()
    current = GestaltStats(
        load_level=LoadLevel.EXTREME,
        performance_tier=PerformanceTier.CRITICAL,
        cost_efficiency_score=35,
        security_risk_score=82,
        gestalt_cohesion_score=41,
    )

    assert current.should_trigger_optimizer(previous, delta_threshold=10) is True


def test_security_intervention_threshold() -> None:
    stats = GestaltStats(security_risk_score=71, open_security_findings=2)
    assert stats.should_trigger_security_intervention() is True

    low_risk = GestaltStats(security_risk_score=25, open_security_findings=0)
    assert low_risk.should_trigger_security_intervention() is False
