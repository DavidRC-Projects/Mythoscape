"""Cached M9-pipeline sprites. Fixed camera, gentle eight-frame banner loops.

Props use real ground footprints and depth masks; not UI billboards. Scaled art
and inverse-alpha masks are bounded caches, with no disk IO after warm-up.
"""
from pathlib import Path
import json,os,time
import pygame
_IMAGES={};_SCALED={};_MASKS={}

_ROOTS={}

def _root(stem):
    # Resolved once per stem (no per-frame disk stats).
    if stem not in _ROOTS:
        root=Path(os.environ.get('KCS_VISUAL_FIXTURES','/tmp/kcs_visual_fixtures'))/'assets'/'baked_round3f'
        if not (root/'bench_000_00.png').is_file():
            # This round's new art is self-contained in the test worktree; do not
            # write through the legacy/main art symlinks or alter old fixtures.
            root=Path(__file__).resolve().parents[1]/'fixtures'/'kcs_visual_gear_anim_v1'/'assets'/'baked_round3f'
        if not (root/(stem+'.png')).is_file():
            # Round 3g turned-view (90/180/270) and ambient bakes, same worktree fixtures.
            root=Path(__file__).resolve().parents[1]/'fixtures'/'kcs_visual_gear_anim_v1'/'assets'/'baked_round3g'
        _ROOTS[stem]=root
    return _ROOTS[stem]

def _asset(stem,scale):
    root=_root(stem)
    key=(str(root),stem)
    if key not in _IMAGES:
        path=root/(stem+'.png')
        if not path.is_file():return None
        _IMAGES[key]=(pygame.image.load(str(path)).convert_alpha(),json.loads(path.with_suffix('.json').read_text()))
    img,meta=_IMAGES[key];f=scale/float(meta['px_per_tile']);size=(max(1,round(img.get_width()*f)),max(1,round(img.get_height()*f)))
    sk=key+size
    if sk not in _SCALED:
        if len(_SCALED)>=260:_SCALED.pop(next(iter(_SCALED)))
        _SCALED[sk]=pygame.transform.smoothscale(img,size)
    return _SCALED[sk],(meta['foot_px'][0]*f,meta['foot_px'][1]*f),sk

def _turned(rotation):
    """World facing to the baked camera-relative facing in a turned view."""
    from kings_castle_siege_map import angled_view as av
    return int(rotation-(av.view_quarter() if av.QUARTERS else 0)*90)%360

def _hidden_face(view,row):
    """A banner hangs on one outer face; in a turned view that face can be
    turned away from the camera, where its own stone must hide it."""
    from kings_castle_siege_map import angled_view as av
    if not av.QUARTERS:return False
    r=view.bf.keep_rect if row.get('attached')=='keep' else view.bf.wall_box
    x,y=row['x'],row['y']
    side=min((abs(y-r[3]-1),'s'),(abs(x-r[0]),'w'),(abs(y-r[1]),'n'),(abs(x-r[2]-1),'e'))[1]
    return side not in av.FRONT_SIDES[av.view_quarter()]

def _inverse(sprite,key):
    if key not in _MASKS:
        if len(_MASKS)>=192:_MASKS.pop(next(iter(_MASKS)))
        _MASKS[key]=pygame.mask.from_surface(sprite,90).to_surface(setcolor=(255,255,255,0),unsetcolor=(255,255,255,255))
    return _MASKS[key]

def _cut(image,box,occluders):
    touched=False
    for other,otherbox,key in occluders:
        hit=box.clip(otherbox)
        if not hit.width or not hit.height:continue
        if not touched:image=image.copy();touched=True
        image.blit(_inverse(other,key),(hit.x-box.x,hit.y-box.y),pygame.Rect(hit.x-otherbox.x,hit.y-otherbox.y,hit.w,hit.h),special_flags=pygame.BLEND_RGBA_MULT)
    return image

