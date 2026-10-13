# Crownfall — Phase 2: Taxes and land fees (royal treasury)

Work directly on `main`. Do each step in turn, run the check after it, and keep every change small. Do not rewrite existing functions; add to them.
Paths are relative to `game/assets/mmorpg/` unless stated.

## Step 0 — Before you start
1. Run `git status`. If there are uncommitted changes (Phase 1 may have left some in `server/content.py`, `server/server.py`, `server/world_map.py`, `tools/`), stop and ask David whether to commit them first. Do not stash, reset or discard anything.
2. Read these first, and adapt to the real line numbers:
   - `server/server.py`: `handle_shop_buy` (~4173), `handle_shop_sell` (~4229), `send_shop_state` (~3985), the game loop (~5553, where `tick_leases` and `tick_taxes` run every 500 ticks), `WORLD.add_coins`, `MAX_PURSE_COINS`.
   - `server/housing.py`: `housing_deeds` schema, `settle_lease`, `tick_leases` (weekly lease of 50,000 already exists).
   - `server/castle_owners.py`: `settle_taxes` / `tick_taxes` (weekly castle upkeep already exists).
   - `server/database.py`: schema and `save_player_stats`.
   - The client shop UI in `client/` (search for `SHOP_STATE`).

## Rules
- No new feature flags. Existing flags (`USE_PLAYER_HOUSING`, `USE_CASTLE_OWNERS`) stay as they are; code that depends on them just respects them.
- Never touch the walk cycle: `pose_walk`, `rs_style.py`, `rs_humanoid*.py`, `tools/walk_proof.py`, `draw_humanoid*`. Do not touch movement, camera or combat.
- Taxes never take a player below 0 gold in purse or bank. If a player can't pay a land fee, record nothing as debt and take nothing. The existing lease grace system handles non-payment of the lease itself.
- Losing a castle never costs gold. Don't add any gold loss to castle loss code.
- All rates live in ONE place: a new `server/royal_treasury.py` module (constants at the top). A later phase lets the player-king change them, so read them through functions, not by copying numbers around.
- Works for new and existing saves: use `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN` guarded by a column check. No destructive migrations.
- After every step, run `python -m py_compile` on each `.py` file you touched.

## Tax numbers (use exactly these)
| Tax | Rate | Notes |
|---|---|---|
| Shop sales tax on buying | 5% of the cost, rounded up, minimum 1 coin when cost > 0 | Added on top of the price. Pets bought from the bank also pay it. Re-calling an owned pet (cost 0) pays nothing. |
| Shop sales tax on selling | 5% of the sale value, rounded down | Taken from the coins the shop pays out. A value of 0 pays 0. |
| Daily land fee (player houses) | 500 coins per house per real day | Paid from bank first, then purse. If the player has less than 500 in total, they pay nothing that day (never partial, never negative). |
| Existing weekly house lease (50,000) | unchanged | Now also credited to the treasury. |
| Existing weekly castle upkeep | unchanged | Now also credited to the treasury. King's Castle stays lease-free. |

## Step 1 — `server/royal_treasury.py` (new)
- Constants: `SALES_TAX_RATE = 0.05`, `LAND_FEE_DAILY = 500`, `DAY_SECONDS = 86400`.
- `ensure_schema(conn)` creates:
  - `royal_treasury (id INTEGER PRIMARY KEY CHECK (id = 1), balance INTEGER NOT NULL DEFAULT 0, updated_at REAL)` with one row inserted if missing.
  - `treasury_ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, source TEXT, player_id INTEGER, amount INTEGER)`. `source` is one of `sales_tax_buy`, `sales_tax_sell`, `land_fee`, `house_lease`, `castle_upkeep`.
- Functions: `sales_tax_rate()`, `land_fee_daily()`, `buy_tax(cost)` (ceil, min 1 when cost>0), `sell_tax(value)` (floor), `credit(conn, source, player_id, amount)` (ignore amount <= 0, update the balance and add a ledger row in one transaction), `balance(conn)`.
- Call `ensure_schema` wherever the other modules call theirs at startup.
- Check: py_compile; start the server once and confirm both tables exist.

