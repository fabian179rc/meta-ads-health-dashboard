# tests/test_rules_engine.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from rules_engine import CampaignMetrics, classify_campaign, rollup_campaign_verdict


def _base_metrics(**overrides):
    defaults = dict(
        campaign_id="1",
        campaign_name="Test Campaign",
        spend=200.0,
        impressions=5000,
        purchases=10,
        cost_per_purchase=20.0,
        ctr=1.5,
        frequency=2.0,
        quality_ranking="average",
        ctr_trend_pct=0.0,
        cvr_trend_pct=0.0,
        cpa_trend_pct=0.0,
        has_blocking_errors=False,
        days_since_last_creative=5,
        days_active=10,
    )
    defaults.update(overrides)
    return CampaignMetrics(**defaults)


def test_healthy_campaign_is_good():
    result = classify_campaign(_base_metrics())
    assert result.verdict == "good"


def test_blocking_error_is_kill_candidate_regardless_of_other_metrics():
    result = classify_campaign(_base_metrics(has_blocking_errors=True))
    assert result.verdict == "kill_candidate"
    assert any("entrega" in r.lower() for r in result.reasons)


def test_high_frequency_with_bad_cvr_and_cpa_trend_is_kill_candidate():
    result = classify_campaign(
        _base_metrics(frequency=4.0, cvr_trend_pct=-30.0, cpa_trend_pct=35.0)
    )
    assert result.verdict == "kill_candidate"


def test_spend_with_no_purchases_is_kill_candidate():
    result = classify_campaign(
        _base_metrics(purchases=0, cost_per_purchase=None, spend=80.0, days_active=5)
    )
    assert result.verdict == "kill_candidate"
    assert any("sin ventas" in r.lower() for r in result.reasons)


def test_high_frequency_alone_is_renew_creative():
    result = classify_campaign(_base_metrics(frequency=4.0))
    assert result.verdict == "renew_creative"
    assert any("frequency" in r.lower() for r in result.reasons)


def test_below_average_quality_ranking_is_renew_creative():
    result = classify_campaign(_base_metrics(quality_ranking="below_average"))
    assert result.verdict == "renew_creative"
    assert any("quality ranking" in r.lower() for r in result.reasons)


def test_bad_ctr_trend_is_renew_creative():
    result = classify_campaign(_base_metrics(ctr_trend_pct=-40.0))
    assert result.verdict == "renew_creative"
    assert any("ctr" in r.lower() for r in result.reasons)


def test_bad_cvr_trend_is_renew_creative():
    result = classify_campaign(_base_metrics(cvr_trend_pct=-26.0))
    assert result.verdict == "renew_creative"


def test_old_creative_with_no_trend_data_is_renew_creative():
    result = classify_campaign(
        _base_metrics(ctr_trend_pct=None, cvr_trend_pct=None, days_since_last_creative=20)
    )
    assert result.verdict == "renew_creative"
    assert any("14" in r for r in result.reasons)


def test_low_impressions_is_insufficient_data():
    result = classify_campaign(_base_metrics(impressions=200, days_active=10))
    assert result.verdict == "insufficient_data"


def test_low_days_active_is_insufficient_data():
    result = classify_campaign(_base_metrics(days_active=1))
    assert result.verdict == "insufficient_data"


def test_blocking_error_beats_insufficient_data():
    result = classify_campaign(
        _base_metrics(impressions=100, days_active=1, has_blocking_errors=True)
    )
    assert result.verdict == "kill_candidate"


def test_rollup_prefers_worst_verdict_kill_over_renew_over_good():
    assert rollup_campaign_verdict(["good", "renew_creative", "kill_candidate"]) == "kill_candidate"
    assert rollup_campaign_verdict(["good", "renew_creative"]) == "renew_creative"
    assert rollup_campaign_verdict(["good", "good"]) == "good"
    assert rollup_campaign_verdict([]) == "insufficient_data"
