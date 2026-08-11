import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import meta_client as mc


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def test_get_last_creative_change_days_ignores_events_from_other_objects():
    now = datetime.now(timezone.utc)
    fake_response = {
        "data": [
            # Account-level event and another ad's event, both more recent
            # than this ad's real change — must not leak into the result.
            {"event_type": "add_images", "event_time": _iso(now), "object_id": "act_999"},
            {"event_type": "update_ad_creative", "event_time": _iso(now), "object_id": "some_other_ad"},
            {
                "event_type": "update_ad_creative",
                "event_time": _iso(now - timedelta(days=10)),
                "object_id": "target_ad",
            },
        ]
    }
    with patch.object(mc, "_get", return_value=fake_response):
        result = mc.get_last_creative_change_days("123", "token", "target_ad")

    assert result == 10


def test_get_last_creative_change_days_returns_none_when_no_matching_events():
    fake_response = {
        "data": [
            {"event_type": "update_ad_creative", "event_time": _iso(datetime.now(timezone.utc)), "object_id": "other_ad"},
        ]
    }
    with patch.object(mc, "_get", return_value=fake_response):
        result = mc.get_last_creative_change_days("123", "token", "target_ad")

    assert result is None