## Step 2 — Sales tax in `handle_shop_buy` / `handle_shop_sell`
- Buy (normal items): `tax = buy_tax(cost)`; require `session.coins >= cost + tax`; take `cost + tax`. On the inventory-full rollback, refund both. Credit the treasury only after the item has been added.
- Buy (pets): the same, with purse + bank covering `cost + tax`.
- Sell: `tax = sell_tax(value)`; pay `value - tax` through `WORLD.add_coins`; credit `tax`.
- `send_shop_state` adds `"tax_rate": sales_tax_rate()` to its payload.
- First-time notice: add a `tax_notice_seen` INTEGER DEFAULT 0 column to `players` (guarded ALTER), loaded on the session. The first time a tax over 0 is paid, send CHAT_MSG from `"Royal Tax Collector"`: `"By decree of the King of Crownfall, 5% of every shop sale goes to the royal treasury."` Then set the flag and save it.
- Check: py_compile.

## Step 3 — Shop UI shows the tax
- In the client shop panel, next to each buy price show the total including tax, for example `100 gp (+5 tax)`. Show the tax on sell offers as well, for example `40 gp (−2 tax)`.
- Add one footer line: `Royal sales tax: 5%`, using `tax_rate` from SHOP_STATE.
- Reuse the existing font and colours. No layout rewrite.
- Check: py_compile; open a shop and take a screenshot to confirm the text fits.

## Step 4 — Daily land fee for houses (real-time daily tick)
- Add a guarded `land_fee_paid_through REAL` column to `housing_deeds`. When it's NULL, set it to the current time (don't charge back-pay).
- In `housing.py` add `settle_land_fee(session, quiet=False)`: for each house the player owns, work out the whole days that have passed since `land_fee_paid_through`, capped at 7 so long absences don't drain them. For each day, charge `LAND_FEE_DAILY` from bank then purse only if they can cover the full fee, then credit `land_fee`. Move `paid_through` forward one day for every day that passed, whether or not it was paid, so unpaid days are forgiven and never become debt.
- Message (not quiet): `"The King's land fee of 500 coins for {house} is paid."` If nothing could be paid: `"You couldn't cover the King's land fee for {house} today. No debt is kept."`
- Call it from `settle_lease` callers on login and inside `tick_leases`, so it runs on the same 500-tick cadence. The real-time maths makes it daily.
- Credit the treasury in `settle_lease` (`house_lease`) and `castle_owners.settle_taxes` (`castle_upkeep`) where coins are taken now. Add one line each and change nothing else.
- Update the housing office dialogue (~housing.py:139) to add: `"The King also takes a land fee of 500 gold a day."`
- Check: py_compile.

## Step 5 — Tests
Add `tools/test_taxes.py` (pure functions plus an in-memory sqlite):
1. `buy_tax(100)==5`, `buy_tax(1)==1`, `buy_tax(0)==0`, `sell_tax(39)==1`, `sell_tax(0)==0`.
2. `credit` adds to the balance and writes a ledger row; `credit(…, 0)` and negative amounts change nothing.
3. Land fee: a player with 499 total coins pays 0, nothing goes negative, and `paid_through` moves forward. A player with 10,000 coins after 3 days pays 1,500 and the treasury gains 1,500. After 30 days offline they pay at most 3,500.
4. Buy with exactly `cost` coins (no room for tax) is refused, and no coins are taken.
5. Run the existing tests (`server/test_castle_realm.py` and anything in `tools/test_*.py`) and confirm nothing new fails.

## Verification checklist
- [ ] `git status` was checked first, and no unrelated files were changed.
- [ ] Walk cycle files are untouched (`git diff --stat` shows none of them).
- [ ] Buying a 100 gp item costs 105 and the treasury goes up by 5.
- [ ] Selling shows the tax and pays the net amount.
- [ ] The tax notice appears once per character only.
- [ ] Shop UI shows the tax per line plus the footer.
- [ ] A house owner is charged 500 per real day; it is never partial and never below 0.
- [ ] Lease and castle upkeep now reach the treasury; their amounts are unchanged.
- [ ] Losing a castle still costs no gold.
- [ ] `royal_treasury.balance` survives a server restart.
- [ ] No new feature flags; `tools/test_taxes.py` passes.
- Commit: `Crownfall phase 2: royal taxes, land fee, treasury`.
