"""Compact siege-only chrome. Existing actions and server data, no game rules.

Four independent session-local folds; F10 hides/restores them without losing the
folds. Geometry is also rebuilt without painting after a toggle, so stale
invisible hit boxes cannot eat the next click in the same event batch.
"""
from __future__ import annotations
import time
import pygame

PANELS = ("menu", "status", "actions", "info")
FOLDABLE = PANELS + ("bag",)  # the siege bag only exists while deployed with economy
GOLD = (170, 137, 78)
TEXT = (239, 222, 188)
MUTED = (192, 180, 155)


def enabled(client, view=None):
    import kcs_client as k
    view = view or getattr(client, "kcs_view", None)
    dungeon = getattr(client, "dungeon", None) or {}
    return (getattr(client, "state", "") == "GAME" and
            dungeon.get("id") in (None, k.DUNGEON_ID) and
            bool(k.active(client) or view and (view.status or view.lobby)))


def _state(view):
    if not hasattr(view, "hud_collapsed"):
        view.hud_collapsed = set()
        view.hud_hidden = False
    return view.hud_collapsed


def toggle(client, view, action):
    _state(view)
    if action == "hud-all":
        view.hud_hidden = not view.hud_hidden
        if view.hud_hidden:
            view.guide_open = False
            view.guide_buttons = []
    elif action.startswith("hud-") and action[4:] in FOLDABLE:
        name = action[4:]
        if name in view.hud_collapsed:
            view.hud_collapsed.remove(name)
        else:
            view.hud_collapsed.add(name)
    else:
        return False
    draw(client, view, paint=False)
    return True


def blocks_world(client, pos):
    view = getattr(client, "kcs_view", None)
    return bool(view and enabled(client, view) and
                (view.guide_open or any(r.collidepoint(pos) for r in view.ui_regions)))


def on_wheel(client, pos, amount):
    view = getattr(client, "kcs_view", None)
    if not blocks_world(client, pos):
        return False
    box = getattr(view, "hud_rects", {}).get("info")
    if box and "info" not in _state(view) and box.collidepoint(pos) and view.details_open:
        view.hud_info_scroll = max(0, min(getattr(view, "hud_info_scroll_max", 0),
                                         getattr(view, "hud_info_scroll", 0) - int(amount)*32))
        draw(client, view, paint=False)
    return True


def _plate(screen, rect, alpha=174):
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (25, 20, 15, alpha), layer.get_rect(), border_radius=4)
    pygame.draw.rect(layer, (*GOLD, 215), layer.get_rect(), 1, border_radius=4)
    screen.blit(layer, rect)


def _fit(font, text, width):
    text = str(text)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."


def _text(screen, font, text, pos, width, color=TEXT):
    screen.blit(font.render(_fit(font, text, width), True, color), pos)


def _panel(screen, view, name, title, rect, font):
    # Only the little tab owns input when folded. The former body is world.
    if name in view.hud_collapsed:
        title = {"menu": "Siege", "status": "Status", "actions": "Actions", "info": "Info", "bag": "Siege bag  I"}[name]
        rect = pygame.Rect(rect.x, rect.y, font.size(title + " +")[0] + 16, 22)
        _plate(screen, rect)
        _text(screen, font, title + " +", (rect.x + 7, rect.y + 5), rect.w - 14)
        view.buttons.append((rect, "hud-" + name))
        view.ui_regions.append(rect)
        view.hud_rects[name] = rect
        return None
    _plate(screen, rect)
    view.ui_regions.append(rect)
    view.hud_rects[name] = rect
    _text(screen, font, title, (rect.x + 7, rect.y + 5), rect.w - 32, MUTED)
    fold = pygame.Rect(rect.right - 29, rect.y + 2, 25, 22)
    _plate(screen, fold, 220)
    pygame.draw.line(screen, (255,220,145), (fold.x+7,fold.centery), (fold.right-7,fold.centery), 3)
    view.buttons.append((fold, "hud-" + name))
    return rect


