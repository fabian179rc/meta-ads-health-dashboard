import json
import os
from datetime import date, timedelta

from dotenv import load_dotenv

from meta_client import get_ad_insights_for_range, get_delivery_issues, get_last_creative_change_days
from rules_engine import CampaignMetrics, classify_campaign, rollup_campaign_verdict

load_dotenv()

ACCOUNT_ID = "1899970234248234"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")


def _pct_change(current, prior):
    if current is None or prior in (None, 0):
        return None
    return ((current - prior) / prior) * 100


def build_snapshot(token: str) -> dict:
    today = date.today()
    current_since = (today - timedelta(days=7)).isoformat()
    current_until = today.isoformat()
    prior_since = (today - timedelta(days=14)).isoformat()
    prior_until = (today - timedelta(days=8)).isoformat()

    current_rows = get_ad_insights_for_range(ACCOUNT_ID, token, current_since, current_until)
    prior_rows = get_ad_insights_for_range(ACCOUNT_ID, token, prior_since, prior_until)
    prior_by_ad = {row["ad_id"]: row for row in prior_rows}

    ad_ids = [row["ad_id"] for row in current_rows]
    issues = get_delivery_issues(ad_ids, token)

    campaigns: dict[str, dict] = {}
    for row in current_rows:
        prior_row = prior_by_ad.get(row["ad_id"], {})

        ctr_trend = _pct_change(row.get("ctr"), prior_row.get("ctr"))
        cvr_current = (row["purchases"] / row["clicks"] * 100) if row.get("clicks") else None
        cvr_prior = (
            (prior_row["purchases"] / prior_row["clicks"] * 100)
            if prior_row.get("clicks")
            else None
        )
        cvr_trend = _pct_change(cvr_current, cvr_prior)
        cpa_trend = _pct_change(row.get("cost_per_purchase"), prior_row.get("cost_per_purchase"))
        days_since_creative = get_last_creative_change_days(ACCOUNT_ID, token, row["ad_id"])

        metrics = CampaignMetrics(
            campaign_id=row["campaign_id"],
            campaign_name=row["campaign_name"],
            spend=row["spend"],
            impressions=row["impressions"],
            purchases=row["purchases"],
            cost_per_purchase=row.get("cost_per_purchase"),
            ctr=row["ctr"],
            frequency=row["frequency"],
            quality_ranking=row.get("quality_ranking", "unknown"),
            ctr_trend_pct=ctr_trend,
            cvr_trend_pct=cvr_trend,
            cpa_trend_pct=cpa_trend,
            has_blocking_errors=row["ad_id"] in issues,
            days_since_last_creative=days_since_creative,
            days_active=7,
        )
        verdict_result = classify_campaign(metrics)

        campaign = campaigns.setdefault(
            row["campaign_id"],
            {
                "campaign_id": row["campaign_id"],
                "campaign_name": row["campaign_name"],
                "spend": 0.0,
                "purchases": 0,
                "ads": [],
            },
        )
        campaign["spend"] += row["spend"]
        campaign["purchases"] += row["purchases"]
        campaign["ads"].append(
            {
                "ad_id": row["ad_id"],
                "ad_name": row["ad_name"],
                "verdict": verdict_result.verdict,
                "reasons": verdict_result.reasons,
            }
        )

    for campaign in campaigns.values():
        campaign["verdict"] = rollup_campaign_verdict([ad["verdict"] for ad in campaign["ads"]])
        campaign["spend"] = round(campaign["spend"], 2)

    account_spend = sum(c["spend"] for c in campaigns.values())
    account_purchases = sum(c["purchases"] for c in campaigns.values())

    return {
        "generated_at": today.isoformat(),
        "account_id": ACCOUNT_ID,
        "account_spend": round(account_spend, 2),
        "account_purchases": account_purchases,
        "account_cpa": round(account_spend / account_purchases, 2) if account_purchases else None,
        "campaigns": list(campaigns.values()),
    }


def main() -> None:
    token = os.environ["ADS_API_TOKEN"]
    snapshot = build_snapshot(token)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    print(
        f"Wrote {OUTPUT_PATH}: {len(snapshot['campaigns'])} campaigns, "
        f"{snapshot['account_purchases']} purchases, ${snapshot['account_spend']} spend"
    )


if __name__ == "__main__":
    main()
