from types import SimpleNamespace

from app.station_groups import group_apparatus_by_station, sort_station_labels


def test_sort_station_labels_station_first_then_descending():
    labels = [
        "AFD Shop",
        "Station 204",
        "Quaker Lane",
        "Station 206",
        "station 205",
        "Unassigned",
    ]
    ordered = sort_station_labels(labels)
    assert ordered[:3] == ["Station 206", "station 205", "Station 204"]
    assert ordered[3:] == ["Unassigned", "Quaker Lane", "AFD Shop"]


def test_group_apparatus_by_station():
    rows = [
        SimpleNamespace(
            vehicle_id=1,
            unit_name="Engine 206",
            app_unit="5562",
            station="Station 206",
            vehicle_type="Engine",
            status="IN SERVICE",
            status_class="text-success",
            status_display_raw="IN SERVICE",
            in_reserve=0,
        ),
        SimpleNamespace(
            vehicle_id=2,
            unit_name="Medic Reserve",
            app_unit="5214",
            station="AFD Shop",
            vehicle_type="Medic",
            status="OUT OF SERVICE",
            status_class="",
            status_display_raw=None,
            in_reserve=1,
        ),
        SimpleNamespace(
            vehicle_id=3,
            unit_name="Ladder 204",
            app_unit="5401",
            station="Station 204",
            vehicle_type="Ladder",
            status="IN SERVICE",
            status_class="",
            status_display_raw="IN SERVICE",
            in_reserve=0,
        ),
    ]
    payload = group_apparatus_by_station(rows)
    assert payload["total"] == 3
    assert [g["station"] for g in payload["by_station"]] == [
        "Station 206",
        "Station 204",
        "AFD Shop",
    ]
    shop = payload["by_station"][-1]["apparatus"][0]
    assert shop["name"] == "Medic Reserve"
    assert shop["in_reserve"] == 1
    assert shop["door_number"] == "5214"


def test_empty_station_becomes_unassigned():
    rows = [
        SimpleNamespace(
            vehicle_id=9,
            unit_name="Spare",
            app_unit="",
            station="  ",
            vehicle_type="",
            status="",
            status_class="",
            status_display_raw="",
            in_reserve=0,
        )
    ]
    payload = group_apparatus_by_station(rows)
    assert payload["by_station"][0]["station"] == "Unassigned"
