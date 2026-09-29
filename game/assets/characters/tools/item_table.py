import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from render_common import ITEMS
import gear_v2 as G
DESC = {
 "sword": "Short straight blade (12.6u), point, grip + pommel",
 "longsword": "Long blade (15.6u) with dark fuller, longer grip",
 "dagger": "Stubby 7.4u blade, narrow, short guard",
 "battleaxe": "Long haft (17u) + double-bit crescent head",
 "axe": "Short haft + single bit, back poll (woodcutting tool look)",
 "pickaxe": "Short haft + curved two-point pick head",
 "cleaver": "Broad obsidian slab blade, gold edge, gold eclipse disc, gold guard",
 "bow": "D-profile shortbow, leather grip, string (nocked arrow while drawing)",
 "platebody": "Bulky plate (armour_v2): broad breastplate with keel + abdomen lames, 3-lame layered pauldrons (size by tier), rerebrace, couter, vambrace, gauntlets, edge trim + rivets",
 "chainbody": "Mail shirt (0.7 bulk): staggered ring dots, mail mantle over shoulders, trim hem band, leather bracers",
 "leather_body": "Leather jerkin (0.4 bulk): stitched seams, strap, studs, shoulder caps, bracers",
 "goblin_mail": "Rusty patched mail: mismatched rust + dark plates, stray rivets",
 "platelegs": "Two-row faulds skirt, tassets following the thighs, cuisses, fan-winged knee cops, greaves, segmented sabatons",
 "chainlegs": "Mail leggings (widened): ring rows, mail knee cops",
 "chaps": "Leather chaps: front seam, darker inner panel, knee pads",
 "med_helm": "Open med helm (see tier detail)",
 "cowl": "Leather hood wrapping the head, open face",
 "dragon_helm": "Dragon helm: crimson, big gold swept horns, red fin spines, gold chevron visor, gold cheek wings, glowing ruby eyes; runes on the back",
 "grill_helm": "Black great helm: gold wings, 7-ray gold sun crown, gold face grill, glowing amber brow gem; eclipse emblem on the back",
 "kiteshield": "Kite shape, light centre stripe (steel+: cross bar; adamant: gold stripe); Mythos: gold dragon emblem, double gold filigree, gem inlays",
 "sq_shield": "Square shield, corner rivets, central boss, two-tone halves",
 "round_wood": "Round planked wooden shield, iron rim, iron boss",
 "aegis": "Round black aegis, double gold filigree rim, large eclipse emblem (sun + crescent), gem inlays",
}
TIER = {
 "bronze": "plain guard; open cap + nasal + mail aventail; dull trim, few rivets", "iron": "square guard; kettle-brim helm + aventail; dark trim, rivet rows",
 "steel": "angled guard; snouted bascinet with visor slit + breath holes; bright trim", "mithril": "upswept guard; sallet with tail + ridge crest; silver trim",
 "adamant": "winged guard; flat-top great helm, cross visor, comb + red plume; brass trim", "mythos": "DRAGON SET: gold filigree on every plate edge, gold winged dragon-head chest emblem with ruby eyes, gold-horned pauldrons, runes, ruby gems, glow, crimson cape with emblem, rune-etched blades",
 "eclipse": "gold filigree on every plate edge, large eclipse chest emblem (sun + crescent + amber gem), sun-spiked pauldrons, runes, gems, glow, cape with emblem, rune-etched blades",
}
rows = ["| Item id | Name | Slot | Kind (silhouette) | Material / tier | Design |", "|---|---|---|---|---|---|"]
n = 0
for iid, it in ITEMS.items():
    if it.get("equip_slot") not in ("weapon", "body", "legs", "helmet", "shield"):
        continue
    L = G.look_for(iid)
    d = DESC[L["kind"]]
    extra = TIER.get(L["mat"], {"oak": "oak-brown limbs", "willow": "pale willow limbs", "maple": "orange maple limbs + light inlays",
                                 "yew": "dark yew limbs + light inlays", "magic": "teal limbs, glowing string + runes", "wood": "plain wood",
                                 "leather": "brown leather", "goblin": "olive/rust"}.get(L["mat"], ""))
    rows.append(f"| `{iid}` | {it['name']} | {it['equip_slot']} | {L['kind']} | {L['mat']} (t{L['tier']}) | {d}; {extra} |")
    n += 1
rows2 = ["", "### Ammo / jewellery icons", "", "| Item id | Name | Slot | Icon |", "|---|---|---|---|"]
for iid, it in ITEMS.items():
    if it.get("equip_slot") in ("ammo", "amulet", "ring"):
        rows2.append(f"| `{iid}` | {it['name']} | {it['equip_slot']} | " + (
            "leather quiver with fletchings" if iid == "arrow_quiver" else
            "three arrows, tip in material colour" if it['equip_slot'] == "ammo" else
            f"gold {'band' if it['equip_slot']=='ring' else 'chain + pendant'} with gem {it.get('gem_color')}") + " |")
open(sys.argv[1], "w").write(f"# Item looks — {n} armour/weapon items (every one unique = kind x material x tier detail)\n\n"
    "Palette: muted OSRS-like materials (gear_v2.MATS). Worn look + icon come from the same look entry.\n\n" + "\n".join(rows + rows2) + "\n")
print(n)
