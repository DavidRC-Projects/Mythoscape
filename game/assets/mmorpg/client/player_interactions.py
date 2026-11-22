"""Player-only picking, menus and chase. NPC/object menus stay in GameClient."""
import time
import pygame
import kcs_client as siege


def _people(client):
    """Players, plus siege mercenaries (negative ids) so they can be clicked and chased like players."""
    people = client.players or {}
    if siege.active(client):
        mercs = getattr(siege.view_of(client), "mercs", None) or {}
        if mercs:
            people = {**people, **mercs}
    return people


def attack_reason(client, person):
    if not person or person.get("id") == (client.player or {}).get("id"):
        return "Choose another player."
    if int(person.get("hp", 1)) <= 0:
        return "That player is down."
    if siege.active(client):
        view = siege.view_of(client)
        if (client.dungeon or {}).get("mode") != "combatant":
            return "Spectators cannot attack."
        side = person.get("kcs_side")
        if side not in ("attack", "defend") or person.get("kcs_mode") != "combatant":
            return "That player is not a fighter."
        if side == view.your_side:
            return "That player is on your side."
        return ""
    if client.dungeon:
        return "PvP is not allowed in this dungeon."
    if not (client.player or {}).get("player_killer"):
        return "Turn on PvP to attack players."
    if not person.get("player_killer"):
        return "That player has PvP turned off."
    return ""


def menu_rows(client, person):
    rows = [{"label": "Walk here", "kind": "walk", "x": person["x"], "y": person["y"], "beside_player":person["id"]}]
    reason = attack_reason(client, person)
    rows.append({"label": "Attack — " + reason if reason else "Attack " + (person.get("name") or "player"),
                 "kind": "info" if reason else "attack_player", "id": person["id"]})
    if not siege.active(client):
        rows.append({"label": "Trade with " + (person.get("name") or "player"), "kind": "trade",
                     "id": person["id"], "x": person["x"], "y": person["y"]})
    return rows


