from app.models.scrape_config import ScrapeConfig


def test_reserve_homes_empty_and_many():
    cfg = ScrapeConfig()
    assert cfg.get_reserve_homes() == []

    cfg.set_reserve_homes(None)
    assert cfg.reserve_homes == ""
    assert cfg.get_reserve_homes() == []

    cfg.set_reserve_homes([])
    assert cfg.get_reserve_homes() == []

    cfg.set_reserve_homes(["Station 201", "Quaker Lane", "station 201", "  "])
    assert cfg.get_reserve_homes() == ["Station 201", "Quaker Lane"]

    cfg.set_reserve_homes("AFD Shop, Station 206\nStation 204")
    assert cfg.get_reserve_homes() == ["AFD Shop", "Station 206", "Station 204"]
