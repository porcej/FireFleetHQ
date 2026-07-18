from app.pstrax_alerts_map import (
    alert_kwargs_from_pstrax,
    parse_alert_comments,
    parse_alerts_payload,
)


def test_alert_kwargs_from_sample_row():
    row = {
        "DT_RowId": "id_1466822",
        "alertid": 1466822,
        "alertdate": "09/05/2025 06:47 AM",
        "category": "Fire Maintenance",
        "appname": "Engine 206 | #5562",
        "poststation": "Station 206",
        "currentlocation": "AFD Shop",
        "alerttext": "DAILY CHECKS - PUMP - Side intake leak.<br/>",
        "openedby": "Carlson, Theresa",
        "priority": "Routine",
        "lastupdate": "09/05/2025 06:47 AM",
        "withimage": 0,
        "cost": "",
    }
    kw = alert_kwargs_from_pstrax(row)
    assert kw["alert_id"] == 1466822
    assert kw["app_name"] == "Engine 206 | #5562"
    assert kw["post_station"] == "Station 206"
    assert kw["current_location"] == "AFD Shop"
    assert "leak" in (kw["alert_text"] or "").lower()
    assert "<br" not in (kw["alert_text"] or "").lower()
    assert kw["priority"] == "Routine"


def test_parse_alerts_payload():
    rows = parse_alerts_payload({"data": [{"alertid": 1}, {"alertid": 2}]})
    assert len(rows) == 2


def test_parse_alert_comments():
    html = (
        "<dt>July 28, 2022 09:42 AM - Scott Corder:</dt>"
        "<dd>Rear passenger wheel fender</dd>"
        "<dt>November 27, 2022 11:07 AM - Warren Sollers:</dt>"
        "<dd>Large scratch inside of the EMS logo</dd>"
    )
    entries = parse_alert_comments(html)
    assert len(entries) == 2
    assert "Scott Corder" in entries[0]["header"]
    assert "wheel fender" in entries[0]["body"]
    assert parse_alert_comments(None) == []
    assert parse_alert_comments("") == []