def player_at(client, pos):
    """Pick painted torso, not only the tile below its feet (especially on walls)."""
    picks = []
    view = siege.view_of(client)
    for person in _people(client).values():
        if person.get("id") == (client.player or {}).get("id") or (siege.active(client) and person.get("id") in view.eliminated):
            continue
        if siege.active(client):
            xy = view.motion.get(person["id"], {}).get("draw", (person["x"], person["y"]))
            foot = siege._actor_floor_spot(client, view, xy)
            if foot is None:
                continue
            scale = max(.38, min(1.15, view.scale / 28.))
            w, h = max(18, int(45*scale)), max(28, int(100*scale))
        else:
            rect = client.map_screen_rect(person["x"], person["y"])
            foot = (rect.centerx, rect.bottom)
            w, h = max(18, int(rect.width*.85)), max(28, int(rect.height*1.8))
        rect = pygame.Rect(foot[0]-w//2, foot[1]-h, w, h+5)
        if rect.collidepoint(pos):
            picks.append((abs(pos[0]-foot[0])+abs(pos[1]-(foot[1]-h*.45)), person))
    return min(picks, key=lambda row: row[0])[1] if picks else None


def on_click(client, pos, button):
    person = player_at(client, pos)
    if person is None:
        return False
    if button == 3:
        client._open_context_menu(*pos, menu_rows(client, person))
    elif button == 1:
        if siege.active(client):
            if person.get("kcs_side") and person.get("kcs_side") == siege.view_of(client).your_side:
                return False   # friendlies (your mercenaries crowd round you) never swallow a gate/rock click
            start_attack(client, person["id"])
        else:
            # Left click is harmless in the normal game; trade is explicit.
            walk_here(client, person["x"], person["y"])
    return True


def walk_here(client, x, y):
    client.clear_walk()
    occupied = any(p.get("id") != (client.player or {}).get("id") and (p.get("x"),p.get("y")) == (x,y)
                   for p in (client.players or {}).values())
    goals = client.adjacent_goals(x,y) if occupied else {(x,y)}
    client.walk_and_act(goals)


def start_attack(client, pid):
    person = _people(client).get(pid)
    reason = attack_reason(client, person)
    if reason:
        client.add_chat(reason)
        if siege.active(client): siege.note(client, reason, error=True)
        return
    client._opening_attack_id = None
    client._engine_attack_id = None
    client.clear_walk()
    client._player_attack_target = pid
    client._player_attack_next = 0.
    client._player_attack_started = time.monotonic()
    if siege.active(client):
        siege.view_of(client).build = False
        siege.view_of(client).inspect = None


def tick(client):
    pid = getattr(client, "_player_attack_target", None)
    if pid is None:
        return
    person = _people(client).get(pid)
    if attack_reason(client, person):
        client.clear_walk()
        return
    px, py = map(int, client.player_xy())
    reach = client.equipped_bow_range()
    if siege.active(client) and client.player_using_bow() and ((siege.view_of(client).status or {}).get('economy') or {}).get('wallwalk_bow_bonus'):reach+=2
    if siege.active(client) and not client.player_using_bow():
        import kcs_balance
        reach = kcs_balance.player_range()
    if max(abs(px-person["x"]), abs(py-person["y"])) <= reach:
        client.walk_path = []
        client.walk_goal = None
        client._player_attack_started = time.monotonic()
        if time.time() >= getattr(client, "_player_attack_next", 0):
            from kcs_animation import attack_profile
            profile = attack_profile((client.player or {}).get("equipment"))
            client.net.send("KCS_STRIKE" if siege.active(client) else "ATTACK_PLAYER", target_player_id=pid)
            interval = 1.2
            if not siege.active(client) and not client.player_using_bow():
                from content import weapon_stats, SWING_SECONDS_PER_SPEED
                stats = weapon_stats((client.player or {}).get("equipment", {}).get("weapon"))
                if stats: interval = SWING_SECONDS_PER_SPEED*float(stats["attack_speed"])
            client._player_attack_next = time.time() + max(interval+.08, profile["duration"]+.08)
        return
    if time.monotonic() - client._player_attack_started > 30:
        client.add_chat("Couldn't reach that player.")
        client.clear_walk()
        return
    goals = {(person["x"]+dx, person["y"]+dy)
             for dx in range(-reach, reach+1) for dy in range(-reach, reach+1)
             if (dx or dy) and client.tile_walkable(person["x"]+dx, person["y"]+dy)}
    if not client.walk_path or tuple(client.walk_path[-1]) not in goals:
        path = client.find_path(px, py, goals)
        if path is None:
            client.add_chat("Can't reach that player. A wall or closed gate is in the way.")
            client.clear_walk()
            return
        client.walk_path = path
        client.walk_goal = path[-1] if path else None
        client.pending_action = None
        client._next_walk_at = 0


def siege_walkable(client, x, y):
    view = siege.view_of(client)
    if view.bf is None:
        return False
    from kings_castle_siege_map.layout import walkable
    if (view.status or {}).get('decor'):
        import kcs_decor
        if (x,y) in kcs_decor.blocked(view.bf.plane):return False
    states = {r.get("id") or r.get("opening_id"): r.get("state", "intact") for r in view.openings}
    blocked, crossings = set(), set()
    import kcs_balance
    for engine in view.engines:
        tiles = {tuple(t) for t in engine.get("tiles", [])}
        if engine.get("engine_type") in ("ladder", "siege_tower"):
            if int(engine.get("hp", 1)) > 0:
                crossings.update(tiles)
                dx, dy = kcs_balance.FACE[int(engine.get("rotation", 0)) % 360]
                edge = (min(t[1] for t in tiles) if dy < 0 else max(t[1] for t in tiles)) if dy else (max(t[0] for t in tiles) if dx > 0 else min(t[0] for t in tiles))
                noses = [t for t in tiles if t[1 if dy else 0] == edge]
                nose_x, nose_y = (int(round(sum(t[i] for t in noses)/len(noses))) for i in (0, 1))
                crossed = False
                for step in range(1, 6):
                    nx, ny = nose_x+dx*step, nose_y+dy*step
                    if not view.bf.plane.in_bounds(nx, ny): break
                    crossings.add((nx, ny))
                    ground = walkable(view.bf.plane, nx, ny, states)
                    if ground and crossed: break
                    if not ground: crossed = True
        else:
            blocked.update(tiles)
    if (x, y) in blocked:return False
    if (view.status or {}).get('economy'):
        import kcs_engineering
        for op in view.openings:
            if (op.get('id') or op.get('opening_id')) in kcs_engineering.SALLY_GATES and view.your_side=='defend' and any((x,y)==tuple(t) for t in op.get('tiles',[])):return True
        return walkable(view.bf.plane,x,y,states)
    return (x, y) in crossings or walkable(view.bf.plane, x, y, states)


def siege_step(client,ax,ay,bx,by):
    view=siege.view_of(client)
    if not (view.status or {}).get('economy'):return True
    import kcs_engineering,types
    p=view.bf.plane
    proxy=types.SimpleNamespace(width=p.width,height=p.height,rows=p.grid,in_bounds=p.in_bounds,opening_rects={key:obj.rect for key,obj in p.openings.items()},landmarks={key:obj.rect for key,obj in p.landmarks.items()})
    states={r.get('id') or r.get('opening_id'):r.get('state') for r in view.openings}
    if view.your_side=='defend' and kcs_engineering.in_sally(proxy.opening_rects,(ax,ay),(bx,by)):return True
    return kcs_engineering.height_step(proxy,states,ax,ay,bx,by)


def pvp_view(client):
    view = getattr(client, "_pvp_view", None)
    if view is None:
        view = client._pvp_view = siege.SiegeView()
    return view


def on_fight(client, msg):
    if msg.get("active"):
        client._player_fight = dict(msg, expires_at=time.time()+float(msg.get("expires_after", 20)))
        client._player_attack_target = None  # server owns BOTH fighters' repeat swings
        client.walk_path = []
        client.walk_goal = None
        client._combat_active_until = time.time()+8
        if client.player:
            client.player["combat_facing"] = msg.get("facing")
            client.player["combat_target_player_id"] = msg.get("opponent_id")
    else:
        client._player_fight = None
        client._player_attack_target = None
        if client.player:
            client.player["combat_facing"] = None
            client.player["combat_target_player_id"] = None


def on_disconnect(client):
    """A reconnect must never keep an old lock, target, or facing cache."""
    on_fight(client, {"active":False})
    for person in (getattr(client, "players", {}) or {}).values():
        person["combat_facing"] = None
        person["combat_target_player_id"] = None
    for view in (getattr(client, "_pvp_view", None), getattr(client, "kcs_view", None)):
        if view is not None:
            view.combat_facings = {}
            view.actor_actions.clear()
            view.actor_hits.clear()
            view.shots.clear()
            view.arrow_hp = []


def combat_facing(client, pid, fallback=None):
    view = pvp_view(client)
    return getattr(view, "combat_facings", {}).get(pid, fallback)


def on_message(client, msg):
    view = pvp_view(client)
    event = msg["event"]
    siege._apply_delta(client, view, event)
    # The shared view.shots list draws PvP arrows too: never append a second,
    # chunkier copy to the legacy PvE projectile list.
    if event.get("kind") == "player_hp" and event.get("hit",True) and not any(s.get("action_id")==event.get("action_id") for s in view.shots):
        client.player_hit_at[event["player_id"]] = time.time()
    client._combat_active_until = time.time()+10


def advance_contacts(client):
    import kcs_siege_fx as fx
    for view in (getattr(client,"_pvp_view",None),getattr(client,"kcs_view",None)):
        if view is not None:fx.present_contacts(client,view,time.time())


def draw_projectiles(client, cam_x, cam_y, now, tile):
    view=getattr(client,"_pvp_view",None)
    if view is None:return
    import kcs_siege_fx as fx
    view.shots=[s for s in view.shots if s.get("until",0)>now]
    def project(x,y):
        rect=client.map_screen_rect(x,y,cam_x,cam_y)
        return rect.centerx,rect.bottom
    def position(pid):
        person=client.player if pid==(client.player or {}).get("id") else (client.players or {}).get(pid)
        return (person["x"],person["y"]) if person else None
    fx.draw_player_arrows(client.screen,view,now,project,position,max(.38,min(1.5,tile/40.)))


def draw_actor(client, person, cx, feet, tile, now, moving=False, facing=1):
    """Use the same weapon-specific full-set sheets in PvP as on the siege map."""
    view = getattr(client, "_pvp_view", None)
    if view is None:
        return False
    pid = person["id"]
    action = view.actor_actions.get(pid, {})
    until = max(action.get("start", 0)+action.get("duration", 0), view.actor_hits.get(pid, 0))
    active_facing = combat_facing(client, pid, person.get("combat_facing"))
    if (now > until+8 or until == 0) and not active_facing:
        return False
    import kcs_siege_players as actors
    eq = person.get("equipment") or {}
    tier = actors.full_tier(eq)
    weapon = actors.weapon_family(eq)
    hit_until = view.actor_hits.get(pid, 0)
    if hit_until-.36 <= now < hit_until:
        anim, start, duration = "hit", hit_until-.36, .36
    elif action.get("start", 0) <= now < action.get("start", 0)+action.get("duration", 0):
        anim, start, duration = ("ranged" if weapon == "bow" else "melee"), action["start"], action["duration"]
    else:
        anim, start, duration = ("walk" if moving else "idle"), 0, .8
    if anim in ("melee", "ranged"):
        dx, dy = action.get("tx", 0)-action.get("x", 0), action.get("ty", 0)-action.get("y", 0)
        facing = client.facing_for_view((1 if dx > 0 else -1) if abs(dx) > abs(dy) else ("front" if dy > 0 else "back"))
    if active_facing in ("n", "s", "e", "w"):
        facing = client.facing_for_view({"n":"back", "s":"front", "e":1, "w":-1}[active_facing])
    face = {1:"e", -1:"w", "right":"e", "left":"w", "front":"s", "back":"n", "e":"e", "w":"w", "s":"s", "n":"n"}.get(facing, "s")
    progress = (now-start)/duration
    progress = progress % 1 if anim in ("walk", "idle") else max(0, min(1, progress))
    view.actor_anims[pid] = (anim, start)
    root = siege.ensure_assets() if tier else None
    if tier is None or root is None:
        # No invented armour: partial sets/outfits use their existing weapon-
        # specific HD sheets, plus recoil when their look lacks a hit strip.
        import math, player_hd_client
        hit_t = now-start if anim == "hit" else -1.
        recoil = int(round(4*math.sin(hit_t/.36*math.pi))) if 0 <= hit_t < .36 else 0
        equipment = {**eq, "shield":None} if weapon == "bow" else eq
        return player_hd_client.draw_player(client.screen, person.get("gender", "male"), person.get("appearance"),
            cx+recoil, feet, tile, now, anim="idle" if anim == "hit" else anim,
            progress=progress, facing=face, hit_t=hit_t, equipment=equipment)
    actors.configure(root)
    return actors.actor_blit(client.screen, kind="female" if str(person.get("gender", "male")).startswith("f") else "male",
        tier=tier, weapon=weapon, shield=eq.get("shield"), facing=face, anim=anim,
        progress=progress, foot_screen=(cx, feet), scale=max(.38, min(1.5, tile/40.)))
