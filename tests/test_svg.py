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
