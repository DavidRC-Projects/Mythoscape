"""In the Resting Ox the player's back shows their head, not the helm they walked in wearing."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "client")))

import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((8, 8))

import resting_ox_bar as bar


def look(helmet):
    return {
        "sex": "male",
        "appearance": {"hair": "hair_crop", "hair_colour": "dark_brown", "skin_tone": "tone_3"},
        "equipment": {"helmet": helmet, "body": "bronze_body"},
    }


def pixels(surf):
    rgb = pygame.surfarray.array3d(surf)
    alpha = pygame.surfarray.array_alpha(surf)
    return rgb, alpha


def test_helm_comes_off_for_the_back_of_the_head():
    worn = look("bronze_helmet")
    assert bar.RestingOxBar._helm_id(worn) == "bronze_helmet"
    shown = bar.RestingOxBar._without_helmet(worn)
    assert worn["equipment"]["helmet"] == "bronze_helmet"
    assert shown["equipment"]["helmet"] is None
    assert bar.RestingOxBar._helm_id(shown) is None
    packed = bar.RestingOxBar._without_helmet(look({"id": "eclipse_helmet"}))
    assert packed["equipment"]["helmet"] is None

    ox = bar.RestingOxBar(None)
    helms = []
    real = bar.RestingOxBar._wear_helm

    def spy(self, helm, bust, front):
        helms.append((helm, front))
        return real(self, helm, bust, front)

    bar.RestingOxBar._wear_helm = spy
    try:
        with_helm = ox._back_figure(worn, 220)
        bare = ox._back_figure(look(None), 220)
    finally:
        bar.RestingOxBar._wear_helm = real

    assert helms == [], helms
    assert with_helm is not None and bare is not None
    a, aa = pixels(with_helm)
    b, ba = pixels(bare)
    assert a.shape == b.shape
    assert int(np.abs(a.astype(int) - b.astype(int)).max()) == 0
    assert int(aa[: aa.shape[0] // 3].max()) > 200

    # The helm art would cover the head if it were still drawn.
    covered = real(ox, "bronze_helmet", bare, False)
    c, _ = pixels(covered)
    assert int(np.abs(c.astype(int) - b.astype(int)).max()) > 20


if __name__ == "__main__":
    test_helm_comes_off_for_the_back_of_the_head()
    print("bar helmet off, back of head shows")
