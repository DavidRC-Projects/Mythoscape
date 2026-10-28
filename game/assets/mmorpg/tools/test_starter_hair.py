"""Starter hair colour (Outfitters): Villager / Village Lady masks on every anim strip;
hair tint applies whenever *_hair.png exists (starters + fire/water), idle and walk,
without bleeding off the head."""
from __future__ import annotations

import glob
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "..", "player_hd", "assets")
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((8, 8))
import player_hd_client as P  # noqa: E402

STARTERS = (
    ("male", "outfit_villager_hd"),
    ("female", "outfit_village_lady_hd"),
)


def test_starter_hair_masks_cover_all_1x_2x_strips():
    for sex, layer in STARTERS:
        for sc in ("1x", "2x"):
            d = os.path.join(ASSETS, sex, sc, layer)
            mains = [
                p for p in glob.glob(os.path.join(d, "*.png"))
                if not p.endswith(("_skin.png", "_hair.png", "_tint.png"))
                and "anchors" not in os.path.basename(p)
            ]
            assert mains, (sex, sc, layer)
            for art in mains:
                hair = art[:-4] + "_hair.png"
                assert os.path.isfile(hair), hair
                # non-empty mask
                import pygame as pg
                surf = pg.image.load(hair)
                assert pg.mask.from_surface(surf).count() > 20, hair


def test_starter_idle_and_walk_hair_follows_colour_on_head():
    for sex in ("male", "female"):
        base = P.get_default_appearance(sex)
        for anim in ("idle", "walk"):
            dark = _px(sex, dict(base, hair_colour="black"), anim)
            blonde = _px(sex, dict(base, hair_colour="blonde"), anim)
            alpha = _alpha(sex, base, anim)
            diff = np.abs(dark - blonde).sum(-1) > 30
            assert diff.sum() > 20, (sex, anim, diff.sum())
            ys = np.nonzero(diff.any(0))[0]
            fig = np.nonzero(alpha.any(0))[0]
            assert len(fig), (sex, anim)
            # hair changes stay in the upper portion of the figure
            assert ys.max() < fig.min() + 0.40 * (fig.max() - fig.min()), (
                sex, anim, ys.max(), fig.min(), fig.max(),
            )
            assert P.last_draw.get("whole") in (
                "outfit_villager_hd", "outfit_village_lady_hd",
            ), P.last_draw


def test_hair_colour_does_not_recolour_skin_idle_or_walk():
    """Black vs blonde must not move face/neck/hand pixels (skin mask region)."""
    for sex in ("male", "female"):
        base = P.get_default_appearance(sex)
        for anim in ("idle", "walk"):
            # Draw once to learn the whole layer, then sample that layer's skin mask.
            _draw(sex, base, anim)
            whole = P.last_draw.get("whole")
            facing = P.last_draw.get("facing") or "s"
            frame = int(P.last_draw.get("frame") or 0)
            skin = P._layer_skin(sex, "2x", whole, anim if anim != "melee" else "idle",
                                 facing, frame, 96, 80)
            # Prefer the anim actually drawn
            anim_draw = P.last_draw.get("anim") or anim
            skin = P._layer_skin(sex, "2x", whole, anim_draw, facing, frame, 96, 80)
            assert skin is not None, (sex, anim, whole)
            dark = _draw(sex, dict(base, hair_colour="black"), anim)
            blonde = _draw(sex, dict(base, hair_colour="blonde"), anim)
            # Align skin mask to the drawn sprite footprint via a full-canvas blit at same feet.
            # Simpler: compare pixels only where the 2x skin frame (scaled to tile) is opaque,
            # sampled from the same draw path's cached surfaces is hard — instead compare
            # rendered figures and require skin-band (forehead) stability using mask overlay.
            d = np.abs(pygame.surfarray.array3d(dark).astype(int)
                       - pygame.surfarray.array3d(blonde).astype(int)).sum(-1)
            # Build a screen-space skin proxy: top-center face box should be stable for
            # male short hair; for both sexes, require that where skin mask is strong on
            # the strip, corresponding figure pixels barely change.
            # Direct approach: re-tint in isolation using the same helpers.
            main = P._frame_surface(f"{sex}/2x/{whole}/{anim_draw}_{facing}.png", frame, "2x", 96, 80)
            assert main is not None
            skin = P._layer_skin(sex, "2x", whole, anim_draw, facing, frame, 96, 80)
            hair = P._hair_without_skin(
                P._layer_hair(sex, "2x", whole, anim_draw, facing, frame, 96, 80), skin,
            )
            skinned = P._skin_whole(main, skin, P.skin_rgb(P.skin_tone_id(base)))
            black = P._skin_whole(skinned, hair, P._parse_hair_colour("black")) if hair else skinned
            blonde_s = P._skin_whole(skinned, hair, P._parse_hair_colour("blonde")) if hair else skinned
            diff = np.abs(pygame.surfarray.array3d(black).astype(int)
                          - pygame.surfarray.array3d(blonde_s).astype(int)).sum(-1)
            sa = pygame.surfarray.array_alpha(skin)
            # Strict: no meaningful change on skin pixels
            bleed = ((diff > 25) & (sa > 80)).sum()
            assert bleed == 0, (sex, anim_draw, facing, frame, int(bleed), whole)
            # And hair still changes somewhere
            assert (diff > 30).sum() > 10, (sex, anim_draw, int((diff > 30).sum()))


def test_fire_set_hair_tint_when_mask_exists():
    """Ungating: collection fire art already had *_hair.png; colour must apply."""
    base = P.get_default_appearance("male")
    look = dict(base, set="set_fire_m", outfit=None, hair_colour="black")
    for k in ("head", "cloak", "held"):
        look[k] = None
    dark = _px("male", look, "idle", starter=False)
    blonde = _px("male", dict(look, hair_colour="blonde"), "idle", starter=False)
    diff = np.abs(dark - blonde).sum(-1) > 30
    assert diff.sum() > 30, diff.sum()
    assert P.last_draw.get("whole") == "outfit_set_fire_m_hd"
    # walk too
    dark = _px("male", look, "walk", starter=False)
    blonde = _px("male", dict(look, hair_colour="blonde"), "walk", starter=False)
    assert (np.abs(dark - blonde).sum(-1) > 30).sum() > 30


def _draw(sex, appearance, anim, starter=True):
    surf = pygame.Surface((240, 240), pygame.SRCALPHA)
    P.draw_player(
        surf, sex, appearance, 120, 210, 96, 0.4,
        anim=anim, progress=0.5, facing=1, starter=starter,
    )
    return surf


def _px(sex, appearance, anim, starter=True):
    return pygame.surfarray.array3d(_draw(sex, appearance, anim, starter)).astype(int)


def _alpha(sex, appearance, anim, starter=True):
    return pygame.surfarray.array_alpha(_draw(sex, appearance, anim, starter))


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    bad = 0
    for n, f in tests:
        try:
            f()
            print("ok  ", n)
        except AssertionError as e:
            bad += 1
            print("FAIL", n, e)
    print(f"{len(tests) - bad}/{len(tests)} starter hair tests passed")
    sys.exit(1 if bad else 0)
