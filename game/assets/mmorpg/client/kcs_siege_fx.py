"""Shared player arrows and read-only siege art caches. Effects never enter gameplay lists."""
import json, math
from pathlib import Path
import pygame
_ROOT = None
_META, _STRIPS, _FRAMES = {}, {}, {}

def configure(root):
    global _ROOT
    root = Path(root)
    if _ROOT != root:
        _ROOT = root
        for cache in (_META, _STRIPS, _FRAMES): cache.clear()

def _bound(cache, key, value, limit):
    if len(cache) >= limit: cache.pop(next(iter(cache)))
    cache[key] = value
    return value

def _meta(group, name):
    key = (group, name)
    if key in _META: return _META[key]
    if _ROOT is None: return None
    p = _ROOT / group / name / 'manifest.json'
    if not p.is_file(): return None
    return _bound(_META, key, json.loads(p.read_text()), 16)

def _frame(group, name, action, rotation, progress, scale, alpha=255):
    meta = _meta(group, name)
    if meta is None: return None
    desc = meta['actions'].get(action)
    if desc is None: return None
    n = desc['frames'];k = min(n-1, max(0, round(progress*(n-1))))
    # Quantisation bounds the fade cache rather than creating a surface/player.
    scale = round(scale, 3);alpha = max(0, min(255, round(alpha/17)*17))
    key = (group, name, action, rotation, k, scale, alpha)
    if key in _FRAMES: return _FRAMES[key]
    skey = (group, name, action, rotation)
    strip = _STRIPS.get(skey)
    if strip is None:
        path = _ROOT / group / name / f'{action}_{rotation:03d}.png'
        if not path.is_file(): return None
        strip = _bound(_STRIPS, skey, pygame.image.load(str(path)).convert_alpha(), 8)
    w,h=meta['cell'];cell=strip.subsurface(pygame.Rect(k*w,0,w,h))
    cell=pygame.transform.smoothscale(cell,(max(1,round(w*scale)),max(1,round(h*scale))))
    if alpha!=255: cell.set_alpha(alpha)
    foot=meta['foot_px']
    return _bound(_FRAMES,key,(cell,(foot[0]*scale,foot[1]*scale)),192)

def engine_blit(surf, root, name, rotation, action, progress, foot, tile_scale):
    configure(root);meta=_meta('engine_motion_v2',name)
    if meta is None: return False
    frame=_frame('engine_motion_v2',name,action,rotation,progress,tile_scale/meta['px_per_tile'])
    if frame is None:return False
    cell,anchor=frame;surf.blit(cell,(int(foot[0]-anchor[0]),int(foot[1]-anchor[1])));return True

def decal_blit(surf, root, name, progress, foot, tile_scale, alpha=255, rotation=0):
    configure(root);meta=_meta('siege_fx_v2',name)
    if meta is None: return False
    frame=_frame('siege_fx_v2',name,'effect',rotation,progress,tile_scale/meta['px_per_tile'],alpha)
    if frame is None:return False
    cell,anchor=frame;surf.blit(cell,(int(foot[0]-anchor[0]),int(foot[1]-anchor[1])));return True

def projectile(surf, start, end, progress, family, scale):
    p=max(0,min(1,progress));x=start[0]+(end[0]-start[0])*p;y=start[1]+(end[1]-start[1])*p
    if family=='trebuchet':
        y-=max(28,80*scale)*math.sin(math.pi*p)
        pygame.draw.circle(surf,(80,77,71),(round(x),round(y)),max(3,round(5*scale)))
        pygame.draw.circle(surf,(157,150,134),(round(x-1),round(y-1)),max(1,round(2*scale)))
    elif family=='cauldron':
        y-=12*math.sin(math.pi*p)
        for i in range(4):pygame.draw.circle(surf,(108+i*15,58+i*6,17),(round(x+i*2),round(y-i*5)),max(2,round(4*scale)))
    else:
        dx,dy=end[0]-start[0],end[1]-start[1];length=max(1,math.hypot(dx,dy));ux,uy=dx/length,dy/length
        size=14 if family=='ballista' else 10
        tail=(x-ux*size,y-uy*size);tip=(round(x+ux*3),round(y+uy*3))
        pygame.draw.line(surf,(220,185,115),tail,(x,y),2)
        pygame.draw.polygon(surf,(218,218,211),[tip,(x-ux*3-uy*3,y-uy*3+ux*3),(x-ux*3+uy*3,y-uy*3-ux*3)])
        pygame.draw.line(surf,(217,222,217),(tail[0]-uy*3,tail[1]+ux*3),(tail[0]+uy*3,tail[1]-ux*3),2)


