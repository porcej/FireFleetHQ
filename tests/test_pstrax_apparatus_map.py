"""Unit tests for apparatus field mapping (no live PSTrax required)."""

from app.pstrax_apparatus_map import (
    apparatus_kwargs_from_pstrax,
    parse_department_status_html,
    parse_department_status_payload,
)


def test_kwargs_from_json_row():
    row = {
        "app_id": 8374,
        "app_name": "Engine 201",
        "app_unit": "#5563",
        "station_name": "Station 201",
        "vehicle_type": "Engine",
        "service_param": "IN SERVICE",
        "service_class": "inServiceBadge",
        "alerts": 9,
        "checks_due": "74",
        "scba_due": "19",
        "assets_due": 0,
        "supplies_due": 0,
    }
    kw = apparatus_kwargs_from_pstrax(row)
    assert kw["vehicle_id"] == 8374
    assert kw["unit_name"] == "Engine 201"  # Assignment / app_name
    assert kw["app_unit"] == "#5563"  # Door # / app_unit
    assert kw["station"] == "Station 201"
    assert kw["status"] == "IN SERVICE"
    assert kw["status_class"] == "inServiceBadge"
    assert kw["open_alerts"] == 9
    assert kw["checks_due"] == 74


def test_in_service_reserve_displays_as_reserve():
    row = {
        "app_id": 5346,
        "app_name": "Truck (Reserve - Seagrave)",
        "service_param": "IN SERVICE",
        "service_class": "inServiceBadge",
        "in_reserve": 1,
        "in_service": 1,
        "alerts": 0,
        "checks_due": 0,
    }
    kw = apparatus_kwargs_from_pstrax(row)
    assert kw["status"] == "Reserve"
    assert kw["in_service"] == 1
    assert kw["in_reserve"] == 1


def test_parse_payload_datatables():
    payload = {"data": [{"vehicle_id": 1, "unit_name": "L1"}]}
    rows = parse_department_status_payload(payload)
    assert len(rows) == 1
    assert rows[0]["vehicle_id"] == 1


def test_parse_html_table():
    html = """
    <table id="fleet-status">
      <thead><tr><th>Unit</th><th>Station</th><th>Status</th><th>Alerts</th><th>Checks Due</th></tr></thead>
      <tbody>
        <tr id="veh_99"><td>R2</td><td>HQ</td><td>OOS</td><td>1</td><td>4</td></tr>
      </tbody>
    </table>
    """
    rows = parse_department_status_html(html)
    assert len(rows) == 1
    assert rows[0]["vehicleid"] == 99
    assert rows[0].get("unit_name") == "R2" or rows[0].get("unit") == "R2"
