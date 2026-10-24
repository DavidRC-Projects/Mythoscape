"""tools/test_jewellery.py - free starters + Crown Jewels (JEWELLERY_SPEC.md)."""
import json, os, sys, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("JW_CLIENT", os.path.join(HERE, "..", "client")))
import pygame
pygame.init(); pygame.display.set_mode((1, 1))
import jewellery as J
if os.environ.get("JW_ROOT"): J.ROOT = os.environ["JW_ROOT"]
ASSETS = os.environ.get("JW_ASSETS", os.path.join(HERE, "..", "..", "player_hd", "assets"))
LF = os.environ.get("JW_LAYER_F", os.path.join(ASSETS, "female", "2x", "outfit_set_fire_f_hd"))
LM = os.environ.get("JW_LAYER_M", os.path.join(ASSETS, "male", "2x", "outfit_set_fire_m_hd"))
FREE = {"jw_f_wood_bead_necklace": "neck", "jw_f_pearl_drop_earrings": "ears", "jw_f_silver_vine_bangle": "wrist", "jw_f_bone_hair_comb": "head_back",
        "jw_u_brass_brooch": "chest", "jw_m_brass_signet_ring": "hand", "jw_m_iron_tooth_pendant": "neck"}
PRICES = {"lx_f_diamond_gold_necklace": 40000, "lx_f_ruby_parure": 50000, "lx_f_emerald_parure": 50000, "lx_f_sapphire_parure": 50000,
          "lx_f_ruby_ring": 12000, "lx_f_emerald_ring": 12000, "lx_f_sapphire_ring": 12000, "lx_f_diamond_tiara": 60000,
          "lx_f_diamond_drop_earrings": 25000, "lx_f_gem_bracelet": 30000, "lx_f_lilac_necklace": 45000, "lx_f_lilac_ring": 20000, "lx_bundle_lilac_set": 55000}

def render(layer, facing, look, ctx=None, frame=0, anim="idle"):
    st = pygame.image.load(f"{layer}/{anim}_{facing}.png").convert_alpha(); s = st.get_height()
    fr = st.subsurface((frame * s, 0, s, s)).copy()
    dest = pygame.Surface((s, s), pygame.SRCALPHA); dest.blit(fr, (0, 0)); base = dest.copy()
    n = J.draw(dest, fr, pygame.Rect(0, 0, s, s), layer, anim, facing, frame, False, look, ctx or {"preview": True, "t": 0.3})
    return base, dest, n

def diff_in(base, dest, rect):
    r = rect.clip(base.get_rect()); c = 0
    for y in range(r.top, r.bottom):
        for x in range(r.left, r.right):
            if base.get_at((x, y)) != dest.get_at((x, y)): c += 1
    return c

class Catalogue(unittest.TestCase):
    def test_free_starters(self):
        for pid, an in FREE.items():
            it = J.item(pid); self.assertIsNotNone(it, pid)
            self.assertEqual((it["price"], it["free_starter"], it["fx"], it["anchor"]), (0, True, None, an), pid)
            self.assertEqual(it["release"], "live")
        self.assertEqual(J.item("jw_f_wood_bead_necklace")["name"], "Wood Bead Necklace")  # sheet said "Village Lady"
        self.assertEqual(J.item("jw_u_brass_brooch")["sex"], "u")
    def test_paid(self):
        for pid, p in PRICES.items():
            it = J.item(pid); self.assertIsNotNone(it, pid); self.assertEqual(it["price"], p, pid)
            if "bundle" in it: continue
            self.assertFalse(it["free_starter"]); self.assertEqual(it["fx"]["frames"], 12); self.assertAlmostEqual(it["fx"]["loop_s"], 1.8)
            for v, pts in it["sparkle_points"].items(): self.assertLessEqual(len(pts), 6, pid)
            if it.get("release") == "live": self.assertGreaterEqual(it.get("review_score") or 0, 8, pid)
        self.assertEqual(J.item("lx_f_diamond_tiara")["slot"], "headwear")
        self.assertEqual(J.item("lx_bundle_lilac_set")["bundle"], ["lx_f_lilac_necklace", "lx_f_lilac_ring"])
    def test_art(self):
        for pid, it in J.items().items():
            if "bundle" in it: continue
            self.assertTrue(os.path.exists(J.card_path(pid)), pid)
            parts = ["neck_", "ear_"] if it["anchor"] == "neck+ears" else [""]
            for k in (2, 4, 8):
                for p in parts:
                    for v in "sen": self.assertTrue(os.path.exists(os.path.join(J.ROOT, f"{k}x", pid, f"{p}{v}.png")), (pid, k, p, v))

