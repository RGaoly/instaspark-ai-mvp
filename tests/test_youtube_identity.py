from src.youtube_identity import channel_title_matches, pick_matching_channel


def test_channel_title_matches_exact_and_allowed_suffix():
    assert channel_title_matches("Catalina Mesa", "Catalina Mesa")
    assert channel_title_matches("Valeria Vlog", "Valeria vlogs")
    assert channel_title_matches("Emma Peaks", "Emma Peaks Official")
    assert not channel_title_matches("Hayden Brook", "Hayden Brook - Topic")
    assert not channel_title_matches("Avery Drift", "Avery Drift - Topic")


def test_channel_title_rejects_unrelated_and_extra_profession():
    assert not channel_title_matches("Jordan Ridge", "Jordan Ridge Dental")
    assert not channel_title_matches("Ryan Gear", "Ryan's Gear Reviews")
    assert not channel_title_matches("Nia Hollow", "Nia")
    assert not channel_title_matches("Maya Outdoors", "Maya Outdoor Living")
    assert not channel_title_matches("Alex Rides", "Random POV Channel")


def test_pick_matching_channel_takes_first_reasonable_hit():
    items = [
        {"channel_id": "UCdental", "title": "Jordan Ridge Dental"},
        {"channel_id": "UCreal", "title": "Jordan Ridge"},
        {"channel_id": "UCother", "title": "Jordan Ridge Official"},
    ]
    picked = pick_matching_channel("Jordan Ridge", items)
    assert picked["channel_id"] == "UCreal"
    assert pick_matching_channel("Nia Hollow", items) is None