def _button(screen, view, rect, action, label, font, key="", selected=False, usable=True):
    _plate(screen, rect, 188 if selected else 92)
    if selected:
        pygame.draw.rect(screen, (236, 185, 81), rect, 1, border_radius=3)
    if key:
        _text(screen, font, key, (rect.x + 5, rect.y + 2), rect.w - 10, (219, 178, 103))
        text = font.render(_fit(font, label, rect.w - 8), True, TEXT)
        screen.blit(text, (rect.centerx - text.get_width() // 2, rect.y + 18))
    else:
        _text(screen, font, label, (rect.x + 7, rect.y + 5), rect.w - 14, TEXT if usable else (143,135,118))
    view.buttons.append((rect, action))


def _opening(view, oid):
    rows = list(view.openings) + list((view.status or {}).get("objectives") or [])
    return next((r for r in rows if (r.get("id") or r.get("opening_id")) == oid), {})


def _health(row):
    if row.get("state") in ("destroyed", "open", "breached"):
        return str(row["state"])
    hp = row.get("hp")
    if hp is None:
        return str(row.get("state") or "--")
    top = row.get("max_hp")
    if top is None:
        try:
            import kcs_balance
            oid = row.get("id") or row.get("opening_id")
            if oid:
                top = kcs_balance.opening_max_hp(oid)
        except Exception:
            top = None
    return f"{hp}/{top}" if top else f"{hp} HP"


def action_specs(client, view):
    import kcs_client as k
    if not k.active(client):
        return []
    if (view.status or {}).get("status") in ("resolved", "resolving"):
        return []
    if k.quarters_on(view):
        view_specs = [("view-left", "Rotate left", "Q", 88),
                      ("view-right", "Rotate right", "]" if (view.status or {}).get("economy") else "E", 92)]
    else:
        view_specs = [("view", "Fixed camera", "F9", 90)]
    if (client.dungeon or {}).get("mode") == "spectator":
        return view_specs
    order = k.DEFENDER_ORDER if view.your_side == "defend" else k.ENGINE_ORDER
    specs = [("type-" + kind, k.ENGINE_SHORT[kind], str(n), 76 if kind == "trebuchet" else 64)
             for n, kind in enumerate(order, 1)]
    specs += [("build", "Build", "F6", 64), ("turn", "Turn", "F7", 64),
              *view_specs, ("face", "Face wall", "", 72),
              ("fire", "Fire", "", 60), ("pack", "Pack", "", 60)]
    if view.your_side == "defend" or (view.status or {}).get("economy"):
        specs.append(("repair", "Repair", "", 64))
    specs += [("strike", "Strike", "Space", 66)]
    if view.your_side == "attack":
        specs.append(("claim", "Claim throne", "", 84))
    return specs


def _owned(client, view):
    me=(getattr(client,'player',None) or {}).get('id')
    return [r for r in view.engines if (r.get('player_id')==me or r.get('owner_id')==me) and r.get('engine_type')==view.engine_type]


def action_state(client, view, action):
    """Presentation guard from known state only. The server still authorises all actions."""
    import kcs_client as k
    if action.startswith('hud-') or action in ('guide','details','view','view-left','view-right','prep') or action.startswith('side-'):
        return True,''
    battle=k.active(client);st=view.status or {};phase=st.get('status')
    if action.startswith('enlist-') or action=='begin':
        return (not battle and phase=='registration','Enlist and Begin are available in registration.')
    if action in ('deploy','watch'):
        mode=(getattr(client,'dungeon',None) or {}).get('mode')
        available=phase=='active' and (not battle or action=='watch' and mode!='spectator')
        return available,('Already deployed.' if battle and action=='deploy' else 'Begin the siege before deploying or watching.')
    if action=='leave':
        if not battle:return False,'You are not deployed in the siege.'
        locked=getattr(client,'combat_flee_locked',None)
        return not(callable(locked) and locked()),'Finish the five combat rounds before leaving.'
    if not battle or phase not in ('active',None):return False,'No active battle.'
    if view.stale or not getattr(getattr(client,'net',None),'connected',True):return False,'Waiting for the siege connection.'
    if (client.dungeon or {}).get('mode')=='spectator':return False,'Spectators cannot use combat tools.'
    if (getattr(client,'player',None) or {}).get('hp',1)<=0:return False,'You are out of this battle.'
    eco=st.get('economy') or {}
    if eco and (action.startswith('type-') or action in ('build','turn','face')):
        if not st.get('preparing'):return False,'Preparation is over: no new engines can be built.'
        if not eco.get('clan_id'):return False,'Join a clan and deposit real materials before building.'
        kind=action[5:] if action.startswith('type-') else view.engine_type
        cost=(eco.get('costs') or {}).get(kind,{})
        if eco.get('engineering_level',1)<cost.get('level',1):return False,f'Engineering level {cost["level"]} required.'
        materials=eco.get('materials') or {}
        for key,item in [('wood',eco.get('wood_type','logs')),('iron',eco.get('metal_type','iron_bar'))]:
            if materials.get(item,0)<cost.get(key,0):return False,f'Clan needs {cost[key]} {item.replace("_"," ")}.'
        if eco.get('gold',0)<cost.get('gold',0):return False,f'Clan needs {cost["gold"]} gold.'
    if eco and st.get('preparing') and action in ('strike','fire','claim'):
        return False,'Preparation: no fighting or firing until the countdown ends.'
    if action.startswith('type-') or action in ('build','turn','face'):
        return True,''
    if action=='strike':
        from content import is_bow, bow_attack_range
        import kcs_balance as balance
        px,py=k._player_tile(client)
        weapon=((getattr(client,'player',None) or {}).get('equipment') or {}).get('weapon')
        reach=bow_attack_range(weapon) if is_bow(weapon) else balance.player_range()
        import player_interactions
        for row in (getattr(client,'players',{}) or {}).values():
            allowed=not player_interactions.attack_reason(client,row)
            if allowed and max(abs(px-row.get('x',px+999)),abs(py-row.get('y',py+999)))<=reach:return True,''
        if eco and view.your_side=='attack':
            if any(row.get('hp',0)>0 and any(max(abs(px-x),abs(py-y))<=reach for x,y in row.get('tiles',[])) for row in view.openings):return True,''
        for row in view.engines:
            if row.get('side') not in ('attack','defend') or row.get('side')==view.your_side or row.get('hp',1)<=0:continue
            if any(max(abs(px-x),abs(py-y))<=reach for x,y in row.get('tiles',[])):return True,''
        return False,'No enemy player or engine in strike range.'
    if action=='claim':
        if view.your_side!='attack':return False,'Only attackers claim the throne.'
        if not _breached(_opening(view,'keep_doors')):return False,'Break the keep doors first.'
        if (client.dungeon or {}).get('plane')!='kings_castle_siege.throne_room':return False,'Enter the throne room first.'
        try:
            from kings_castle_siege_map.layout import build_throne_room
            dais=build_throne_room().spawn['dais'];px,py=k._player_tile(client)
            if max(abs(px-dais[0]),abs(py-dais[1]))>8:return False,'Move onto the royal dais.'
        except (ImportError,KeyError):pass
        return True,''
    if action=='repair':
        if eco:
            px,py=k._player_tile(client);materials=eco.get('materials') or {}
            if materials.get(eco.get('wood_type','logs'),0)<2 or materials.get(eco.get('metal_type','iron_bar'),0)<1:return False,'Repair costs 2 chosen logs + 1 chosen bar.'
            for row in view.engines:
                if row.get('side')==view.your_side and 0<row.get('hp',0)<row.get('max_hp',0) and any(max(abs(px-x),abs(py-y))<=2 for x,y in row.get('tiles',[])):
                    need=(eco.get('costs',{}).get(row.get('engine_type'),{}) or {}).get('level',99)
                    if eco.get('engineering_level',1)>=need:return True,'4 HP / 5 seconds; 2 logs + 1 bar.'
            if view.your_side=='defend' and eco.get('engineering_level',1)>=10:
                for row in view.openings:
                    if row.get('hp',999)<row.get('max_hp',0) and any(max(abs(px-x),abs(py-y))<=2 for x,y in row.get('tiles',[])):return True,'4 HP / 5 seconds; 2 logs + 1 bar.'
            return False,'Stand within 2 tiles of a damaged friendly engine or opening; engineering level required.'
        if view.your_side!='defend':return False,'Only defenders repair castle openings.'
        px,py=k._player_tile(client)
        for row in view.openings:
            if (row.get('id') or row.get('opening_id'))=='throne_doors':continue
            hp,maximum=row.get('hp'),row.get('max_hp')
            damaged=(hp is not None and maximum is not None and hp<maximum) or row.get('state') in ('damaged','destroyed','breached')
            if damaged and any(max(abs(px-x),abs(py-y))<=8 for x,y in row.get('tiles',[])):return True,''
        return False,'No damaged gate or wall within repair range.'
    if action in ('fire','pack'):
        owned=_owned(client,view)
        if eco and action=='fire':
            px,py=k._player_tile(client)
            owned=[r for r in view.engines if r.get('side')==view.your_side and any(max(abs(px-x),abs(py-y))<=2 for x,y in r.get('tiles',[]))]
            if not owned:return False,'Stand within 2 tiles of a friendly engine.'
            costs=eco.get('costs') or {}
            needed=min(costs.get(r.get('engine_type'),{}).get('level',99) for r in owned)
            owned=[r for r in owned if eco.get('engineering_level',1)>=costs.get(r.get('engine_type'),{}).get('level',99)]
            if not owned:return False,f'Engineering level {needed} required to fire a nearby engine.'
        if not owned:return False,'Build your selected engine first.'
        import kcs_balance as balance
        if view.your_side=='defend' and not (eco and action=='fire'):
            px,py=k._player_tile(client)
            owned=[r for r in owned if balance.beside(px,py,r.get('tiles') or [(r['x'],r['y'])])]
            if not owned:return False,'Stand beside your selected engine.'
        if action=='pack':return (any(r.get('hp',1)>0 for r in owned),'Wrecked engines cannot be packed or refunded.')
        ready=[r for r in owned if r.get('hp',1)>0 and (r.get('cooldown_until') or 0)<=time.time()]
        if not ready:return False,'Your engine is reloading or wrecked.'
        if view.your_side=='attack':
            cells={(r.get('id') or r.get('opening_id')):r['tiles'] for r in view.openings if r.get('tiles') and not _breached(r) and str(r.get('plane','battlefield')).endswith('battlefield')}
            if cells and not any(balance.shot_target(r.get('tiles') or [(r['x'],r['y'])],r.get('rotation',0),r.get('engine_type',view.engine_type),cells) for r in ready):
                return False,'No intact opening in front of this engine.'
        else:
            targets=[(r.get('engine_id'),r.get('tiles') or [(r['x'],r['y'])]) for r in view.engines if r.get('side')=='attack' and r.get('hp',1)>0]
            targets += [(r.get('id'),[(r['x'],r['y'])]) for r in (getattr(client,'players',{}) or {}).values() if r.get('kcs_side')=='attack' and r.get('hp',1)>0]
            cells=[p for r in view.openings for p in r.get('tiles',[])]
            in_range=False
            for engine in ready:
                kind=engine.get('engine_type',view.engine_type);tiles=engine.get('tiles') or [(engine['x'],engine['y'])]
                if kind=='cauldron':
                    in_range|=any(tuple(p) in balance.cauldron_zone(tiles,cells,balance.engine_spec(kind)['range']) for _,cells2 in targets for p in cells2)
                else:in_range|=bool(balance.aimed_target(tiles,engine.get('rotation',0),kind,targets))
            if not in_range:return False,'No enemy in front of this engine.'
        return True,''
    return True,''


def _breached(row):
    return bool(row) and (row.get('state') in ('destroyed','breached','open') or row.get('hp')==0)


def objective_rows(view):
    """(label, state) where state is done, active, failed or unknown. No invented progress."""
    st=view.status or {};result=st.get('result') or {};winner=result.get('winner') or st.get('winner')
    finished=st.get('status') in ('resolved','resolving')
    gate,keep=_opening(view,'main_gate'),_opening(view,'keep_doors')
    if view.your_side=='defend':
        def held(row):
            if not row:return 'unknown'
            if _breached(row):return 'failed'
            return 'done' if finished and winner=='defend' else 'active'
        return [('Hold the gate',held(gate)),('Hold the keep',held(keep)),
                ('Until time runs out','done' if finished and winner=='defend' and result.get('reason')=='timeout' else 'unknown' if finished and winner=='defend' else 'failed' if finished else 'active')]
    def breach_state(row):return 'done' if _breached(row) else 'active' if row else 'unknown'
    return [('Breach the main gate',breach_state(gate)),('Break the keep doors',breach_state(keep)),
            ('Claim the throne','done' if finished and winner=='attack' and result.get('reason')=='claim' else 'failed' if finished else 'active'),
            ('Before the timer ends','done' if finished and winner=='attack' else 'failed' if finished else 'active')]


def _draw_progress(screen, point, state):
    x,y=point
    color={'done':(133,203,113),'active':(225,186,101),'failed':(174,108,94),'unknown':(155,146,128)}[state]
    pygame.draw.circle(screen,color,(x,y),6,1)
    if state=='done':pygame.draw.lines(screen,color,False,[(x-3,y),(x-1,y+2),(x+4,y-3)],2)
    elif state=='active':pygame.draw.circle(screen,color,(x,y),2)
    elif state=='failed':
        pygame.draw.line(screen,color,(x-2,y-2),(x+2,y+2),1);pygame.draw.line(screen,color,(x+2,y-2),(x-2,y+2),1)
    else:pygame.draw.line(screen,color,(x-2,y),(x+2,y),1)


def _draw_status(screen,client,view,box,font,small,battle):
    import kcs_client as k
    import kcs_hud_icons as icons
    st=view.status or {};me=getattr(client,'player',None) or {}
    remaining=st.get('remaining')
    if isinstance(remaining,int) and st.get('status')=='active' and hasattr(view,'status_received_at'):
        remaining=max(0,remaining-int(max(0,time.monotonic()-view.status_received_at)))
    timer=k._clock(remaining) or ('Not begun' if st.get('status')=='registration' else '--:--')
    cx=box.centerx;cy=box.y+29
    # The timer is the visual centre, bracketed by red attackers / blue defenders.
    plate=pygame.Rect(cx-72,box.y+3,144,49)
    shape=[(plate.x+10,plate.y),(plate.right-10,plate.y),(plate.right,plate.y+10),(plate.right-4,plate.bottom),(plate.x+4,plate.bottom),(plate.x,plate.y+10)]
    layer=pygame.Surface(plate.size,pygame.SRCALPHA)
    local=[(x-plate.x,y-plate.y) for x,y in shape];pygame.draw.polygon(layer,(38,27,15,200),local);pygame.draw.polygon(layer,(*GOLD,255),local,2);screen.blit(layer,plate)
    clock,_=icons.icon('clock',(19,19));screen.blit(clock,(cx-58,box.y+20))
    title=small.render('PREPARATION' if st.get('preparing') else 'SIEGE TIMER',True,MUTED);screen.blit(title,(cx-title.get_width()//2,box.y+7))
    big=pygame.font.Font(None,29 if len(timer)<=5 else 22)
    label=big.render(timer,True,(255,219,143));screen.blit(label,(cx+7-label.get_width()//2,box.y+22))
    for side,name,color,x in [('attack','ATTACKERS',(163,66,56),cx-225),('defend','DEFENDERS',(63,113,166),cx+88)]:
        pts=[(x,box.y+10),(x+23,box.y+10),(x+23,box.y+34),(x+11,box.y+43),(x,box.y+34)]
        pygame.draw.polygon(screen,color,pts);pygame.draw.polygon(screen,(211,174,103),pts,1)
        pygame.draw.line(screen,(240,213,158),(x+11,box.y+15),(x+11,box.y+32),2)
        pygame.draw.line(screen,(240,213,158),(x+5,box.y+23),(x+17,box.y+23),2)
        count=st.get(side+'_on_map',st.get(side+'_deployed',0)) if battle else st.get(side+'_enlisted',0)
        _text(screen,small,name,(x+31,box.y+10),105)
        number=pygame.font.Font(None,26).render(str(count),True,TEXT);screen.blit(number,(x+32,box.y+26))
    # Compact health line remains part of the same minimisable/translucent panel.
    hp,maximum=me.get('hp','--'),me.get('max_hp','--')
    fields=[f'HP {hp}/{maximum}','Gate '+_health(_opening(view,'main_gate')),'Keep '+_health(_opening(view,'keep_doors'))]
    start=box.x+28;cell=(box.w-56)//3
    for n,text in enumerate(fields):_text(screen,small,text,(start+n*cell,box.y+57),cell-8)


def _action_button(screen,client,view,rect,action,label,key,font):
    import kcs_hud_icons as icons
    import kcs_client as k
    usable,reason=action_state(client,view,action)
    if not usable:view.hud_disabled[action]=reason
    selected=view.build and action in ('build','type-'+view.engine_type)
    _plate(screen,rect,202 if selected else 115 if usable else 80)
    pygame.draw.rect(screen,(235,188,92) if selected else GOLD if usable else (99,91,75),rect,2 if selected else 1,border_radius=4)
    feedback=k.fire_feedback(client,view) if action=='fire' else None
    countdown=None
    if feedback:
        remaining,progress=k.engine_reload(feedback)
        if remaining>0:
            countdown=f'{remaining:.1f}s'
            fill=pygame.Surface((rect.w-4,rect.h-4),pygame.SRCALPHA)
            hh=round(fill.get_height()*progress)
            pygame.draw.rect(fill,(205,156,67,78),(0,fill.get_height()-hh,fill.get_width(),hh))
            screen.blit(fill,(rect.x+2,rect.y+2))
        elif getattr(view,'engine_ready_flash',{}).get(feedback.get('engine_id'),0)>time.monotonic():
            pygame.draw.rect(screen,(255,230,147),rect,2,border_radius=4)
    image,source=icons.icon(action,(40,31),not usable);screen.blit(image,(rect.centerx-20,rect.y+4));view.hud_icon_sources[action]=source
    color=TEXT if usable else (151,142,125)
    text=font.render(_fit(font,label,rect.w-6),True,color);screen.blit(text,(rect.centerx-text.get_width()//2,rect.y+36))
    hint=pygame.font.Font(None,15).render(countdown or key or 'Click',True,(223,180,100) if usable else (134,126,109));screen.blit(hint,(rect.centerx-hint.get_width()//2,rect.y+50))
    view.buttons.append((rect,action))
    mouse=pygame.mouse.get_pos() if pygame.display.get_init() else (-1,-1)
    if rect.collidepoint(mouse):
        tip=reason if not usable else label+(' / '+key if key else ' / click')
        eco=(view.status or {}).get('economy') or {}
        if eco and (action.startswith('type-') or action=='build'):
            kind=action[5:] if action.startswith('type-') else view.engine_type
            cost=(eco.get('costs') or {}).get(kind,{})
            tip+=' | '+str(cost.get('wood','?'))+' '+eco.get('wood_type','logs').replace('_',' ')+' + '+str(cost.get('iron','?'))+' '+eco.get('metal_type','iron_bar').replace('_',' ')+' + '+str(cost.get('gold','?'))+' gold; Eng '+str(cost.get('level','?'))
        view.hud_tip=(tip,rect)


def _draw_tip(screen,view,font):
    if not view.hud_tip:return
    text,anchor=view.hud_tip
    import kcs_client as k
    width=min(360,max(120,font.size(text)[0]+18))
    lines=k._wrap(font,text,width-16);height=12+16*len(lines)
    box=pygame.Rect(min(screen.get_width()-width-8,max(8,anchor.centerx-width//2)),max(4,anchor.y-height-3),width,height)
    _plate(screen,box,235)
    for n,line in enumerate(lines):_text(screen,font,line,(box.x+8,box.y+6+16*n),box.w-16)
    view.ui_regions.append(box)

BAG_CELL = 34
BAG_COLS = 5          # 5 wide so the worn row below gets one full 34 px cell per slot (t642u)
WORN_SLOTS = ("helmet", "body", "weapon", "shield", "ammo")
WORN_LABELS = {"helmet": "Helm", "body": "Body", "weapon": "Wep", "shield": "Shield", "ammo": "Ammo"}


def bag_rows(client):
    """The siege-issued/gathered/made items actually carried (server inventory)."""
    inv = (getattr(client, "player", None) or {}).get("inventory") or {}
    rows = []
    for slot, entry in inv.items():
        if entry and entry.get("item_id"):
            rows.append((int(slot), entry))
    return sorted(rows, key=lambda r: r[0])


def _item(item_id):
    try:
        from content import ITEMS
        return ITEMS.get(item_id) or {}
    except Exception:
        return {}


def _draw_bag(screen, client, view, font, small, actions):
    """Small, minimisable siege inventory: ore from the rocks, bars from the
    furnace, armour from the anvil (click armour to wear it). Reuses the real
    server inventory and EQUIP; nothing here survives the siege (escrow)."""
    import kcs_client as k
    view.bag_rects = []
    if not k.active(client) or not (view.status or {}).get("economy"):
        return
    if (client.dungeon or {}).get("mode") == "spectator":
        return
    rows = bag_rows(client)
    now = time.monotonic()
    seen = getattr(view, "bag_seen", None)
    counts = {}
    for _, entry in rows:
        counts[entry["item_id"]] = counts.get(entry["item_id"], 0) + int(entry.get("qty", 1) or 1)
    flash = getattr(view, "bag_flash", {})
    if seen is not None:
        for item_id, qty in counts.items():
            if qty > seen.get(item_id, 0):
                flash[item_id] = now + 1.4
    view.bag_seen, view.bag_flash = counts, {i: t for i, t in flash.items() if t > now}
    menu = view.hud_rects.get("menu")
    top = (menu.bottom if menu else 90) + 8
    width = BAG_CELL * BAG_COLS + 10
    eq = (getattr(client, "player", None) or {}).get("equipment") or {}
    worn_h = 58          # own row under the bag: label line + full-width cells (David t642u: was cramped)
    room = max(1, (actions.y - 8 - top - 34 - worn_h) // (BAG_CELL + 2))
    need = max(1, -(-len(rows) // BAG_COLS))
    shown_rows = min(room, need)
    height = 32 + shown_rows * (BAG_CELL + 2) + worn_h + 4
    box = _panel(screen, view, "bag", "Siege bag  I", pygame.Rect(8, top, width, height), font)
    if not box:
        return
    capacity = shown_rows * BAG_COLS
    visible = rows if len(rows) <= capacity else rows[:capacity - 1]
    mouse = pygame.mouse.get_pos() if pygame.display.get_init() else (-1, -1)
    try:
        import procedural_sprites_finished as sprites
        from content import ITEMS
    except Exception:
        sprites = None
        ITEMS = {}
    for n, (slot, entry) in enumerate(visible):
        cell = pygame.Rect(box.x + 5 + (n % BAG_COLS) * (BAG_CELL + 1), box.y + 28 + (n // BAG_COLS) * (BAG_CELL + 2), BAG_CELL, BAG_CELL)
        item_id = entry["item_id"]
        info = ITEMS.get(item_id) or {}
        _plate(screen, cell, 120)
        if sprites is not None:
            try:
                sprites.draw_item_icon(screen, cell.inflate(-6, -6), item_id, ITEMS)
            except Exception:
                _text(screen, small, (info.get("name") or item_id)[:4], (cell.x + 3, cell.y + 11), cell.w - 4)
        qty = int(entry.get("qty", 1) or 1)
        if qty > 1:
            label = small.render(str(qty), True, (255, 231, 160))
            screen.blit(label, (cell.right - label.get_width() - 2, cell.bottom - label.get_height()))
        if info.get("equip_slot"):
            pygame.draw.polygon(screen, (236, 185, 81), [(cell.x + 1, cell.y + 1), (cell.x + 8, cell.y + 1), (cell.x + 1, cell.y + 8)])
        if view.bag_flash.get(item_id):
            pygame.draw.rect(screen, (255, 226, 140), cell, 2, border_radius=3)
        view.buttons.append((cell, "bag-" + str(slot)))
        view.bag_rects.append((cell, slot, item_id))
        if cell.collidepoint(mouse):
            name = info.get("name") or item_id.replace("_", " ").title()
            tip = name + (f" x{qty}" if qty > 1 else "")
            if info.get("equip_slot"):
                tip += " / click to wear"
            view.hud_tip = (tip, cell)
    hidden = len(rows) - len(visible)
    if hidden > 0:
        n = len(visible)
        cell = pygame.Rect(box.x + 5 + (n % BAG_COLS) * (BAG_CELL + 1), box.y + 28 + (n // BAG_COLS) * (BAG_CELL + 2), BAG_CELL, BAG_CELL)
        _text(screen, small, f"+{hidden}", (cell.x + 7, cell.y + 11), cell.w - 6, MUTED)
    if not rows:
        _text(screen, small, "Click ore to mine", (box.x + 7, box.y + 36), box.w - 14, MUTED)
    y = box.y + 30 + shown_rows * (BAG_CELL + 2)
    pygame.draw.line(screen, (92, 80, 60), (box.x + 6, y + 1), (box.right - 6, y + 1))
    _text(screen, small, "Worn", (box.x + 6, y + 4), 60, MUTED)
    y += 18
    cell_w = max(24, (box.w - 10) // len(WORN_SLOTS))
    for i, slot in enumerate(WORN_SLOTS):
        cell = pygame.Rect(box.x + 5 + i * cell_w, y, cell_w - 3, 36)
        _plate(screen, cell, 110)
        item_id = eq.get(slot)
        info = _item(item_id) if item_id else {}
        if item_id and sprites is not None:
            try:
                sprites.draw_item_icon(screen, cell.inflate(-6, -6), item_id, ITEMS)
            except Exception:
                _text(screen, small, (info.get("name") or item_id)[:3], (cell.x + 1, cell.y + 10), cell.w - 2)
        elif not item_id:
            _text(screen, small, WORN_LABELS[slot], (cell.x + 3, cell.y + 12), cell.w - 4, MUTED)
        if item_id and cell.collidepoint(mouse):
            view.hud_tip = ((info.get("name") or item_id.replace("_", " ").title()), cell)


def bag_click(client, view, action):
    """Wear a clicked weapon/armour piece with the real EQUIP message."""
    if not action.startswith("bag-"):
        return False
    import kcs_client as k
    slot = int(action[4:])
    entry = ((getattr(client, "player", None) or {}).get("inventory") or {})
    entry = entry.get(slot) or entry.get(str(slot)) or {}
    info = _item(entry.get("item_id"))
    if info.get("equip_slot") == "legs":
        k.note(client, "Bodies now cover the legs; there is no separate leg armour.", error=True)
        return True
    if info.get("equip_slot"):
        worn = (getattr(client, "player", None) or {}).get("equipment") or {}
        bow = info.get("equip_slot") == "weapon" and (info.get("two_handed") or str(entry.get("item_id", "")).endswith("bow"))
        if bow and worn.get("shield"):
            # Existing rule: a bow needs both hands. Take the shield off first.
            client.net.send("UNEQUIP", equip_slot="shield")
        client.net.send("EQUIP", slot_index=slot)
        k.note(client, "Wearing " + (info.get("name") or entry.get("item_id", "item")) + ".")
    elif entry:
        k.note(client, (info.get("name") or entry.get("item_id")) + ": smelt ore at a furnace, smith bars at an anvil.")
    return True


ARROW_IDS = ("bronze_arrow", "iron_arrow", "steel_arrow", "mithril_arrow", "adamant_arrow", "rune_arrow")
FLETCH_DRAW = 50


def store_arrows(view):
    mats = ((view.status or {}).get("economy") or {}).get("materials") or {}
    return [(a, int(mats.get(a, 0))) for a in ARROW_IDS if int(mats.get(a, 0) or 0) > 0]


def _draw_fletch(screen, client, view, font, small, actions):
    """Fletching bench: bows from clan-store logs (bowstring supplied) and
    arrows drawn from the clan store. Server checks level, stock and range."""
    import kcs_client as k
    view.fletch_rects = []
    if not getattr(view, "fletch_open", None) or not k.active(client):
        return
    eco = (view.status or {}).get("economy") or {}
    mats = eco.get("materials") or {}
    try:
        import kcs_workshop
        from content import ITEMS
    except Exception:
        return
    bows = []
    for bow in kcs_workshop.BOWS:
        spec = kcs_workshop.bow_recipe(bow)
        if spec and int(mats.get(spec["wood"], 0) or 0) >= spec["logs"]:
            bows.append((bow, spec))
    arrows = store_arrows(view)
    rows = len(bows) + len(arrows) + 2
    width = 260
    height = min(actions.y - 98, 34 + 24 * rows + 10)
    menu = view.hud_rects.get("menu")
    box = pygame.Rect((menu.right if menu else 160) + 12, 90, width, height)
    _plate(screen, box, 228)
    view.ui_regions.append(box)
    _text(screen, font, "Fletching bench", (box.x + 8, box.y + 6), box.w - 40, (249, 210, 131))
    close = pygame.Rect(box.right - 26, box.y + 3, 22, 20)
    _plate(screen, close, 200); _text(screen, font, "x", (close.x + 7, close.y + 3), 12)
    view.buttons.append((close, "fletch-close"))
    y = box.y + 30
    _text(screen, small, "Bows from clan logs (string supplied):", (box.x + 8, y), box.w - 16, MUTED); y += 18
    if not bows:
        _text(screen, small, "No logs in the clan store.", (box.x + 12, y), box.w - 20, MUTED); y += 20
    for bow, spec in bows:
        if y + 22 > box.bottom - 4:
            break
        rect = pygame.Rect(box.x + 6, y, box.w - 12, 21)
        label = f"{ITEMS[bow]['name']}  ({spec['logs']} {spec['wood'].replace('_', ' ')}, Flet {spec['level']})"
        _button(screen, view, rect, "fletch-" + bow, label, small)
        view.fletch_rects.append((rect, bow)); y += 23
    _text(screen, small, "Arrows from the clan store:", (box.x + 8, y + 2), box.w - 16, MUTED); y += 20
    if not arrows:
        _text(screen, small, "No arrows in the clan store.", (box.x + 12, y), box.w - 20, MUTED)
    for item, qty in arrows:
        if y + 22 > box.bottom - 4:
            break
        rect = pygame.Rect(box.x + 6, y, box.w - 12, 21)
        n = min(FLETCH_DRAW, qty)
        _button(screen, view, rect, f"arrows-{item}-{n}", f"Draw {n} {ITEMS[item]['name']}s  (store {qty})", small)
        view.fletch_rects.append((rect, item)); y += 23


def fletch_click(client, view, action):
    import kcs_client as k
    if action == "fletch-close":
        view.fletch_open = None; return True
    if action.startswith("fletch-"):
        client.net.send("KCS_FLETCH", bow=action[7:])
    elif action.startswith("arrows-"):
        item, n = action[7:].rsplit("-", 1)
        client.net.send("KCS_ARROWS", item_id=item, quantity=int(n))
    else:
        return False
    client.net.send("KCS_LOBBY")  # refresh the clan-store numbers
    return True


def _info_lines(client, view, width, font):
    import kcs_client as k
    st = view.status or {}
    lines = []
    if st.get('preparing'):
        lines+=k._wrap(font,'Prep: Mine ore, smelt at furnaces, smith at anvils.',width)
    eco=st.get('economy') or {}
    if eco:
        mats=eco.get('materials') or {}
        names={'logs':'Logs','oak_logs':'Oak','willow_logs':'Willow','maple_logs':'Maple','yew_logs':'Yew','magic_logs':'Enchanted'}
        stock=' / '.join(f'{label} {mats.get(item,0)}' for item,label in names.items() if mats.get(item,0)) or 'Logs: none'
        lines+=k._wrap(font,stock,width)
        lines+=k._wrap(font,f'Iron {mats.get("iron_bar",0)} / Steel {mats.get("steel_bar",0)} / Gold {eco.get("gold",0)}',width)
        arrows=store_arrows(view)
        lines+=k._wrap(font,'Arrows: '+(' / '.join(f'{a.split("_")[0].title()} {q}' for a,q in arrows) or 'none in store'),width)
        chosen_wood=names.get(eco.get('wood_type'),'Logs')
        chosen_metal='Steel' if eco.get('metal_type')=='steel_bar' else 'Iron'
        cost=(eco.get('costs') or {}).get(view.engine_type,{})
        lines+=k._wrap(font,f'Build: {cost.get("wood","?")} {chosen_wood} + {cost.get("iron","?")} {chosen_metal} + {cost.get("gold","?")}g / Eng {cost.get("level","?")}',width)
    if k.active(client):
        rows = view.openings if view.details_open else [] # Gate/keep HP already lives in the top bar.
        for row in rows:
            label = str(row.get("id") or row.get("opening_id") or "Opening").replace("_", " ").capitalize()
            lines.append(label + ": " + _health(row))
        others = [r for r in view.openings if r not in rows and (r.get("id") or r.get("opening_id")) not in ("main_gate","keep_doors")]
        if others:
            breached = sum(r.get("state") in ("destroyed", "open", "breached") for r in others)
            lines.append(f"Other openings: {breached}/{len(others)} breached")
        if not view.openings:
            lines.extend(str(r.get("label") or r.get("id")) + ": " + _health(r)
                         for r in st.get("objectives") or [])
        me = getattr(client, "player", None) or {}
        mine = next((r for r in view.engines if (r.get("player_id") == me.get("id") or r.get("owner_id") == me.get("id")) and r.get("engine_type") == view.engine_type), None)
        engine = k.ENGINE_SHORT.get(view.engine_type, view.engine_type)
        owner_label='Your'
        if eco:
            px,py=k._player_tile(client)
            nearby=[r for r in view.engines if r.get('side')==view.your_side and r.get('engine_type')==view.engine_type and any(max(abs(px-x),abs(py-y))<=2 for x,y in r.get('tiles',[]))]
            if nearby:
                nearby.sort(key=lambda r:(r.get('hp',1)<=0,(r.get('cooldown_until') or 0)>time.time(),min(max(abs(px-x),abs(py-y)) for x,y in r.get('tiles',[]))))
                mine=nearby[0];owner_label='Nearby'
        if mine:
            wait = max(0, int((mine.get("cooldown_until") or 0) - time.time()))
            lines.append(f"{owner_label} {engine}: {mine.get('hp', '?')} HP")
            lines.append("Wrecked" if mine.get("hp",1)<=0 else "Prep: firing locked" if eco and eco.get("preparing") else f"Reload {wait}s" if wait else "Ready to fire")
        else:
            lines.append(f"Your {engine}: not placed")
        if view.build:
            lines.append("BUILD / nose " + k._face_name(view.rotation))
    else:
        lines.append("King's Castle / " + str(st.get("phase") or st.get("status") or "Lobby"))
        if st.get("status") in ("resolved", "resolving"):
            result = st.get("result") or {}
            winner = result.get("winner") or st.get("winner")
            if winner and view.your_side:
                lines.append("Victory" if winner == view.your_side else "Defeat")
            for text in (result.get("text"), result.get("ownership_note")):
                if text:
                    lines += k._wrap(font, str(text), width)
        elif st.get("status") == "active":
            lines.append("Deploy F8 or Watch the battle.")
        else:
            lines += ["Enlist, Begin, then Deploy F8.", "Clock starts at Begin."]
    if view.details_open:
        lines += [wrapped for line in k._status_lines(st) for wrapped in k._wrap(font, str(line), width)]
        if k.active(client):
            lines += ["Nose " + k._face_name(view.rotation), "Camera: fixed castle view"]
    k.refresh_engine_inspect(view)
    if view.inspect:
        lines += [view.inspect.get("title") or "Selected"] + list(view.inspect.get("lines") or [])
    notice = view.error or (view.preview if view.build and view.preview else view.notice)
    if notice:
        lines += k._wrap(font, k._placement_hint(notice), width)
    return lines


def draw(client, view, paint=True):
    import kcs_client as k
    _state(view)
    view.buttons = []
    view.ui_regions = []
    view.hud_rects = {}
    view.hud_disabled = {}
    view.hud_icon_sources = {}
    view.hud_tip = None
    if not enabled(client, view):
        return
    battle = k.active(client)
    game = k._game(client)
    width, height = client.screen.get_size() if battle else (game.MAP_W, game.MAP_H)
    screen = client.screen if paint else pygame.Surface(client.screen.get_size(), pygame.SRCALPHA)
    font = pygame.font.Font(None, 17)
    small = pygame.font.Font(None, 16)
    if view.hud_hidden:
        tab = pygame.Rect(8 if battle else 148, 8, 105, 22)
        _plate(screen, tab)
        _text(screen, font, "Siege / F10 +", (tab.x + 7, tab.y + 5), 91)
        view.buttons.append((tab, "hud-all")); view.ui_regions.append(tab)
        return

    # Prominent central clock plate, flanked by existing team counts.
    sw = min(570, width - 16)
    status = pygame.Rect((width - sw)//2, 6, sw, 70)
    box = _panel(screen, view, "status", "", status, font)
    if box:
        _draw_status(screen,client,view,box,font,small,battle)

    # Existing navigation only. Begin is a lobby action, never a battle tool.
    menu = [("guide", "Guide"), ("enlist-attack", "Enlist attack"), ("enlist-defend", "Enlist defend")]
    if not battle:
        menu.append(("begin", "Begin"))
    menu += [("deploy", "Deploy  F8"), ("watch", "Watch"),
             ("details", "Less  Tab" if view.details_open else "Details  Tab"), ("leave", "Leave siege")]
    left = pygame.Rect(8 if battle else 148, 90, 144, 32 + 26*len(menu))
    box = _panel(screen, view, "menu", "Siege / F10 hide", left, font)
    if box:
        for n, (action, label) in enumerate(menu):
            usable,reason=action_state(client,view,action)
            if not usable:view.hud_disabled[action]=reason
            _button(screen, view, pygame.Rect(box.x + 5, box.y + 28 + n*26, box.w - 10, 24), action, label, font, usable=usable)

    # Actual engine thumbnails and compact illustrated existing tools.
    specs = action_specs(client, view)
    max_width = width - (156 if not battle else 16)
    rows = [[]]; used = 0
    for spec in specs:
        if used and used + spec[3] + 3 > max_width - 12:
            rows.append([]); used = 0
        rows[-1].append(spec); used += spec[3] + 3
    aw = min(max_width, max((sum(s[3]+3 for s in row) + 9 for row in rows), default=0)) if specs else min(max_width, 276)
    ah = 32 + 68*len(rows) if specs else 52
    actions = pygame.Rect((width - aw)//2 if battle else max(148, (width-aw)//2), height - ah - 8, aw, ah)
    box = _panel(screen, view, "actions", "Actions", actions, font)
    if box:
        if not specs:
            _text(screen, small, "Deploy F8 to use siege actions" if not battle else "No battle actions available", (box.x+7, box.y+26), box.w-14, MUTED)
        for row_n, row in enumerate(rows):
            x = box.x + 6
            for action, label, key, bw in row:
                _action_button(screen,client,view,pygame.Rect(x,box.y+29+68*row_n,bw,65),action,label,key,font)
                x += bw + 3

    _draw_bag(screen, client, view, font, small, actions)
    _draw_fletch(screen, client, view, font, small, actions)

    # Right info is small by default. Details expands within the viewport only.
    iw = 230 if not view.details_open else min(300, width - left.right - 16)
    lines = _info_lines(client, view, iw-16, small)
    st = view.status or {}
    sandbox = bool(st.get("sandbox")) and st.get("status") not in ("locking", "active", "resolving") and view.details_open
    players = [r for r in st.get("sandbox_players") or [] if isinstance(r, dict)] if sandbox else []
    extra = 42 + 22*len(players) if sandbox else 0
    objectives = objective_rows(view)
    objective_h = 25 + 18*len(objectives) + 24
    available = max(90, actions.y - 90 - 8)
    cap = min(12, max(1, (available - 34 - objective_h)//16))
    if not view.details_open and len(lines) > cap:
        lines = lines[:max(0,cap-1)] + ["More in Details / Tab"]
    ih = min(available, 34 + objective_h + 16*len(lines) + extra)
    info = pygame.Rect(width-iw-8, 90, iw, ih)
    box = _panel(screen, view, "info", "Details / wheel" if view.details_open else "Siege info", info, font)
    if box:
        y = box.y+31
        _text(screen,font,"Siege Objectives",(box.x+9,y),box.w-18,(249,210,131));y+=24
        for label,state in objectives:
            _draw_progress(screen,(box.x+15,y+6),state)
            _text(screen,font,label,(box.x+29,y),box.w-38,TEXT if state!='failed' else (204,145,126));y+=18
        pygame.draw.line(screen,GOLD,(box.x+8,y+2),(box.right-8,y+2))
        _text(screen,small,"Battle info" if battle else "Lobby info",(box.x+9,y+9),box.w-18,MUTED)
        body_top = box.y+30+objective_h
        body = pygame.Rect(box.x+3, body_top, box.w-6, max(1,box.bottom-body_top-4))
        view.hud_info_scroll_max = max(0, 16*len(lines) + extra - body.h)
        view.hud_info_scroll = max(0,min(getattr(view,"hud_info_scroll",0),view.hud_info_scroll_max)) if view.details_open else 0
        previous_clip=screen.get_clip();screen.set_clip(body)
        first_button=len(view.buttons)
        y = body.y+1-view.hud_info_scroll
        for line in lines:
            _text(screen, small, line, (box.x+8,y), box.w-16, (255,191,132) if view.error and line in k._wrap(small,k._placement_hint(view.error),iw-16) else TEXT); y+=16
        if sandbox:
            _text(screen, small, "SANDBOX ONLY / click to assign", (box.x+7,y),box.w-14,(230,177,111));y+=18
            for row in players:
                pid=int(row["player_id"])
                side={"attack":"attack", "defend":"defend"}.get(view.prep_side.get(pid),"left out")
                _button(screen,view,pygame.Rect(box.x+5,y,box.w-10,20),"side-"+str(pid),str(row.get("name") or pid)+": "+side,small);y+=22
            _button(screen,view,pygame.Rect(box.x+5,y,box.w-10,22),"prep","Prepare next test siege",small)
        screen.set_clip(previous_clip)
        # Only visible pieces of scrolled buttons are interactive.
        view.buttons[first_button:] = [(r.clip(body),a) for r,a in view.buttons[first_button:] if r.colliderect(body)]

    _draw_tip(screen,view,font)