def _ray_hits(x,y,rect):
    # Ray from prop towards the fixed SW camera; slab intersection in world XY.
    from kings_castle_siege_map import angled_proj as P
    lo,hi=0.,1e6
    for pos,d,a,b in ((x,-P.SIN_Y,rect[0],rect[2]+1),(y,P.COS_Y,rect[1],rect[3]+1)):
        t0,t1=sorted(((a-pos)/d,(b-pos)/d));lo=max(lo,t0);hi=min(hi,t1)
    return hi>max(lo,.01)

_BOXES={}

def _castle_hull(view):
    """Screen boxes of all castle plates this frame; props whose sprite box
    misses every one skip the per-plate ray test entirely."""
    from kings_castle_siege_map import angled_view as av,angled_proj as P
    import kcs_client as k
    states=k._gate_states(view)
    key=(id(view.bf),view.origin,view.scale,view.screen_o,tuple(sorted(states.items())),av.QUARTERS,av.view_quarter(),av.GATE_GRILLE)
    if key not in _BOXES:
        _BOXES.clear();boxes=[]
        for name,wx,wy,r,height,front in av.building_placements(view.bf,states):
            img,meta=av.load_baked(name);f=view.scale/av._px_per_tile(meta)
            sx,sy,_=P.project(wx,wy,0,view.origin,view.scale,view.screen_o)
            boxes.append(pygame.Rect(int(sx-meta['foot_px'][0]*f),int(sy+k.HUD_TOP-meta['foot_px'][1]*f),round(img.get_width()*f),round(img.get_height()*f)))
        _BOXES[key]=boxes
    return _BOXES[key]

def _castle(view,x,y,z,attached=None):
    from kings_castle_siege_map import angled_view as av,angled_proj as P
    import kcs_client as k
    states=k._gate_states(view);result=[]
    cutaway=getattr(view,'cutaway',(False,False))
    # Same plate list the static layer paints. Cut-away foreground stone is
    # composited AFTER dynamics instead, with its actual translucent pixels.
    for name,wx,wy,r,height,front in av.building_placements(view.bf,states):
        base=name.rsplit('/',1)[-1]
        if cutaway[0] and front:continue
        if base.startswith('keep') and (attached=='keep' or cutaway[1]):continue
        if attached=='wall' and base.startswith(('wall_','gatehouse')):continue
        if z>=height or not _ray_hits(x,y,r):continue
        img,meta=av.load_baked(name);f=view.scale/av._px_per_tile(meta);size=(max(2,round(img.get_width()*f)),max(2,round(img.get_height()*f)));key=('castle',name,*size)
        if key not in _SCALED:
            if len(_SCALED)>=160:_SCALED.pop(next(iter(_SCALED)))
            _SCALED[key]=pygame.transform.smoothscale(img,size)
        sx,sy,_=P.project(wx,wy,0,view.origin,view.scale,view.screen_o)
        box=pygame.Rect(int(sx-meta['foot_px'][0]*f),int(sy+k.HUD_TOP-meta['foot_px'][1]*f),*size)
        result.append((_SCALED[key],box,key))
    return result

def restore_castle(surf,view,x,y,area):
    """Turned views: a ground engine behind a wall/tower gets the nearer
    stone re-painted over it (only that stone's own pixels, only near it)."""
    from kings_castle_siege_map import angled_view as av
    if not (av.QUARTERS and (view.status or {}).get('decor')) or area.collidelist(_castle_hull(view))<0:return 0
    n=0
    for img,box,key in _castle(view,x,y,0.5):
        hit=box.clip(area)
        if hit.width and hit.height:surf.blit(img,hit.topleft,hit.move(-box.x,-box.y));n+=1
    return n

_PREWARMED=set()

def prewarm_assets(view,deadline):
    """Under a quarter_context: load+scale the turned prop sprites of that
    quarter a few at a time, so turning the camera does not decode them all
    in one frame. Returns True when that quarter is done at this zoom."""
    from kings_castle_siege_map import angled_view as av
    import kcs_decor
    if not ((view.status or {}).get('decor') and view.bf and av.QUARTERS):return True
    tag=(id(view.bf),av.view_quarter(),round(view.scale,2))
    if tag in _PREWARMED:return True
    for row in kcs_decor.layout(view.bf.plane):
        if row.get('ambient'):continue
        frames=8 if row['kind'].startswith('lion') else 6 if row['kind']=='fountain' else 1
        for frame in range(frames):
            if time.perf_counter()>=deadline:return False
            _asset(f"{row['kind']}_{_turned(row['rotation']):03d}_{frame:02d}",view.scale)
    _PREWARMED.add(tag);return True

