# Crownfall — Phase 1: Story reframe (dialogue and text only)

Work directly on `main`. Do each step in turn, run the check after it, and keep every change small.
Paths are relative to `game/assets/mmorpg/` unless stated.

## Step 0 — Before you start
1. Run `git status`. If there are local uncommitted changes, stop and ask David whether to commit them first. Do not stash, reset or discard anything.
2. This prompt was written against GitHub `main` @ 46b6678. If any quoted "old" text below doesn't match, find the nearest equivalent and keep the intent. Do not guess.

## Rules
- No new feature flags. Do not touch the walk cycle, movement, camera or combat.
- Change data and dialogue text only, except for the small code change in Step 3 (the 25→20 check) and Step 2 (the title card page).
- Do not rename folders, modules, the DB, the repo, item ids, NPC ids, quest ids or the `Mythos` gear/knight/outfitter brand. Those are out of scope.
- Taxes, reputation and guilds come in later phases. Nothing may read or depend on a tax rate, reputation or guild system yet. The tax lines are flavour only.
- It must work for new and existing saves. No migrations. Quest ids stay the same (`fairy_oath`).
- After every step, run `python -m py_compile` on each `.py` file you touched, and `python -m json.tool <file> > /dev/null` on each JSON file you touched.

## Already done (verify only, don't redo)
- The window title is already `pygame.display.set_caption("Crownfall")` in `client/client.py` (~line 168).
- The login screen already uses `client/assets/login_title_crownfall.png` (`client/client_screens.py` ~line 279).
- The opening comic is applied: `client/opening_comic.py` has 7 pages and the `OPENING_COMIC` state in `client/client.py`. It sits behind the existing `USE_OPENING_COMIC` flag in `server/feature_flags.py`, which defaults to on. Leave that flag as it is.

## Step 1 — Rename "Mythoscape" in player-facing text
Make exactly these replacements:
- `server/server.py` ~1759: `"Welcome to Mythoscape! Press H anytime for controls · Esc closes popups."` → `"Welcome to Crownfall! Press H anytime for controls · Esc closes popups."`
- `server/server.py` ~1803: `"Your starting stats are set. Welcome to Mythoscape!"` → `"Your starting stats are set. Welcome to Crownfall!"`
- `client/client.py` ~8148: `"Mythoscape and the Castle Realm are separate maps."` → `"The Kingdom and the Castle Realm are separate maps."`
- `client/client.py` ~8152: the teleport group label `("Mythoscape", ...)` → `("The Kingdom", ...)`. Change the label string only.
- The King NPC name and lines are handled in Step 5. Knight Cedric's line is in Step 5 too.
- Leave docstrings and comments, such as those in `camera_yaw.py` and `fx_shadows.py`, unchanged.
Then grep the client, server and shared folders for `Mythoscape` and confirm that only comments, docstrings and module or path names remain.
Check: py_compile `server/server.py` and `client/client.py`.

## Step 2 — Crownfall title card at the end of the opening comic
In `client/opening_comic.py`, add one extra "title" page after the 7 comic pages:
- Add `TITLE_PAGE = len(LINES)` (index 7).
- In `advance()`: from the last comic page, go to `TITLE_PAGE` instead of finishing. Call `_stop()` and play no audio. Clicking on `TITLE_PAGE` calls `finish(client)`.
- In `draw()`: when `page == TITLE_PAGE`, blit the page 7 art (`_PAGES[-1]`) fitted to the full screen. Darken it with a translucent black overlay (alpha about 150). Draw `CROWNFALL` centred in a large serif-style font, in gold `(232, 196, 110)` with a 2px dark drop shadow. Use `pygame.font.SysFont("georgia,timesnewroman,serif", 96, bold=True)` and cache it in a module global. Underneath, draw `Your story begins...` in `client.font` using `(220, 205, 170)`. Keep the Skip button and a hint line that reads `Click or Space to begin`.
- Clamp page indexes to `TITLE_PAGE`, not `len(LINES) - 1`, wherever the title page needs to draw. The page counter text shows nothing on the title page.
- Esc and Skip still finish immediately, as they do now.
Check: py_compile `client/opening_comic.py`. Launch a new character and confirm pages 1 to 7, then the title card, then the game.

