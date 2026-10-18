# Female helmet head-hide mask: code change (short)

**Why:** the female Eclipse helmet is about 80% of the male worn size, which is smaller than the female head. The art now ships a mask layer whose job is to erase the body's head, face, ears and hair under the helmet, so no skin ever shows through or around it. The male helmet doesn't need a mask.

**New asset (female only):** `game/assets/player_hd/assets/female/<1x|2x|4x>/arm_helm_eclipse_hide/<anim>_<facing>.png`
- It has the same strips, canvas, frame counts and facings as `arm_helm_eclipse`. West is east mirrored, as usual.
- Its catalogue entry in `armour_layers` is `"id": "arm_helm_eclipse_hide"`, with `"role": "erase_mask"`, `"mask_for": "arm_helm_eclipse"` and `"z_class": "mask_head"`.
- **Never draw it.** Only its alpha channel is used.

**Change in `client/player_hd_client.py` (compositor):**
1. When the resolved helmet layer is `arm_helm_eclipse` and the sex is female, load the matching `arm_helm_eclipse_hide` frame (same anim, facing, frame and scale, mirrored for west).
2. Composite every layer whose z is below the helmet (body, hair, brows, outfit and so on) into the working surface as usual. Then, before drawing the helmet, multiply that surface's alpha by `(1 - mask_alpha)`:
   - pygame: `surf.blit(mask_inverted, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)`.
   - `mask_inverted` is the mask frame with RGB set to 255 and alpha replaced by 255 - mask alpha.
   - Build it once per frame and cache it alongside the strip.
3. Draw the helmet and every layer above it (weapon at z 90 and so on) normally, after the erase.
   - Arms or weapons in front of the face aren't erased: the mask already has holes where the arms cover the head.
4. Hair is already hidden by `covers: ["hair"]`. Keep that.
5. Apply the same erase in the Equipment & Stats paper doll, which uses the same compositor.
6. No flag and no fallback: if the mask file is missing, log a warning once and draw as today.
7. **Test:** for a female with `eclipse_helmet`, idle_s/e/n and melee_e at 1x/2x/4x, assert that no pixel inside the mask has body alpha after compositing. Male results must be byte-identical to before.
