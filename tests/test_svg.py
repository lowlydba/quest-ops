import json
import xml.etree.ElementTree as ET

from questops import svg
from questops.state import Character


def test_card_is_well_formed_svg():
    ch = Character.create("octocat & <friends>")
    ch.accessory = "Crown of the Main Branch [legendary]"
    ch.main_hand = "Intern's Staff [common]"
    root = ET.fromstring(svg.card(ch))
    assert root.tag.endswith("svg")


def test_badges_follow_the_shields_endpoint_schema():
    ch = Character.create("octocat")
    for payload in svg.badges_json(ch).values():
        data = json.loads(payload)
        assert data["schemaVersion"] == 1 and {"label", "message", "color"} <= set(data)


def test_one_combined_badge_and_a_card_that_follows_the_viewers_theme():
    ch = Character.create("octocat")
    ch.kens = 12345
    hero = json.loads(svg.badges_json(ch)["hero"])
    assert hero["label"] == "octocat" and hero["message"] == f"Lv {ch.level} {ch.cls} \u00b7 1 toh 2,345 'kens"
    card = svg.card(ch)
    assert "prefers-color-scheme:light" in card and 'class="f0 s3"' in card  # background and border retheme
    assert 'fill="#0d1117"' in card  # the plain attribute stays as the dark fallback
    assert ET.fromstring(card) is not None
