"""Save migrations for item ids that no longer exist.

Daggers were removed; every dagger becomes the sword of the same tier,
keeping quantity and slot. Pure functions so they can be tested without a DB.
"""

DAGGER_TO_SWORD = {
    "bronze_dagger": "bronze_sword",
    "iron_dagger": "iron_sword",
    "steel_dagger": "steel_longsword",
    "mithril_dagger": "mithril_sword",
    "adamant_dagger": "adamant_sword",
    "mythos_dagger": "mythos_longsword",
}


def migrate_daggers(inventory, bank, equipment):
    """Rewrite dagger ids in place. Idempotent.

    Returns (inv_slots, bank_slots, equip_slots) that changed.
    """
    inv_changed, bank_changed, eq_changed = [], [], []
    for store, changed in ((inventory, inv_changed), (bank, bank_changed)):
        for slot, entry in (store or {}).items():
            new = DAGGER_TO_SWORD.get((entry or {}).get("item_id"))
            if new:
                entry["item_id"] = new
                changed.append(slot)
    for slot, item_id in list((equipment or {}).items()):
        new = DAGGER_TO_SWORD.get(item_id)
        if new:
            equipment[slot] = new
            eq_changed.append(slot)
    return inv_changed, bank_changed, eq_changed
