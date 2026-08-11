# scripts/meta_client.py
import datetime
from concurrent.futures import ThreadPoolExecutor

import requests

MAX_WORKERS = 10

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

PURCHASE_ACTION_TYPES = {"offsite_conversion.fb_pixel_purchase", "omni_purchase", "purchase"}
CREATIVE_CHANGE_EVENT_TYPES = {"create_ad", "update_ad_creative", "add_images", "edit_images"}


class MetaApiError(Exception):
    """Raised when the Meta Graph API returns an error response."""


def _get(path: str, params: dict, token: str) -> dict:
    request_params = {**params, "access_token": token}
    response = requests.get(f"{GRAPH_API_BASE}/{path}", params=request_params, timeout=30)
    body = response.json()
    if "error" in body:
        raise MetaApiError(f"{path}: {body['error'].get('message', body['error'])}")
    return body


def _extract_purchases(actions: list[dict] | None) -> int:
    if not actions:
        return 0
    return sum(
        int(float(a["value"])) for a in actions if a.get("action_type") in PURCHASE_ACTION_TYPES
    )


def get_active_campaigns(account_id: str, token: str) -> list[dict]:
    body = _get(
        f"act_{account_id}/campaigns",
        {
            "fields": "id,name,effective_status",
            "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]',
            "limit": 200,
        },
        token,
    )
    return [{"id": c["id"], "name": c["name"]} for c in body.get("data", [])]


def get_ad_insights_for_range(account_id: str, token: str, since: str, until: str) -> list[dict]:
    body = _get(
        f"act_{account_id}/insights",
        {
            "level": "ad",
            "fields": (
                "ad_id,ad_name,campaign_id,campaign_name,spend,impressions,clicks,ctr,"
                "frequency,actions,quality_ranking"
            ),
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "filtering": '[{"field":"ad.effective_status","operator":"IN","value":["ACTIVE"]}]',
            "limit": 500,
        },
        token,
    )
    results = []
    for row in body.get("data", []):
        purchases = _extract_purchases(row.get("actions"))
        spend = float(row.get("spend", 0))
        results.append(
            {
                "ad_id": row["ad_id"],
                "ad_name": row.get("ad_name", ""),
                "campaign_id": row["campaign_id"],
                "campaign_name": row.get("campaign_name", ""),
                "spend": spend,
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr": float(row.get("ctr", 0)),
                "purchases": purchases,
                "cost_per_purchase": (spend / purchases) if purchases else None,
                "frequency": float(row.get("frequency", 0)),
                "quality_ranking": (row.get("quality_ranking") or "unknown").lower(),
            }
        )
    return results


def _fetch_issues(obj_id: str, token: str) -> tuple[str, list[str]]:
    body = _get(obj_id, {"fields": "issues_info{error_summary,level}"}, token)
    issues = body.get("issues_info", [])
    blocking = [i["error_summary"] for i in issues if i.get("error_summary")]
    return obj_id, blocking


def get_delivery_issues(object_ids: list[str], token: str) -> dict[str, list[str]]:
    if not object_ids:
        return {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        pairs = executor.map(lambda obj_id: _fetch_issues(obj_id, token), object_ids)
    return {obj_id: blocking for obj_id, blocking in pairs if blocking}


def get_last_creative_change_days(account_id: str, token: str, object_id: str) -> int | None:
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    body = _get(
        f"act_{account_id}/activities",
        {
            "since": since,
            "object_id": object_id,
            "fields": "event_type,event_time,object_id",
            "limit": 200,
        },
        token,
    )
    # The API's object_id param doesn't actually filter server-side — it
    # returns activity for other ads and account-level events too, so we
    # have to filter client-side or every ad ends up with the same (wrong)
    # "latest" timestamp.
    creative_events = [
        a
        for a in body.get("data", [])
        if a.get("event_type") in CREATIVE_CHANGE_EVENT_TYPES and a.get("object_id") == object_id
    ]
    if not creative_events:
        return None
    latest = max(a["event_time"] for a in creative_events)
    latest_dt = datetime.datetime.fromisoformat(latest.replace("Z", "+00:00"))
    delta = datetime.datetime.now(datetime.timezone.utc) - latest_dt
    return delta.days
