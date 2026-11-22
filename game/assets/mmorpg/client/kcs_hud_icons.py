"""Small HUD icons: actual engine sprites and supersampled gold tool symbols.
Read-only art loading. Never creates assets or changes the shared art symlinks.
"""
import os
from pathlib import Path
import pygame

_CACHE = {}


def engine_path(kind):
    import kcs_client as k
    root = os.environ.get('KCS_VISUAL_FIXTURES')
    roots = ([Path(root)/'assets'/'baked_m9', Path(root)/'baked_m9'] if root else [])
    roots.append(Path(k._parity_path())/'assets'/'baked_m9')
    for folder in roots:
        path = folder/(kind+'_000_intact.png')
        if path.is_file():
            return path
    return None


def icon(action, size=(36, 30), disabled=False):
    """Return the icon and its actual file path (or 'drawn:<tool>')."""
    kind = action[5:] if action.startswith('type-') else None
    path = engine_path(kind) if kind else None
    source = str(path) if path else 'drawn:'+action
    key = (source, tuple(size), bool(disabled))
    if key not in _CACHE:
        if path:
            image = pygame.image.load(str(path))
            bounds = image.get_bounding_rect(min_alpha=10)
            image = image.subsurface(bounds).copy() if bounds.w and bounds.h else image
            if kind in ('ladder','trebuchet'):
                image.fill((38,34,25,0),special_flags=pygame.BLEND_RGB_ADD)
            scale = min(size[0]/image.get_width(), size[1]/image.get_height())
            image = pygame.transform.smoothscale(image, (max(1,round(image.get_width()*scale)),max(1,round(image.get_height()*scale))))
            result = pygame.Surface(size,pygame.SRCALPHA)
            result.blit(image,((size[0]-image.get_width())//2,(size[1]-image.get_height())//2))
        else:
            result = pygame.transform.smoothscale(_symbol(action),size)
        if disabled:
            result = pygame.transform.grayscale(result)
            result.set_alpha(115)
        _CACHE[key] = result
    return _CACHE[key], source


def _symbol(action):
    s=pygame.Surface((96,96),pygame.SRCALPHA)
    gold=(236,197,111);dark=(112,77,34);light=(255,225,157)
    def pts(points):return [(int(x*3),int(y*3)) for x,y in points]
    def line(points,color=gold,width=2):pygame.draw.lines(s,color,False,pts(points),width*3)
    def poly(points,color=gold):pygame.draw.polygon(s,color,pts(points))
    def rect(x,y,w,h,color=gold,width=0):pygame.draw.rect(s,color,(x*3,y*3,w*3,h*3),width*3,border_radius=3)
    if action in ('build','repair'):
        line([(8,27),(22,9)],dark,5);line([(8,27),(22,9)],gold,3)
        poly([(16,6),(21,3),(29,10),(25,15)]);line([(17,6),(24,13)],light,1)
        if action=='repair':
            line([(4,7),(26,27)],gold,2);line([(3,3),(3,8),(8,9),(10,5)],gold,2)
    elif action=='turn':
        pygame.draw.arc(s,gold,(15,12,66,66),.2,5.4,7)
        poly([(19,2),(29,5),(24,13)])
    elif action=='view':
        poly([(2,17),(9,9),(22,9),(30,17),(22,24),(9,24)],dark)
        line([(2,17),(9,9),(22,9),(30,17),(22,24),(9,24),(2,17)],gold,1)
        pygame.draw.circle(s,gold,(48,49),15);pygame.draw.circle(s,dark,(48,49),6)
        rect(21,22,9,8,gold);pygame.draw.arc(s,gold,(65,53,23,26),0,3.14,5)
    elif action=='face':
        for x,y in [(3,5),(15,5),(3,13),(15,13)]:rect(x,y,11,7,dark);rect(x,y,11,7,gold,1)
        line([(16,30),(16,19)],light,3);poly([(10,24),(16,17),(22,24)],light)
    elif action=='fire':
        poly([(15,1),(24,11),(23,17),(29,14),(28,25),(21,31),(10,30),(4,24),(6,14),(12,18)],dark)
        poly([(15,3),(21,13),(18,19),(25,18),(24,26),(16,29),(9,25),(10,18),(14,21)],gold)
        poly([(17,18),(20,25),(15,28),(12,25)],light)
    elif action=='pack':
        rect(4,13,24,16,dark);rect(4,13,24,16,gold,1)
        line([(4,17),(28,17)],gold,1);line([(10,13),(10,29),(22,29),(22,13)],gold,1)
        line([(16,13),(16,3)],light,2);poly([(11,7),(16,1),(21,7)],light)
    elif action=='strike':
        poly([(5,26),(23,4),(29,2),(28,9),(10,29)],gold)
        line([(9,24),(26,5)],light,1);line([(4,19),(14,29)],dark,4);line([(4,19),(14,29)],gold,2)
        line([(6,25),(2,30)],gold,3)
    elif action=='claim':
        poly([(3,8),(10,16),(16,3),(22,16),(29,8),(26,27),(6,27)],dark)
        line([(3,8),(10,16),(16,3),(22,16),(29,8),(26,27),(6,27),(3,8)],gold,2)
        rect(6,25,20,4,gold);pygame.draw.circle(s,light,(48,56),7)
    elif action=='clock':
        pygame.draw.circle(s,gold,(48,48),38,6);line([(16,7),(16,16),(23,20)],gold,2)
    else:
        # Visible missing-art fallback, never silently counted as real engine art.
        rect(3,9,26,16,dark);rect(3,9,26,16,gold,1);line([(6,24),(25,10)],gold,2)
    return s
