"""
Shared network protocol constants.

Every message sent over the websocket is a single JSON object:
    {"type": "<MESSAGE_TYPE>", ...fields}

Client -> Server message types
-------------------------------
LOGIN            {username, password}
CREATE_CHARACTER {username, password, char_name, gender?}  -- gender: male | female
ALLOCATE_STATS   {stats: {attack, strength, defence, hitpoints}}  -- sum must be 10; new chars only
LEADERBOARD      {limit?}                 -- works before login; top players per skill
MOVE             {dx, dy}                 -- one tile step, server validates
CHAT             {text}
ATTACK           {target_id}              -- target_id is a monster instance id
SET_COMBAT_STYLE {style}                  -- attack | strength | defence | hitpoints | archery
                                              -- archery only while a bow is equipped; bow locks melee styles
CAST_MAGIC       {ability_id}             -- quest-magic ability; requires combat target (manual = shorter CD)
SET_MAGIC_MODE   {auto: bool}             -- auto cast in combat vs manual fight buttons
GATHER           {x, y}                   -- coordinates of the resource node
CRAFT            {recipe_id, qty?}        -- smelt/smith/cook/fletch; qty multiplies cook/fletch batches
TALK             {npc_id}
SET_PET          {pet_id}                 -- switch active companion (must own it)
SHOP_BUY         {shop_id, item_id, qty}
SHOP_SELL        {shop_id, item_id, qty}
EQUIP            {slot_index}
UNEQUIP          {equip_slot}
DROP             {slot_index, qty}        -- drop qty from that inventory stack
INV_MOVE         {from_slot, to_slot}     -- rearrange inventory (swap / merge stacks)
USE_ITEM         {slot_index, action?}    -- use / pack / eat from bags
QUICK_CONSUME    {kind}                   -- combat quick-use: food | health | attack | strength | defence
TRADE_REQUEST    {target_player_id}
TRADE_RESPOND    {accept: bool}
TRADE_OFFER      {items: [{slot_index, qty}]}
TRADE_CONFIRM    {}
TRADE_CANCEL     {}
PICKUP           {}
SET_OPTION       {auto_pickup_items?}
BANK_OPEN        {}
BANK_DEPOSIT     {slot_index?} | {coins?}
BANK_WITHDRAW    {slot_index?, qty?} | {coins?}
QUEST_ACCEPT     {quest_id}
QUEST_TURNIN     {quest_id}
ENTER_DUNGEON    {}                        -- enter Tidehollow Cave (must be at mouth)
LEAVE_DUNGEON    {}                        -- abandon current Tidehollow run
WISH             {kind}                   -- power | gear | gold  (at wishing well)
WISH_STAT        {skill}                  -- permanent +1 after rare power wish
LOGOUT           {}

Server -> Client message types
-------------------------------
LOGIN_OK          {player}
LOGIN_FAIL        {reason}
LEADERBOARD       {skills, boards}        -- boards[skill|total] = [{name, xp, level}, ...]
                                              -- total.level = sum of skill levels; total.xp = sum XP
WORLD_STATE       {tiles, width, height, npcs, resources, interactables, buildings, craft_recipes}
STATE_UPDATE      {players, monsters, resources, fires, dungeon?}  -- sent every tick
PLAYER_UPDATE     {player}                                  -- your own full state (inventory/stats changed)
CHAT_MSG          {from, text, style?}                      -- style "gold" = Tidehollow announcement
DUNGEON_ENTER     {id, floor, floors, label, tiles, width, height, monsters, remaining, player_x, player_y}
DUNGEON_FLOOR     {…same as DUNGEON_ENTER…}                 -- advanced to next Tidehollow floor
DUNGEON_EXIT      {x, y}                                    -- returned to overworld
DUNGEON_COMPLETE  {rewards:[{item_id, qty}]}                -- cleared all 10 floors
COMBAT_EVENT      {attacker_id, defender_id, damage, hit, defender_hp, defender_max_hp, kind, ranged?, magic_effect?}
MAGIC_CAST        {caster_id, target_id, ability_id, name, effect, damage, freeze, manual, defender_hp, defender_max_hp}
DEATH             {entity_id, entity_kind}
LOOT_DROPPED      {x, y, items}                             -- overworld ground loot
SKILL_XP          {player_id, skill, gained, xp, level, leveled_up}
DIALOGUE          {npc_id, npc_name, lines, shop_id, quest, forge?, bank?}
SHOP_STATE        {shop_id, name, stock, your_coins}
BANK_STATE        {inventory, bank, coins, bank_coins, max_purse, max_bank_coins, bank_slots}
TRADE_REQUEST_IN  {from_player_id, from_name}
TRADE_STATE       {other_name, your_offer, other_offer, your_confirmed, other_confirmed}
TRADE_DONE        {}
TRADE_CANCELLED   {reason}
QUEST_LOG         {quests}
QUEST_COMPLETE    {quest_id, rewards, quest_points?, total_quest_points?}
ERROR             {message}
"""

TICK_SECONDS = 0.6  # one "game tick", matches classic RuneScape's 0.6s tick