class Rules(unittest.TestCase):
    def test_clashes(self):
        H = J.hidden_reason
        self.assertTrue(H("lx_f_ruby_parure", {"neck": True}))
        self.assertIn("ring", H("lx_f_ruby_parure", {"neck": True}))
        self.assertIsNone(H("lx_f_ruby_ring", {"neck": True}))
        self.assertTrue(H("lx_f_diamond_tiara", {"head": True})); self.assertTrue(H("lx_f_diamond_tiara", {}, {"head": "bronze_helm"}))
        self.assertTrue(H("lx_f_diamond_drop_earrings", {}, {"head": "x"})); self.assertTrue(H("jw_f_pearl_drop_earrings", {"hair_covers_ears": True}))
        self.assertTrue(H("lx_f_diamond_gold_necklace", {}, {"body": "x"})); self.assertTrue(H("lx_f_gem_bracelet", {"sleeves_long": True}))
        self.assertTrue(H("lx_f_lilac_ring", {}, {"hands": "x"})); self.assertTrue(H("jw_f_bone_hair_comb", {}, {}, "s", hood_up=True))
        self.assertTrue(H("jw_f_wood_bead_necklace", {"collar": True}, {}, "e")); self.assertIsNone(H("jw_f_wood_bead_necklace", {"collar": True}, {}, "s"))

class Render(unittest.TestCase):
    def test_draws_each_view(self):
        for f in "sen":
            b, d, n = render(LF, f, {"jewellery": ["jw_f_wood_bead_necklace", "jw_f_pearl_drop_earrings"]}); self.assertGreater(n, 0, f)
            b, d, n = render(LM, f, {"jewellery": ["jw_m_iron_tooth_pendant"]}); self.assertGreaterEqual(n, 0 if f == "n" else 1, f)
    def test_face_rule(self):
        for f in "se":
            A = J.anchor(LF, "idle", f, 0); fb = A["face_box"]; pad = 2 * A["u"]
            face = pygame.Rect(int(fb[0] - pad), int(fb[1] - pad), int(fb[2] - fb[0] + 2 * pad), int(fb[3] - fb[1] + pad))
            for look in ({"jewellery": ["lx_f_diamond_gold_necklace", "jw_f_bone_hair_comb"]}, {"jewellery": ["lx_f_lilac_necklace"], "head": "lx_f_diamond_tiara"}):
                b, d, n = render(LF, f, look, {"armour_glow": True})   # sparkle off: pieces only
                inner = face.inflate(-2, -2)
                if look.get("head"): inner.top = int(fb[1] + A["u"]) + 1; inner.height = int(fb[3]) - inner.top
                self.assertEqual(diff_in(b, d, inner), 0, (f, look))
    def test_never_tinted(self):
        look = {"jewellery": ["lx_f_ruby_parure"]}
        _, d1, _ = render(LF, "s", look, {"armour_glow": True}); _, d2, _ = render(LF, "s", dict(look, skin="tone_9"), {"armour_glow": True})
        self.assertEqual(pygame.image.tobytes(d1, "RGBA"), pygame.image.tobytes(d2, "RGBA"))
    def test_max_two_lit(self):
        import jewellery
        calls = []
        orig = pygame.Surface.blit
        look = {"jewellery": ["lx_f_ruby_parure", "lx_f_ruby_ring"], "head": "lx_f_diamond_tiara"}
        for t in [i * 0.15 for i in range(12)]:
            st = pygame.image.load(f"{LF}/idle_s.png").convert_alpha(); s = st.get_height(); fr = st.subsurface((0, 0, s, s)).copy()
            dest = pygame.Surface((s, s), pygame.SRCALPHA)
            sp = []
            real = J._draw_sparkle
            def spy(dest_, sparks, ctx, u, face, _r=real):
                sp.append(len(sparks)); return _r(dest_, sparks, ctx, u, face)
            J._draw_sparkle = spy
            try: J.draw(dest, fr, pygame.Rect(0, 0, s, s), LF, "idle", "s", 0, False, look, {"preview": True, "t": t})
            finally: J._draw_sparkle = real
            self.assertTrue(sp and sp[0] <= 10 + 6)
    def test_reduced_and_off(self):
        self.assertEqual(J._sparkle_mode({"elemental_full": True}), "reduced"); self.assertEqual(J._sparkle_mode({"preview": True, "elemental_full": True}), "full")
        self.assertEqual(J._sparkle_mode({"armour_glow": True}), "off")
        self.assertEqual(J._sparkle_mode({"preview": True}), "full")

if __name__ == "__main__":
    unittest.main(verbosity=2)
