"""
Shared network protocol constants.

Every message sent over the websocket is a single JSON object:
    {"type": "<MESSAGE_TYPE>", ...fields}

Client -> Server message types
-------------------------------
LOGIN            {username, password}
CREATE_CHARACTER {username, password, char_name}
LEADERBOARD      {limit?}                 -- works before login; top players per skill
MOVE             {dx, dy}                 -- one tile step, server validates
CHAT             {text}
ATTACK           {target_id}              -- target_id is a monster instance id
SET_COMBAT_STYLE {style}                  -- attack | strength | defence | hitpoints
GATHER           {x, y}                   -- coordinates of the resource node
CRAFT            {recipe_id}              -- smelt/smith at the village forge
TALK             {npc_id}
SHOP_BUY         {shop_id, item_id, qty}
SHOP_SELL        {shop_id, item_id, qty}
EQUIP            {slot_index}
UNEQUIP          {equip_slot}
DROP             {slot_index, qty}
USE_ITEM         {slot_index}
TRADE_REQUEST    {target_player_id}
TRADE_RESPOND    {accept: bool}
TRADE_OFFER      {items: [{slot_index, qty}]}
TRADE_CONFIRM    {}
TRADE_CANCEL     {}
QUEST_ACCEPT     {quest_id}
QUEST_TURNIN     {quest_id}
LOGOUT           {}

Server -> Client message types
-------------------------------
LOGIN_OK          {player}
LOGIN_FAIL        {reason}
LEADERBOARD       {skills, boards}        -- boards[skill] = [{name, xp, level}, ...]
WORLD_STATE       {tiles, width, height, npcs, resources}   -- sent once after login
STATE_UPDATE      {players, monsters, resources}            -- sent every tick
PLAYER_UPDATE     {player}                                  -- your own full state (inventory/stats changed)
CHAT_MSG          {from, text}
COMBAT_EVENT      {attacker_id, defender_id, damage, hit, defender_hp, defender_max_hp, kind}
DEATH             {entity_id, entity_kind}
LOOT_DROPPED      {x, y, items}
SKILL_XP          {player_id, skill, gained, xp, level, leveled_up}
DIALOGUE          {npc_id, npc_name, lines, shop_id, quest_id}
SHOP_STATE        {shop_id, name, stock, your_coins}
TRADE_REQUEST_IN  {from_player_id, from_name}
TRADE_STATE       {other_name, your_offer, other_offer, your_confirmed, other_confirmed}
TRADE_DONE        {}
TRADE_CANCELLED   {reason}
QUEST_LOG         {quests}
QUEST_COMPLETE    {quest_id, rewards}
ERROR             {message}
"""

TICK_SECONDS = 0.6  # one "game tick", matches classic RuneScape's 0.6s tick