def engine_visibility(view,x,y,cell,topleft,size=None):
    """Share (0..1) of an engine sprite's own opaque pixels NOT covered by
    the castle stone in front of it (same occluders restore_castle paints).
    1.0 when no castle plate can be in front."""
    from kings_castle_siege_map import angled_view as av
    if (cell is None and size is None) or not (av.QUARTERS and (view.status or {}).get('decor')):return 1.0
    area=pygame.Rect(topleft,cell.get_size() if cell is not None else size)
    if area.collidelist(_castle_hull(view))<0:return 1.0
    occ=[(img,box,key) for img,box,key in _castle(view,x,y,0.5) if box.colliderect(area)]
    if not occ:return 1.0
    mine=pygame.mask.from_surface(cell,40) if cell is not None else pygame.mask.Mask(area.size,fill=True);total=mine.count()
    if not total:return 1.0
    cover=pygame.mask.Mask(area.size)
    for img,box,key in occ:
        mk=_MASKS.get(('occ',)+tuple(key))
        if mk is None:
            if len(_MASKS)>=120:_MASKS.pop(next(iter(_MASKS)))
            mk=_MASKS[('occ',)+tuple(key)]=pygame.mask.from_surface(img,127)
        cover.draw(mk,(box.x-area.x,box.y-area.y))
    return 1.0-mine.overlap_area(cover,(0,0))/total

def clear_of_ui(rect,view,screen,anchor_top=None):
    """Move a small map label so it does not sit under a HUD panel (last
    frame's panel rects) or off screen. Tries below, above the anchor, then
    nudges sideways. None when no clear spot exists."""
    regions=[r for r in getattr(view,'ui_regions',[]) or []]
    bounds=screen.inflate(-4,-4)
    def ok(r):return bounds.contains(r) and r.collidelist(regions)<0
    if ok(rect):return rect
    cands=[]
    if anchor_top is not None:cands.append(rect.move(0,anchor_top-rect.h-3-rect.y))
    for r in regions:
        if rect.colliderect(r):
            cands+=[rect.move(0,r.top-3-rect.bottom),rect.move(r.left-3-rect.right,0),rect.move(r.right+3-rect.x,0),rect.move(0,r.bottom+3-rect.y)]
    for c in cands:
        c=c.clamp(bounds)
        if ok(c):return c
    return None

