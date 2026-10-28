"""One-at-a-time HUD click pointers for the early NPC tutorial beats.

Server sends UI_COACH:
  {id, target, text, dismiss_key?}           — single tip
  {id, steps: [{target, text, dismiss_key?, wait?}]}  — guided sequence

`wait` (optional) auto-advances when the player does the right thing:
  open_equipment | unequip_weapon | equip_weapon

Tips that need the world/HUD (not dialogue Accept) wait until the talk box
is closed, so they never fight Tamsin's dialogue for attention.
"""
import math
import time

import pygame

GOLD = (255, 214, 110)
GOLD_DEEP = (205, 140, 40)
PANEL = (18, 22, 40)
DIM = (0, 0, 0, 110)

_TARGETS = (
    "equipment",
    "inventory",
    "inv_filters",
    "skills",
    "dialogue_accept",
    "dialogue_turnin",
    "quests",
    "eat",
    "equip_weapon",
    "inv_sword",
    "auto_pickup",
)

_DIALOGUE_TARGETS = frozenset({"dialogue_accept", "dialogue_turnin"})

TIMEOUT_S = 45.0
SEQUENCE_TIMEOUT_S = 120.0
SWORD_IDS = ("recruit_bronze_sword", "bronze_sword")


def on_message(client, msg):
    """Queue tips that need a free HUD until dialogue is closed."""
    steps = msg.get("steps")
    first_target = None
    if steps:
        for step in steps:
            if step.get("target") in _TARGETS and (step.get("text") or "").strip():
                first_target = step["target"]
                break
    else:
        first_target = msg.get("target")
    # Accept / Turn-in pointers must show while the dialogue is open.
    needs_free_hud = first_target and first_target not in _DIALOGUE_TARGETS
    if needs_free_hud and getattr(client, "dialogue", None):
        client._ui_coach_pending = dict(msg)
        return
    _activate(client, msg)


def flush_pending(client):
    """Call each frame — starts a queued tip once talk is closed."""
    pending = getattr(client, "_ui_coach_pending", None)
    if not pending:
        return
    if getattr(client, "dialogue", None):
        return
    client._ui_coach_pending = None
    _activate(client, pending)


def _activate(client, msg):
    steps = msg.get("steps")
    if steps:
        cleaned = []
        for step in steps:
            target = step.get("target")
            text = (step.get("text") or "").strip()
            if target in _TARGETS and text:
                cleaned.append({
                    "target": target,
                    "text": text,
                    "dismiss_key": (step.get("dismiss_key") or "").lower() or None,
                    "wait": step.get("wait") or None,
                })
        if not cleaned:
            return
        eq = (getattr(client, "player", None) or {}).get("equipment") or {}
        client.ui_coach = {
            "id": msg.get("id") or "sequence",
            "steps": cleaned,
            "step": 0,
            "until": time.time() + SEQUENCE_TIMEOUT_S,
            "pulse": time.time(),
            "weapon_at_start": eq.get("weapon"),
            "paused_for_dialogue": False,
        }
        _prepare_step(client)
        return

    target = msg.get("target")
    text = (msg.get("text") or "").strip()
    if target not in _TARGETS or not text:
        return
    client.ui_coach = {
        "id": msg.get("id") or target,
        "target": target,
        "text": text,
        "dismiss_key": (msg.get("dismiss_key") or "").lower() or None,
        "until": time.time() + TIMEOUT_S,
        "pulse": time.time(),
        "steps": None,
        "step": 0,
        "paused_for_dialogue": False,
    }
    _prepare_panel(client, target)


def clear(client, completed=False):
    tip = getattr(client, "ui_coach", None)
    coach_id = (tip or {}).get("id")
    client.ui_coach = None
    if completed and coach_id in ("equip_gear", "equip_gear_v2"):
        _after_gear(client)


def _after_gear(client):
    """Point them at Sarah next — eating is the other life skill before rats."""
    for npc in getattr(client, "npcs", None) or []:
        if npc.get("id") == "innkeeper_sarah" and npc.get("x") is not None:
            try:
                import new_player_guide
                new_player_guide.set_waypoint(
                    client, int(npc["x"]), int(npc["y"]), "Innkeeper Sarah",
                )
            except Exception:
                pass
            client.add_chat(
                "Next: Innkeeper Sarah (arrow) — food and potions restore HP.",
                color=GOLD, highlight=True,
            )
            return


def active(client):
    tip = getattr(client, "ui_coach", None)
    if not tip:
        return False
    # Don't burn the timer while a talk box is covering the HUD tip.
    if getattr(client, "dialogue", None) and tip.get("target") not in _DIALOGUE_TARGETS:
        tip["until"] = time.time() + TIMEOUT_S
        return True
    if time.time() > float(tip.get("until") or 0):
        clear(client)
        return False
    return True