# Player arrows share this presentation in the siege and overworld renderers.
# The server still owns hits/damage. All positions below are screen-space only.
ARROW_STUCK_LIMIT = 3
ARROW_LIFE = 1.65
ARROW_TORSO = 50.0


def _arrow(surf, tip, direction, scale, alpha=255, trail=False, embedded=False):
    """A thin, antialiased shaft, small steel head and two short feather barbs."""
    ux, uy = direction
    scale = max(.25, min(2., float(scale)))
    length = max(5., min(18., 11.*scale)) * (.82 if embedded else 1.)
    head = max(1.2, 2.4*scale)
    pad = int(length + max(8, 24*scale) + 8)
    cell = pygame.Surface((pad*2, pad*2), pygame.SRCALPHA)
    tip = (float(tip[0]), float(tip[1]));x=y=float(pad)
    tail = (x-ux*length, y-uy*length)
    def color(rgb, a=1.):return (*rgb, max(0,min(255,int(alpha*a))))
    if trail:
        for i in range(3):
            a=length+(i+1)*max(2.5,5*scale);b=length+i*max(2.5,5*scale)
            pygame.draw.aaline(cell,color((220,211,179),.26/(i+1)),(x-ux*a,y-uy*a),(x-ux*b,y-uy*b))
    pygame.draw.aaline(cell,color((44,37,27),.7),(tail[0]+.5,tail[1]+.7),(x+.5,y+.7))
    pygame.draw.aaline(cell,color((184,144,85)),tail,(x-ux*head*.4,y-uy*head*.4))
    pygame.draw.polygon(cell,color((215,222,219)),[(x,y),(x-ux*head-uy*head*.38,y-uy*head+ux*head*.38),(x-ux*head+uy*head*.38,y-uy*head-ux*head*.38)])
    feather=max(1.,1.8*scale)
    for side in (-1,1):
        pygame.draw.aaline(cell,color((205,199,175),.9),(tail[0]+ux*2*scale,tail[1]+uy*2*scale),(tail[0]-uy*feather*side,tail[1]+ux*feather*side))
    surf.blit(cell,(round(tip[0]-pad),round(tip[1]-pad)))


def _arrow_puff(surf, point, age, scale, ground=False):
    if not 0 <= age < .28:return
    u=age/.28;pad=max(12,round(18*scale));cell=pygame.Surface((pad*2,pad*2),pygame.SRCALPHA)
    for i in range(6):
        angle=i*math.tau/6+.35
        r=(1+6*u)*scale
        at=(round(pad+math.cos(angle)*r),round(pad+math.sin(angle)*r*(.4 if ground else .7)-u*3*scale))
        pygame.draw.circle(cell,(205,187,150,int(150*(1-u))),at,max(1,round((1.1+u)*scale)))
    if not ground and age < .075:
        for i in range(3):
            a=i*math.tau/3+.3
            pygame.draw.aaline(cell,(237,220,169,int(200*(1-age/.075))),(pad+math.cos(a)*scale,pad+math.sin(a)*scale),(pad+math.cos(a)*3.5*scale,pad+math.sin(a)*3.5*scale))
    surf.blit(cell,(round(point[0]-pad),round(point[1]-pad)))


def _set_presented_hp(client, pid, hp):
    local=getattr(client,"player",None) or {}
    if local.get("id")==pid:local["hp"]=hp
    other=(getattr(client,"players",{}) or {}).get(pid)
    if other is not None:other["hp"]=hp


def present_contacts(client, view, now):
    """Keep HUD/state snapshots from displaying a bundled bow hit before arrival."""
    pending=getattr(view,"arrow_hp",[]);keep=[]
    for row in pending:
        if now >= row["at"]:_set_presented_hp(client,row["pid"],row["hp"])
        else:keep.append(row)
    held=set()
    for row in keep:
        if row["pid"] not in held:
            _set_presented_hp(client,row["pid"],row["before"]);held.add(row["pid"])
    view.arrow_hp=keep