## Step 3 — Elowen's clan objective: 25 → 20 (the Royal Challenge)
- In `server/fairy_village.py` `oath_progress()`, both checks `members >= 25` → `members >= 20`, and the line `f"{members}/25 members"` → `f"Clan {members}/20 members"`.
- In `server/content.py` `QUESTS["fairy_oath"]["description"]`: `"Reach combat 100, own a castle, finish every other quest, and gather a clan of 25."` → `"The Royal Challenge: reach combat 100, own a castle, finish every other quest, and lead or join a clan of 20."`
- Leave `server/clans.py` as it is. Its `25` is the maximum clan size, not the oath requirement.
- Optional: in `tools/fairy_village_check.py`, change the preview strings `0/25` and `1/25` to `/20`.
Check: py_compile `server/fairy_village.py` and `server/content.py`.

## Step 4 — Rewrite Lady Elowen Moonwhisper (`elowen_moonwhisper`)
Edit `assets/fairy_village/dialogue/fairy_story.json` only. `open_talk()` shows `pages` on the first talk, when `fairy_oath` has no progress yet. Later talks show `repeat_pages.in_progress` or `repeat_pages.all_done`. Lines are plain strings with no speaker field, so write the player's replies as quoted lines starting with `You:`.

Replace the whole `"pages"` array with:
```json
[
  {"id": "meet", "lines": ["You're new.", "You: \"Is it that obvious?\"", "You still have money.", "You: \"What does that mean?\"", "Give it a week."]},
  {"id": "taxes", "lines": ["The King has raised the taxes again.", "You: \"Then why doesn't someone stop him?\"", "Someone tried.", "You: \"What happened?\"", "He became King."]},
  {"id": "glade", "lines": ["I am Elowen Moonwhisper. I keep the Moonwater, for as long as he lets me.", "His collectors came to the glade last spring. They measured the fountains."]},
  {"id": "law", "lines": ["There is an old law, older than his throne. He wrote none of it, so he cannot unwrite it.", "Anyone strong enough to take the King's Castle may claim the Crown.", "He doesn't fear the law. He's certain no one will ever be strong enough."]},
  {"id": "castle", "lines": ["(She turns toward the far-off towers of the King's Castle.)", "The King owns the land. The King owns the castles. The King owns the law.", "But there is one thing he does not own.", "You: \"What's that?\"", "Your destiny."]},
  {"id": "title", "lines": ["~  C R O W N F A L L  ~", "Your story begins..."]},
  {"id": "objectives_intro", "lines": ["The law calls it the Royal Challenge. Four things stand between you and it."]},
  {"id": "obj_combat", "lines": ["First, strength. Reach combat level 100.", "Armour first, then the levels. The dungeon beside our glade will test you."]},
  {"id": "obj_castle", "lines": ["Second, stone. Own a castle of your own.", "Quests fill the purse. Dungeons make you strong enough to spend it."]},
  {"id": "obj_quests", "lines": ["Third, a name people trust. Complete every quest in the realm.", "Each one is a promise kept. He keeps none."]},
  {"id": "obj_clan", "lines": ["Fourth, people who will stand with you.", "Lead or join a clan of at least twenty souls. One sword never took a throne."]},
  {"id": "farewell", "lines": ["When all four are done, come back to me. Not before.", "Drink from the Moonwater when you're weary. It will always know you."]}
]
```
Replace `"repeat_pages"` with the following. The `{objectives_status}` placeholder must stay.
```json
{
  "in_progress": ["Still here? Good. Most people leave once the money runs out.", "The King owns the land, the castles and the law. Not your destiny.", "The Royal Challenge: {objectives_status}"],
  "all_done": ["Strong, housed, trusted and followed. The old law can't refuse you now.", "Anyone strong enough to take the King's Castle may claim the Crown.", "Go and claim it. Then try not to become him."],
  "objectives_status_example": "Combat 64/100 · Castle 0/1 · Quests 9/14 · Clan 14/20 members"
}
```
In `"objectives"`, change the clan entry to `"id": "clan_20"`, `"text": "Lead or join a clan of at least 20 members."`, `"target": 20`, `"progress_format": "Clan {cur}/20 members"` and `"hook": "clans.member_count(...) >= 20"`. No code reads these fields, so this is documentation only. Set `"quest_title"` to `"The Royal Challenge"`, and change `QUESTS["fairy_oath"]["name"]` in `server/content.py` to `"The Royal Challenge"` too. The id stays `fairy_oath`.
In `comic_consistency`, change "old law: guild + castle to challenge the crown" to "old law: anyone strong enough to take the King's Castle may claim the Crown".
Existing saves already have `fairy_oath` active, so they'll see the new `in_progress` page, which carries the destiny line. That's intended. No migration.
Optionally, tweak `other_npcs` in the same file:
- warden_thorne page 2 → `["I've guarded this glade for three hundred winters.", "First they taxed the honey. Now they want the water."]`
- pip_dewdrop: add a page `["The tax man asked how much a wish weighs.", "Lady Elowen told him to go and weigh his own."]`
Check: json.tool `fairy_story.json`, py_compile `server/content.py`. Talk to Elowen once on a new character and once on an old one.