def paint(surf,client,view,attachments=False):
    started=time.perf_counter()
    if not attachments:view.decor_sprites=[];view.decor_count=0
    if not (view.status or {}).get('decor') or not view.bf:return
    import kcs_decor,kcs_client as k
    from kings_castle_siege_map import angled_proj as P
    states=k._gate_states(view);now=time.time()
    rows=kcs_decor.layout(view.bf.plane)
    if view.bf.plane.width>=400 and view.origin is not None:
        # ~1.8k ambient items on the large map: keep only the on-screen window.
        w,h=surf.get_size();pts=[P.unproject(x,y,view.origin,view.scale,view.screen_o,0.) for x,y in ((0,0),(w,0),(0,h),(w,h))]
        ax0=min(q[0] for q in pts)-10;ax1=max(q[0] for q in pts)+10;ay0=min(q[1] for q in pts)-6;ay1=max(q[1] for q in pts)+16
        # Distance LOD: tiny ground detail drops out when zoomed far out.
        small={'tuft','flowers'} if view.scale<12 else set()
        if view.scale<9:small|={'bush','field_rock'}
        rows=[r for r in rows if not r.get('ambient') or (r['kind'] not in small and ax0<=r['x']<=ax1 and ay0<=r['y']<=ay1)]
    rows=sorted(rows,key=lambda r:P.depth_of(r['x'],r['y'],view.origin),reverse=True)
    missing=set()
    for row in rows:
        if (row['kind']=='lion_banner')!=attachments:continue
        if row.get('opening_id') and states.get(row['opening_id'])=='destroyed':continue
        # A banner attached to a breakable curtain disappears with its stone.
        if row['kind']=='lion_banner' and not row.get('opening_id'):
            if any(states.get(oid)=='destroyed' and obj.rect[0]-1<=row['x']<=obj.rect[2]+1 and obj.rect[1]-1<=row['y']<=obj.rect[3]+1 for oid,obj in view.bf.plane.openings.items()):continue
        if row.get('attached') in ('wall','keep') and _hidden_face(view,row):continue
        if row.get('ambient'):
            # Wind: trees and tufts loop four sway frames; others are variants.
            sway=row['kind'] in ('oak','pine','tuft')
            frame=int(now*(2.4 if row['kind']=='tuft' else 1.5)+row['variant']*1.3+row['x']*.07)%4 if sway else row['variant']
            stem=f"{row['kind']}_000_{frame:02d}"
        else:
            frames=8 if row['kind'].startswith('lion') else 6 if row['kind']=='fountain' else 1
            frame=int(now*(3 if frames==8 else 6)+sum(ord(c) for c in row['id'])*.1)%frames
            stem=f"{row['kind']}_{_turned(row['rotation']):03d}_{frame:02d}"
        # Flower beds are baked one tile wide; at play zoom that read as
        # specks, so they are drawn as larger clumps.
        asset=_asset(stem,view.scale*(1.7 if row['kind']=='flowers' else 1.0))
        if not asset:
            missing.add(stem);asset=_asset(f"{row['kind']}_{row['rotation']:03d}_{frame:02d}",view.scale)
            if not asset:continue
        img,foot,key=asset;sx,sy,_=P.project(row['x'],row['y'],row['z'],view.origin,view.scale,view.screen_o)
        box=pygame.Rect(round(sx-foot[0]),round(sy+k.HUD_TOP-foot[1]),*img.get_size())
        if not surf.get_rect().colliderect(box):continue
        if (not row.get('ambient') or row.get('near')) and box.collidelist(_castle_hull(view))>=0:
            img=_cut(img,box,_castle(view,row['x'],row['y'],row['z']+row['height'],row.get('attached')))
        if attachments and ((row.get('attached')=='wall' and getattr(view,'cutaway',(False,False))[0]) or (row.get('attached')=='keep' and getattr(view,'cutaway',(False,False))[1])):
            # Faded stone hides its own banners; a ghost banner read as a
            # flag floating through the wall.
            continue
        surf.blit(img,box);view.decor_sprites.append((row,img,box,('prop',row['id'],key,tuple(sorted(states.items())))));view.decor_count+=1
    view.decor_missing=sorted(set(getattr(view,'decor_missing',[]) if attachments else [])|missing)
    elapsed=(time.perf_counter()-started)*1000
    view.decor_ms=(getattr(view,'decor_ms',0)+elapsed) if attachments else elapsed

def actor_blit(dest,view,position,foot_screen,draw,**kwargs):
    """Actors behind furniture are cut by its silhouette, never pasted on it."""
    if not (view.status or {}).get('decor'):return draw(dest,foot_screen=foot_screen,**kwargs)
    from kings_castle_siege_map import angled_proj as P
    x,y=position;depth=P.depth_of(x+.5,y+.5,view.origin)
    import kcs_client as k
    ground=P.project(x+.5,y+.5,0,view.origin,view.scale,view.screen_o)
    floor=max(0,(ground[1]+k.HUD_TOP-foot_screen[1])/(view.scale*P.COS_P))
    occluders=_castle(view,x+.5,y+.5,floor+1.9)
    for row,img,box,key in getattr(view,'decor_sprites',[]):
        if floor>=row['z']+row['height']:continue
        if depth>P.depth_of(row['x'],row['y'],view.origin):occluders.append((img,box,key))
    if not occluders:return draw(dest,foot_screen=foot_screen,**kwargs)
    box=pygame.Rect(round(foot_screen[0])-128,round(foot_screen[1])-220,256,256)
    image=pygame.Surface(box.size,pygame.SRCALPHA);ok=draw(image,foot_screen=(128,220),**kwargs)
    if ok:dest.blit(_cut(image,box,occluders),box)
    return ok


