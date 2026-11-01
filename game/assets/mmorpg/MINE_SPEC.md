# Deepdelve Mine - v2 (three levels)

| Level | Where | Ores | Way in | Way out |
|---|---|---|---|---|
| Ground Level | volcano yard + B0 chamber | copper..runite (lower ores) | yard path | yard |
| Level 2 - Silver Dark | chamber 2 | Mithril (Mining 40) | tunnel mouth at the top of the yard (65-69,105) or the B0 ramp (65-69,106) | ladder up -> Ground |
| Level 3 - The Green Deep | chamber 3 | Adamantite (Mining 46) | ladder/shaft at (67,130) on Level 2 | ladder up -> Level 2 |

- Floor gates unchanged: first descent runs the gauntlet; once a floor is unlocked you go straight down.
- Golems ~247, Ancient Golem 271, Colossus 337 stay as before.
- No mithril/adamantite on Ground Level; stray old-pocket tiles walled. Player inventories untouched.
- Client: each level is masked to its own chamber, darker ambience, cold crystal light, 0.7 s fade with level title, signposts at (63,103), (65,110), (65,129).
- Layout lives in server/deepdelve_layout.py (shared by client). Tests: tools/test_mine.py.
