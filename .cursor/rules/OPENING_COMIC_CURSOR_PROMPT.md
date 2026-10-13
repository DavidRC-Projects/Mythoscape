# Opening comic for a new game

Paste this into Cursor on the Mythoscape repo, branch `castle-interiors-v2`.

## What to build

When the player starts a **new game**, show a 7-page painted comic before the world. Click or press Space / Enter to go to the next page. Escape or a Skip button closes it and starts the game. The last page's click also starts the game.

Do not show it when loading a saved game.

## Flag

Add `USE_OPENING_COMIC` in the feature flags, **default off**. When it is off, new game behaves exactly as it does now.

## Art

Copy `pages/page_01.jpg` through `pages/page_07.jpg` to:

`game/assets/mmorpg/assets/opening_comic/`

Scale each page to fit the game window, keep the aspect ratio, letterbox with a near-black background. Do not crop the panels.

## Lines

Show the line for the current page in a bar along the bottom. These are the narrator lines. Do not add speech bubbles onto the paintings.

1. The king does not rule this land. He eats it.
2. Every coin in the deep belongs to him now.
3. A guild, and a castle. Only then may you challenge the crown.
4. Armour first. Then the levels. Then the people who will stand with you.
5. Quests fill the purse. Dungeons make you strong enough to spend it.
6. The guild has a home. The king has a problem.
7. Not today. When the clan is ready, the war begins.

Page 7 is the last page. After it, enter the world as a new game already does.

## Voice

Do not generate a voice and do not imitate a real actor. Leave a hook so a later `page_01.ogg` through `page_07.ogg` in the same folder can play with the page if the file exists. If the file is missing, show the text only. No error if the sound is absent.

## How to change the code

Small hook only. Find where a new game is created and the first frame of the world is drawn. Before that, if the flag is on and this is a new game, run a short comic state: page index, blit, bottom line, next / skip.

Do not rewrite the client. Do not edit the walk cycle: `pose_walk`, `rs_style.py` walk posing, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.

Do not change castle, Emberdeep, or HUD behaviour.

## Done when

- Flag off: new game is unchanged.
- Flag on, new game: pages 1 to 7, click advances, skip works, then the normal new game.
- Load game: comic does not play.