def _current(tip):
    steps = tip.get("steps")
    if steps:
        i = int(tip.get("step") or 0)
        if 0 <= i < len(steps):
            return steps[i]
        return None
    return tip


def _prepare_step(client):
    tip = getattr(client, "ui_coach", None)
    cur = _current(tip) if tip else None
    if not cur:
        clear(client, completed=True)
        return
    tip["pulse"] = time.time()
    tip["until"] = time.time() + SEQUENCE_TIMEOUT_S
    tip["target"] = cur["target"]
    tip["text"] = cur["text"]
    tip["dismiss_key"] = cur.get("dismiss_key")
    tip["wait"] = cur.get("wait")
    if cur.get("wait") != "open_equipment" and cur["target"] != "equipment":
        _prepare_panel(client, cur["target"])
    elif cur["target"] in ("equip_weapon", "inv_sword"):
        client.show_equipment = True
        try:
            import hud_v2
            hud_v2.ensure(client)
            client.hud_system = "inventory"
        except Exception:
            pass


def _prepare_panel(client, target):
    if target in ("equipment", "equip_weapon", "inv_sword"):
        if target != "equipment":
            client.show_equipment = True
        client.show_skills = False
        client.show_travel = False
        try:
            import hud_v2
            hud_v2.ensure(client)
            client.hud_system = "inventory"
        except Exception:
            pass
    elif target == "skills":
        client.show_skills = True
        client.show_equipment = False
    elif target in ("inventory", "inv_filters"):
        try:
            import hud_v2
            hud_v2.ensure(client)
            client.hud_system = "inventory"
            client.hud_focus = None
        except Exception:
            pass
    elif target == "auto_pickup":
        # Toggle now sits on the combat bar — no menu needed.
        pass


def _advance(client):
    tip = getattr(client, "ui_coach", None)
    if not tip or not tip.get("steps"):
        clear(client, completed=True)
        return
    tip["step"] = int(tip.get("step") or 0) + 1
    if tip["step"] >= len(tip["steps"]):
        clear(client, completed=True)
        return
    _prepare_step(client)


def _weapon_id(client):
    return ((getattr(client, "player", None) or {}).get("equipment") or {}).get("weapon")


def _check_wait(client):
    tip = getattr(client, "ui_coach", None)
    cur = _current(tip) if tip else None
    if not cur:
        return
    wait = cur.get("wait")
    if wait == "open_equipment" and getattr(client, "show_equipment", False):
        _advance(client)
    elif wait == "unequip_weapon" and not _weapon_id(client):
        _advance(client)
    elif wait == "equip_weapon" and _weapon_id(client):
        _advance(client)


def _inv_sword_rect(client):
    inv = (getattr(client, "player", None) or {}).get("inventory") or {}
    slots = (getattr(client, "hud_rects", None) or {}).get("slots") or {}
    for slot, entry in inv.items():
        if not entry or entry.get("item_id") not in SWORD_IDS:
            continue
        key = slot if slot in slots else (int(slot) if str(slot).isdigit() else slot)
        if key not in slots and str(slot) in slots:
            key = str(slot)
        rect = slots.get(key)
        if rect is not None:
            return rect
    return None


def _resolve_rect(client, target):
    if target == "equipment":
        return (getattr(client, "hud_rects", None) or {}).get("equipment")
    if target == "inventory":
        rects = getattr(client, "hud_rects", None) or {}
        systems = rects.get("systems") or {}
        if systems.get("inventory"):
            return systems["inventory"]
        slots = rects.get("slots") or {}
        if slots:
            return next(iter(slots.values()))
        return None
    if target == "inv_filters":
        rects = getattr(client, "hud_rects", None) or {}
        if rects.get("inv_filters"):
            return rects["inv_filters"]
        chips = rects.get("filters") or {}
        if chips:
            xs = [r.x for r in chips.values()]
            ys = [r.y for r in chips.values()]
            rights = [r.right for r in chips.values()]
            bottoms = [r.bottom for r in chips.values()]
            return pygame.Rect(min(xs), min(ys), max(rights) - min(xs), max(bottoms) - min(ys))
        return rects.get("systems", {}).get("inventory")
    if target == "skills":
        rects = getattr(client, "hud_rects", None) or {}
        return rects.get("skills") or getattr(client, "skills_btn_rect", None)
    if target == "dialogue_accept":
        return (getattr(client, "dialogue_btn_rects", None) or {}).get("accept")
    if target == "dialogue_turnin":
        return (getattr(client, "dialogue_btn_rects", None) or {}).get("turnin")
    if target == "quests":
        nav = ((getattr(client, "hud_world_rects", None) or {}).get("nav") or {})
        return nav.get("quests")
    if target == "eat":
        actions = ((getattr(client, "hud_world_rects", None) or {}).get("actions") or {})
        return actions.get("eat")
    if target == "equip_weapon":
        return (getattr(client, "equip_slot_rects", None) or {}).get("weapon")
    if target == "inv_sword":
        return _inv_sword_rect(client)
    if target == "auto_pickup":
        world = getattr(client, "hud_world_rects", None) or {}
        if world.get("auto_pickup"):
            return world["auto_pickup"]
        return getattr(client, "auto_pickup_btn_rect", None)
    return None