def station(surf,view,row):
    """HD furnace/anvil, but original real forge/mining rules and packet types."""
    import kcs_client as k
    from kings_castle_siege_map import angled_proj as P
    frame=int(time.time()*4)%4 if row['kind']=='furnace' else 0
    asset=_asset(f"{row['kind']}_{_turned(0):03d}_{frame:02d}",view.scale) or _asset(f"{row['kind']}_000_{frame:02d}",view.scale)
    if not asset:return None
    img,foot,key=asset;x,y=row['x']+.5,row['y']+.5
    sx,sy,_=P.project(x,y,0,view.origin,view.scale,view.screen_o);box=pygame.Rect(round(sx-foot[0]),round(sy+k.HUD_TOP-foot[1]),*img.get_size())
    surf.blit(_cut(img,box,_castle(view,x,y,3.5 if row['kind']=='furnace' else 1.5)),box)
    return box


def rock(surf,view,row,draw,size):
    """Existing procedural ore rock, drawn off-screen and cut by any castle mass
    between it and the camera, so courtyard ore never paints over towers/walls."""
    import kcs_client as k
    from kings_castle_siege_map import angled_proj as P
    x,y=row['x']+.5,row['y']+.5;sx,sy,_=P.project(x,y,0,view.origin,view.scale,view.screen_o);sy+=k.HUD_TOP
    occluders=_castle(view,x,y,1.2);view.rock_cuts=getattr(view,'rock_cuts',0)+bool(occluders)
    if not occluders:draw(surf,round(sx),round(sy),size)
    else:
        w=max(48,size*4);box=pygame.Rect(round(sx-w//2),round(sy-w+size),w,w)
        image=pygame.Surface(box.size,pygame.SRCALPHA);draw(image,w//2,w-size,size)
        surf.blit(_cut(image,box,occluders),box)
    return rock_rect(sx,sy,size)


def rock_rect(sx,sy,size):
    """Click/hover box = the drawn procedural rock (measured: x -0.77..+1.03,
    y -0.6..+0.57 of size about the tile foot) plus a small margin. The old box
    covered only the top-middle, so clicks on most of the rock just walked."""
    m=3
    return pygame.Rect(round(sx-0.8*size)-m,round(sy-0.62*size)-m,round(1.85*size)+2*m,round(1.22*size)+2*m)


def gate_state(view):
    row=next((r for r in view.openings if (r.get('id') or r.get('opening_id'))=='main_gate'),{})
    maximum=row.get('max_hp') or next((r.get('max_hp',140) for r in (view.status or {}).get('objectives',[]) if r.get('id')=='main_gate'),140)
    hp=row.get('hp',maximum)
    if row.get('state')=='destroyed' or hp<=0:return 3
    # Sally (t652u/t657u): while a defender walks through the main gate it shows raised/open
    # (plate gatehouse_s4 = intact gate with the doors gone; NOT the broken s2/s3 art), then drops
    # back to its HP state shortly after they are clear. Set per frame by kcs_client._note_sally.
    if getattr(view,'gate_sally_until',0)>time.time():return 4
    return 0 if hp/maximum>2/3 else 1 if hp/maximum>1/3 else 2


def foreground(surf,client,view):
    if not (view.status or {}).get('decor') or not view.bf:return
    import kcs_client as k
    from kings_castle_siege_map import angled_view as av,angled_proj as P
    cutaway=getattr(view,'cutaway',(False,False))
    if any(cutaway):av.draw_baked_buildings(surf,view.bf,k._gate_states(view),view.origin,view.scale,(view.screen_o[0],view.screen_o[1]+k.HUD_TOP),clip=surf.get_rect(),cutaway=cutaway,foreground_only=True,alpha=70)
    paint(surf,client,view,attachments=True)
    life(surf,client,view)
    index=gate_state(view);view.gate_grille_state=index
    if av.QUARTERS and av.quarter_plates_ready():return  # grille + doors are part of the gatehouse plate
    asset=_asset(f'portcullis_000_{index:02d}',view.scale)
    if asset:
        img,foot,key=asset;r=view.bf.plane.openings['main_gate'].rect
        sx,sy,_=P.project((r[0]+r[2]+1)/2,r[3]+2.,.25,view.origin,view.scale,view.screen_o)
        if cutaway[0]:img=img.copy();img.set_alpha(90)
        surf.blit(img,(round(sx-foot[0]),round(sy+k.HUD_TOP-foot[1])))


_SMOKE={};_SHADOW={}

def life(surf,client,view):
    """Forge smoke drifting downwind and two bird flocks circling the field
    (large map only). Cheap 2D work, timed into view.life_ms."""
    if view.bf is None or view.bf.plane.width<400 or view.origin is None:view.life_ms=0.;return
    import math
    started=time.perf_counter();now=time.time()
    import kcs_client as k
    from kings_castle_siege_map import angled_view as av,angled_proj as P
    rect=surf.get_rect()
    sources=[(r['x']+.5,r['y']+.5) for r in (getattr(client,'dungeon',None) or {}).get('workshops',[]) if r.get('kind')=='furnace']
    try:base=av._fx('fx_smoke_m9')
    except Exception:base=None
    for sx0,sy0 in (sources if base is not None else ()):
        for i in range(5):
            t=(now*.2+i/5+sx0*.013)%1
            px,py,_=P.project(sx0+t*2.6,sy0-t*.8,3.4+t*8.5,view.origin,view.scale,view.screen_o);py+=k.HUD_TOP
            size=max(6,int(view.scale*(1.1+t*2.6))//4*4)
            if size not in _SMOKE:
                if len(_SMOKE)>24:_SMOKE.clear()
                _SMOKE[size]=pygame.transform.smoothscale(base,(size,max(4,size*base.get_height()//max(1,base.get_width()))))
            img=_SMOKE[size];img.set_alpha(int(120*(1-t)*min(1.,t*6)))
            box=img.get_rect(center=(round(px),round(py)))
            if rect.colliderect(box):surf.blit(img,box)
    for flock in range(2):
        ang=now*.03+flock*3.1;fx=200+125*math.cos(ang);fy=200+115*math.sin(ang*1.3)
        hx,hy=-math.sin(ang),math.cos(ang)*1.3
        n=math.hypot(hx,hy) or 1;hx,hy=hx/n,hy/n
        for b in range(5):
            row=(b+1)//2;side=-1 if b%2 else 1
            x=fx-hx*row*2.4+(-hy)*side*row*1.8;y=fy-hy*row*2.4+hx*side*row*1.8;z=15+.6*math.sin(now*.7+b)
            px,py,_=P.project(x,y,z,view.origin,view.scale,view.screen_o);py+=k.HUD_TOP
            if not rect.inflate(40,40).collidepoint(px,py):continue
            gx,gy,_=P.project(x,y,0,view.origin,view.scale,view.screen_o);gy+=k.HUD_TOP
            sw=max(4,int(view.scale*.9))
            if sw not in _SHADOW:
                sh=pygame.Surface((sw,max(2,sw//3)),pygame.SRCALPHA);pygame.draw.ellipse(sh,(0,0,0,45),sh.get_rect());_SHADOW[sw]=sh
            surf.blit(_SHADOW[sw],(round(gx-sw/2),round(gy)))
            s=max(3.,view.scale*.42);flap=math.sin(now*8.5+b*1.9)
            pts=[(px-s,py-s*.55*flap-s*.15),(px-s*.35,py-s*.12),(px,py),(px+s*.35,py-s*.12),(px+s,py-s*.55*flap-s*.15)]
            pygame.draw.lines(surf,(30,29,33),False,pts,2)
    view.life_ms=(time.perf_counter()-started)*1000
