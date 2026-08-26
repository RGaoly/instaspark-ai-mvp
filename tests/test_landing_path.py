from src.landing_path import LANDING_PATH_ID, landing_path


def test_landing_path_closes_the_loop_without_live_send():
    path = landing_path()
    assert path["path_id"] == LANDING_PATH_ID
    assert len(path["phases"]) == 4
    ids = [item["id"] for item in path["phases"]]
    assert ids == ["dna_freeze", "underwrite_book", "human_desk", "measure_calibrate"]
    assert "Calibrator" in path["closed_loop"]
    assert any("Send to Creator stays disabled" in item for item in path["out_of_scope"])
    assert path["phases"][1]["artifact"].startswith("Evidence Reader")
    assert "2-week" in path["horizon"]
