import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fetch_and_analyze as fa


CURRENT_ROW = {
    "ad_id": "ad1",
    "ad_name": "Ad One",
    "campaign_id": "camp1",
    "campaign_name": "Campaign One",
    "spend": 200.0,
    "impressions": 5000,
    "clicks": 100,
    "ctr": 2.0,
    "purchases": 10,
    "cost_per_purchase": 20.0,
    "frequency": 2.0,
    "quality_ranking": "average",
}

PRIOR_ROW = {**CURRENT_ROW, "ctr": 2.0, "purchases": 10, "cost_per_purchase": 20.0, "clicks": 100}


def test_build_snapshot_aggregates_campaign_totals_and_classifies():
    with patch.object(fa, "get_ad_insights_for_range", side_effect=[[CURRENT_ROW], [PRIOR_ROW]]), \
         patch.object(fa, "get_delivery_issues", return_value={}), \
         patch.object(fa, "get_last_creative_change_days", return_value=5):
        snapshot = fa.build_snapshot(token="fake-token")

    assert snapshot["account_spend"] == 200.0
    assert snapshot["account_purchases"] == 10
    assert snapshot["account_cpa"] == 20.0
    assert len(snapshot["campaigns"]) == 1
    campaign = snapshot["campaigns"][0]
    assert campaign["campaign_id"] == "camp1"
    assert campaign["verdict"] == "good"
    assert campaign["ads"][0]["ad_id"] == "ad1"
    assert campaign["ads"][0]["days_since_last_creative"] == 5
    assert campaign["days_since_last_creative"] == 5
    assert snapshot["period"]["current_since"] < snapshot["period"]["current_until"]
    assert snapshot["period"]["prior_until"] < snapshot["period"]["current_since"]


def test_build_snapshot_flags_declining_ctr_as_renew_creative():
    declining_current = {**CURRENT_ROW, "ctr": 1.0}
    with patch.object(fa, "get_ad_insights_for_range", side_effect=[[declining_current], [PRIOR_ROW]]), \
         patch.object(fa, "get_delivery_issues", return_value={}), \
         patch.object(fa, "get_last_creative_change_days", return_value=5):
        snapshot = fa.build_snapshot(token="fake-token")

    assert snapshot["campaigns"][0]["verdict"] == "renew_creative"


def test_build_snapshot_handles_zero_purchase_account_cpa():
    zero_purchase_row = {**CURRENT_ROW, "purchases": 0, "cost_per_purchase": None, "spend": 10.0}
    with patch.object(fa, "get_ad_insights_for_range", side_effect=[[zero_purchase_row], []]), \
         patch.object(fa, "get_delivery_issues", return_value={}), \
         patch.object(fa, "get_last_creative_change_days", return_value=5):
        snapshot = fa.build_snapshot(token="fake-token")

    assert snapshot["account_cpa"] is None


def test_build_snapshot_campaign_creative_age_is_most_recent_ad():
    ad_two = {**CURRENT_ROW, "ad_id": "ad2", "ad_name": "Ad Two"}
    with patch.object(fa, "get_ad_insights_for_range", side_effect=[[CURRENT_ROW, ad_two], [PRIOR_ROW, PRIOR_ROW]]), \
         patch.object(fa, "get_delivery_issues", return_value={}), \
         patch.object(fa, "get_last_creative_change_days", side_effect=[30, 5]):
        snapshot = fa.build_snapshot(token="fake-token")

    assert snapshot["campaigns"][0]["days_since_last_creative"] == 5


def test_build_snapshot_handles_no_current_purchases_with_prior_purchases():
    no_purchase_current = {**CURRENT_ROW, "purchases": 0, "cost_per_purchase": None, "clicks": 100}
    with patch.object(fa, "get_ad_insights_for_range", side_effect=[[no_purchase_current], [PRIOR_ROW]]), \
         patch.object(fa, "get_delivery_issues", return_value={}), \
         patch.object(fa, "get_last_creative_change_days", return_value=5):
        snapshot = fa.build_snapshot(token="fake-token")

    ad = snapshot["campaigns"][0]["ads"][0]
    assert ad["ad_id"] == "ad1"
