# Low-poly OSRS-style monsters - reference code

See ../CURSOR_MONSTER_GUIDE.md for the full guide. Quick start (from this folder):

    pip install -r requirements.txt
    python tools/monster_viewer.py goblin_grunt          # interactive (1-4 anims, arrows cycle)
    python tools/anim_test.py                            # headless smoke test, all monsters
    python tools/render_concepts.py --out ../images      # re-render the concept images
    python tools/render_icons.py --out ../icons          # 96 px transparent portrait icons
    python tools/render_sprites.py goblin_grunt --out ../sprites_example
    python tools/make_contact_sheet.py ../images

Tested: Panda3D 1.10.15, Python 3.13, Linux offscreen (llvmpipe).