## Step 5 — Tax-flavour lines for overworld NPCs (`server/content.py` `NPCS`, `"lines"` lists only)
The full `lines` list is sent as dialogue. Keep every existing instructional or quest line, and **append** the new lines after them, unless the text below says replace. Change nothing else in any NPC dict.

- `farmer_tom`: append `"Used to sell wheat in the market. Now half of what I grow goes to the Crown."`, `"The collector counts my sacks better than I do."`
- `blacksmith_gareth`: append `"Knight orders keep coming. They want better swords."`, `"Meanwhile the people can't afford horseshoes."`
- `shopkeeper_joe`: append `"Prices went up again. Not mine. The Crown's cut."`, `"Every bridge has a toll, every road has a tax. My stock pays both before it reaches this shelf."`
- `merchant_wanderer`: replace with `["Bah, I've got nothing to sell you today. Come back later.", "Every bridge has a toll. Every road has a tax.", "By the time I get anywhere, my cart's lighter and the Crown's heavier."]`
- `guard_marcus`: append `"You think we enjoy collecting taxes? The King's army has to eat too."`
- `guard_aldric`: append `"I'm meant to note who leaves the village with full carts. It's never the villagers."`
- `jeweler_lira` (wealthy merchant): append `"The taxes are terrible. Fortunately, I can afford them."`, `"Gold always finds its way up the hill. I just make sure some of it stops here."`
- `innkeeper_sarah`: append `"Rooms are full of farmers who couldn't pay their land fees."`
- `elder_miriam`: append `"In my day the King visited the village. Now only his collectors do."`
- `priest_cedric`: append `"Even the collection plate is tithed now. The Crown takes a tenth of our charity."`
- `village_kid_timmy`: append `"My dad says the King has a room just for coins. Do you think he swims in it?"`
- `village_idiot_bob`: append `"I tried paying my tax in goblin teeth. They didn't laugh."`
- `old_fisherman_pete`: append `"They tax the lake now. Per fish. I've started throwing the small ones back out of spite."`
- `monk_healer`: append `"A kingdom is its people. Someone should remind the castle."`
- `fishmonger_kai`: append `"Harbour duty on every crate. The fish don't pay it, so I do."`
- `city_vendor_mira`: append `"Stonehaven prices are Stonehaven taxes, with bread on top."`
- `herald_rowan`: append `"By royal decree, the tax is fair. I'm paid to say that."`
- `mythos_knight_2` (Cedric): replace `"Hail Mythoscape."` with `"Hail the Crown."`

Leave unchanged: `wizard_elowen`, the fairy NPCs (handled in Step 4), shop and bank helpers whose lines are instructions (`packer_nell`, `fletcher_elena`, `banker_iris`, `banker_corin`, `outfitter_mae`, `pet_keeper_luna`, `tackle_merchant`, `harbour_cook`), `mia`, `mysterious_traveler`, `mad_scientist`, `mine_scout`, `dungeon_hermit` and `pass_scout`.
Check: py_compile `server/content.py`.

## Step 6 — The King (`id: "king"`, plane `king_f1`, `server/content.py` ~1688)
He should be greedy and smug, but not cartoonish. Change `"name": "The King of Mythoscape"` to `"name": "King of Crownfall"`. Replace `lines` with:
```
"You stand before the Crown. Do be brief, my time is taxed as well.",
"Taxes? A kingdom is expensive. Someone must pay for it, and it certainly won't be me.",
"The old law? Anyone strong enough may take my castle. Look around you. No one is.",
"Kneel, or leave. Either way, the toll on the bridge home is the same."
```
The id stays `king`, and it gets no new behaviour.
Check: py_compile `server/content.py`.

## Step 7 — Final check
- py_compile every touched `.py` file, and run json.tool on `fairy_story.json`.
- Run `tools/fairy_village_check.py` if it runs headless. Otherwise skip it.
- Start the server and client. New character: comic, title card, Elowen's full pages, and the objectives show `/20`. Old character: Elowen shows the in-progress page, and the farmer, guard, Lira and the King show their new lines.
- Leave the changes uncommitted for David to review.

## Out of scope (do not do)
- Renaming folders, modules, the DB, the repo, the `Mythos` items, Mythos Knights or Mythos Outfitters.
- Tax, land fee, reputation, guild, apprenticeship or property systems. These come in later phases.
