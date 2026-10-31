"""Creator: male->female switch uses the female HD starter figure; Outfits tab lists every set."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client"))
import pygame


class _Net:
    def __init__(self): self.sent = []
    def send(self, *a, **k): self.sent.append((a, k))


class _C:
    def __init__(self): self.net = _Net(); self.player = {"gender": "male"}; self.needs_appearance = True


def test_switch_and_outfits():
    pygame.init(); scr = pygame.display.set_mode((1200, 800))
    import cosmetics_ui as C, player_hd_client as P
    ui = C.Outfitters(_C()); ui.open("creator")
    ui.look["skin_tone"] = "tone_6"; ui.look["hair_colour"] = "black"
    ui._toggle_sex()
    fem = ui.sex == "female"
    assert fem
    starter = (C._catalogue().get("starter_sets") or {}).get("female")
    for slot in ("outfit", "head", "held", "hair"):
        item = C._by_id(ui.look.get(slot))
        assert not item or item.get("sex") in (None, "female"), (slot, ui.look.get(slot))
    if starter:
        assert ui.look.get("set") == starter, ui.look
    assert ui.look["skin_tone"] == "tone_6" and ui.look["hair_colour"] == "black"
    ui.tab = "outfits"; ui.render(scr)
    cards = [p for k, _r, p in ui.hit if k == "creator_set"]
    assert set(ui._set_order()) <= set(cards)
    locked = [s for s in cards if s != starter]
    if locked:
        ui._activate("creator_set", locked[0]); assert ui.creator_peek == locked[0]
        ui._activate("confirm", None)
        sent = ui.client.net.sent[-1][1]["appearance"]
        assert sent.get("set") != locked[0], "preview must never be confirmed"


if __name__ == "__main__":
    test_switch_and_outfits(); print("creator switch test passed")