def record_arrow_contact(client, view, event, now):
    """Pair an authoritative result with its existing shot. No speculative hit."""
    aid=event.get("action_id")
    shot=next((s for s in reversed(view.shots) if aid and s.get("action_id")==aid and s.get("weapon")=="bow"),None)
    if shot is None:return False
    if "hit" in shot:return True  # duplicate packet cannot add another stuck arrow
    at=max(now,shot["start"]+float(shot.get("impact_seconds",shot["duration"]*shot.get("release",.62)+shot.get("flight_seconds",.24))))
    hit=bool(event.get("hit",True));pid=event.get("player_id",shot.get("target_id"))
    shot.update(hit=hit,contact_at=at,until=at+ARROW_LIFE,fatal=event.get("hp")==0)
    if hit:
        view.actor_hits[pid]=at+.36
        if hasattr(client,"player_hit_at"):client.player_hit_at[pid]=at
        stuck=[s for s in view.shots if s.get("hit") and s.get("target_id")==pid and s.get("until",0)>now]
        for old in stuck[:-ARROW_STUCK_LIMIT]:old["stuck_suppressed"]=True
    if event.get("hp") is not None:
        pending=getattr(view,"arrow_hp",[])
        person=(getattr(client,"player",{}) or {}) if (getattr(client,"player",{}) or {}).get("id")==pid else (getattr(client,"players",{}) or {}).get(pid,{})
        previous=next((r["hp"] for r in reversed(pending) if r["pid"]==pid),person.get("hp",event["hp"]))
        pending.append({"pid":pid,"at":at,"before":previous,"hp":event["hp"]})
        view.arrow_hp=pending[-128:]
        present_contacts(client,view,now)
    return True


def draw_player_arrows(surf, view, now, project, person_position, scale):
    """Reuse the existing bounded shot list; return flight/impact counts for tests."""
    counts={"flight":0,"stuck":0,"ground":0}
    for shot in view.shots:
        if shot.get("weapon")!="bow" or shot.get("target_id") is None:continue
        foot0=project(shot.get("x",0),shot.get("y",0));foot1=project(shot.get("tx",0),shot.get("ty",0))
        if foot0 is None or foot1 is None:continue
        dx,dy=foot1[0]-foot0[0],foot1[1]-foot0[1];length=max(1,math.hypot(dx,dy));ux,uy=dx/length,dy/length
        start=(foot0[0]+ux*7*scale,foot0[1]-ARROW_TORSO*scale+uy*7*scale)
        end=(foot1[0]-ux*5*scale,foot1[1]-ARROW_TORSO*scale-uy*5*scale)
        release=shot["start"]+shot["duration"]*float(shot.get("release",.62))
        flight=max(.05,float(shot.get("flight_seconds",.24)));planned=release+flight
        contact=shot.get("contact_at",planned+.6)
        if now < release:continue
        if now < contact:
            u=max(0,min(.985,(now-release)/flight));arc=max(1,4*scale)
            tip=(start[0]+(end[0]-start[0])*u,start[1]+(end[1]-start[1])*u-arc*math.sin(math.pi*u))
            vx,vy=end[0]-start[0],end[1]-start[1]-arc*math.pi*math.cos(math.pi*u);n=max(1,math.hypot(vx,vy))
            _arrow(surf,tip,(vx/n,vy/n),scale,trail=True);counts["flight"]+=1;continue
        age=now-contact
        if age >= ARROW_LIFE:continue
        if shot.get("hit",False):
            xy=None if shot.get("fatal") else person_position(shot["target_id"])
            foot=project(*xy) if xy else foot1
            if foot is None:continue
            # Preserve incoming travel direction while following the moving victim.
            torso=ARROW_TORSO*(1-.85*min(1,age/1.0)) if shot.get("fatal") else ARROW_TORSO
            tip=(foot[0]-ux*5*scale,foot[1]-torso*scale-uy*5*scale)
            if not shot.get("stuck_suppressed"):
                fade=max(0,min(1,(ARROW_LIFE-age)/.75))
                _arrow(surf,tip,(ux,uy),scale,alpha=235*fade,embedded=True);counts["stuck"]+=1
            _arrow_puff(surf,tip,age,scale)
        else:
            # Miss: pass the target, drop to the ground, skid, then fade. No recoil.
            fall=min(1,age/.18);skid=max(0,min(1,(age-.18)/.24));advance=(12*fall+6*(1-(1-skid)**2))*scale
            tip=(end[0]+ux*advance,end[1]+(foot1[1]-end[1])*fall*fall+uy*advance)
            fade=max(0,min(1,(1.25-age)/.55));_arrow(surf,tip,(ux,uy),scale,alpha=190*fade)
            _arrow_puff(surf,(end[0]+ux*12*scale,foot1[1]+uy*12*scale),age-.18,scale,ground=True)
            counts["ground"]+=1
    return counts
