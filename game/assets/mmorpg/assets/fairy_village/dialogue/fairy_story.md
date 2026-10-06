# The Moonwater Oath: Lady Elowen Moonwhisper

Story fairy of the Fairy Village (Moonpetal Glade). Talking to her opens these pages in order; each page is 2-3 lines.

**intro**

> Hush, traveller. You walk on moss that remembers the old kings.
> I am Elowen Moonwhisper, keeper of the Moonwater.
> Stay a moment. I have waited a long time for someone like you.

**king_1**

> The king does not rule this land. He eats it.
> Every harvest is taxed. Every forest is felled for his halls.
> Every coin from the deep dungeons ends in his castle vaults.

**king_2**

> The fields to the north grow thinner every year.
> And now his tax-collectors have come to our glade.

**moonwater_1**

> Our fountains hold the Moonwater, the last pure magic in the realm.
> It heals the soil. It keeps the forests green.

**moonwater_2**

> The king wants it drained and sealed in barrels for his crown.
> If the fountains run dry, the glade dies, and the land soon after.

**plea**

> We are small folk. Our wings were not made for war.
> But you... you were. Will you stand with us?

**law_1**

> There is an old law, older than his throne.
> Any who hold a castle and lead a true guild may challenge the crown.

**law_2**

> He fears that law. That is why he keeps the strong ones poor.
> So we must make you strong, rich and loved. In that order.

**objectives_intro**

> Four tasks stand between you and the king.
> Complete them all, and you will be ready for war.

**obj_combat**

> First, your strength. Reach combat level 100.
> Armour first, then the levels. The dungeon beside our glade will test you.

**obj_castle**

> Second, a home of stone. Buy a castle of your own.
> Quests fill the purse. Dungeons make you strong enough to spend it.

**obj_quests**

> Third, a name the people trust. Complete every quest in the realm.
> Each one is a promise kept, and the king keeps none.

**obj_clan**

> Fourth, the people who will stand with you.
> Lead or join a clan of at least twenty-five souls.

**farewell**

> When the clan is ready, the war begins. Not before.
> Drink from the Moonwater when you are weary. It will always know you.
> Go gently, champion. The glade is counting on you.

## Objectives (quest `fairy_oath`)

| id | title | requirement | progress shown | data hook |
|---|---|---|---|---|
| `combat_100` | Strength of a Champion | Reach combat level 100. | Combat {cur}/100 | PlayerSession.combat_level() >= 100 |
| `buy_castle` | A Home of Stone | Buy a castle of your own. | Castles owned {cur}/1 | castle_owners.owners(conn): any row with owner_id == session.player_id |
| `all_quests` | A Name the People Trust | Complete every quest in the realm. | Quests {cur}/{total} | sum(quest_status_for(session, q)['status'] == 'complete' for q in QUESTS) == len(QUESTS) (excluding fairy_oath itself) |
| `clan_25` | Those Who Stand With You | Lead or join a clan of at least 25 members. | {cur}/25 members | clans.member_count(clans.clan_of(session.player_id)) >= 25 (new minimal clan system) |

Example status line: Combat 64/100 · Castle 0/1 · Quests 9/14 · Clan 14/25 members

## Repeat talk

In progress:

> The Moonwater still flows, thanks to you.
> Your tasks: {objectives_status}

All done:

> You are strong, housed, trusted and followed.
> The old law is on your side now, champion.
> Go and take his crown. The glade will sing your name.

## Other villagers

**Warden Thorne Briarwing** (`warden_thorne`)

> Halt. Oh... a friend of the Lady? Then pass, and welcome.
> Mind the crypt to the south-east. The dead sleep badly there.

> I've guarded this glade for three hundred winters.
> I have never seen the king's men this bold.

**Tumbleroot the Gnome** (`tumbleroot`)

> Potions! Tonics! Moonwater draughts, nearly legal!
> Have a look, have a look. Mind the green one, it bites.

**Pip Dewdrop** (`pip_dewdrop`)

> Shh! The lilies are sleeping.
> Lady Elowen says the fountain sings if you're kind to it.

> Are you the hero? You look a bit muddy for a hero.
> That's alright. Heroes get muddy.

## Consistency with the comic

- The king strips the land ("He does not rule this land. He eats it" is reused verbatim).
- Dungeon gold flows to his castle ("Every coin from the deep dungeons ends in his castle vaults").
- Old law: castle + guild to challenge the crown (page `law_1`).
- "Armour first, then the levels", "Quests fill the purse. Dungeons make you strong enough to spend it", and "When the clan is ready, the war begins" echo the comic narrator.