def handle_event(client, event):
    flush_pending(client)
    if not active(client):
        return False
    tip = client.ui_coach
    cur = _current(tip)
    if not cur:
        return False
    if event.type == pygame.KEYDOWN:
        key = cur.get("dismiss_key") or tip.get("dismiss_key")
        if key == "e" and event.key == pygame.K_e:
            return False
        if key == "tab" and event.key == pygame.K_TAB:
            clear(client)
            return False
        if key == "a" and event.key in (pygame.K_a, pygame.K_RETURN):
            clear(client)
            return False
        if key == "t" and event.key == pygame.K_t:
            clear(client)
            return False
        if key == "r" and event.key == pygame.K_r:
            clear(client)
            return False
        if key == "p" and event.key == pygame.K_p:
            clear(client)
            return False
        if event.key == pygame.K_x:
            clear(client)
            return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        rect = _resolve_rect(client, cur["target"])
        tip_rect = getattr(client, "_ui_coach_tip_rect", None)
        if rect and rect.collidepoint(event.pos):
            if tip.get("steps"):
                if cur.get("wait") in ("open_equipment", "unequip_weapon", "equip_weapon"):
                    return False
                _advance(client)
            else:
                clear(client)
            return False
        if tip_rect and tip_rect.collidepoint(event.pos):
            clear(client)
            return True
    return False


def draw(client):
    flush_pending(client)
    if not active(client):
        client._ui_coach_tip_rect = None
        return
    _check_wait(client)
    if not active(client):
        client._ui_coach_tip_rect = None
        return
    tip = client.ui_coach
    cur = _current(tip)
    if not cur:
        client._ui_coach_tip_rect = None
        return
    # Gear tips wait for talk to close (already queued); Accept/Turn-in show over dialogue.
    if getattr(client, "dialogue", None) and cur["target"] not in _DIALOGUE_TARGETS:
        client._ui_coach_tip_rect = None
        return
    rect = _resolve_rect(client, cur["target"])
    if rect is None:
        return
    surf = client.screen
    # Soft dim outside the target so the ring is obvious.
    try:
        veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        veil.fill(DIM)
        pad = rect.inflate(16, 16)
        veil.fill((0, 0, 0, 0), pad.clip(veil.get_rect()))
        surf.blit(veil, (0, 0))
    except Exception:
        pass

    pulse = 0.55 + 0.45 * abs(math.sin((time.time() - tip["pulse"]) * 4.0))
    ring = max(4, int(4 + 3 * pulse))
    pygame.draw.rect(surf, GOLD, rect.inflate(14, 14), ring, border_radius=8)
    pygame.draw.rect(surf, (255, 255, 200), rect.inflate(6, 6), 2, border_radius=6)

    font = client.font_small
    header = "→ CLICK HERE"
    body_lines = _wrap(cur["text"], font, 300)
    pad_x, pad_y = 12, 10
    line_h = font.get_height() + 2
    box_w = 300 + pad_x * 2
    box_h = pad_y * 2 + line_h * (1 + len(body_lines)) + 18
    steps = tip.get("steps")
    bx = max(8, min(surf.get_width() - box_w - 8, rect.centerx - box_w // 2))
    by = rect.y - box_h - 16
    if by < 8:
        by = rect.bottom + 16
    box = pygame.Rect(bx, by, box_w, box_h)
    pygame.draw.rect(surf, PANEL, box, border_radius=8)
    pygame.draw.rect(surf, GOLD, box, 2, border_radius=8)
    y = box.y + pad_y
    surf.blit(font.render(header, True, GOLD), (box.x + pad_x, y))
    y += line_h + 2
    for line in body_lines:
        surf.blit(font.render(line, True, (230, 230, 235)), (box.x + pad_x, y))
        y += line_h
    if steps:
        n = int(tip.get("step") or 0) + 1
        footer = f"Step {n} of {len(steps)}  ·  X to skip"
    else:
        footer = "X to dismiss"
    surf.blit(client.font_tiny.render(footer, True, (160, 170, 185)), (box.x + pad_x, box.bottom - 14))

    ax, ay = box.centerx, (box.bottom if by < rect.y else box.y)
    tx, ty = rect.centerx, (rect.y if by < rect.y else rect.bottom)
    pygame.draw.line(surf, GOLD, (ax, ay), (tx, ty), 3)
    client._ui_coach_tip_rect = box


def _wrap(text, font, width):
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if font.size(trial)[0] <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines
