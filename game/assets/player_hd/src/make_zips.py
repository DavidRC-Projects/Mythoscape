import zipfile, os, glob
os.chdir("/workspace")
for z in glob.glob("player_hd_part*.zip"):
    os.remove(z)
parts = {
 "player_hd_part1_docs_meta_previews_src.zip": ["player_hd/NOTES_PLAYER_HD.md", "player_hd/PLAYER_HD_CURSOR_PROMPT.md", "player_hd/assets/meta.json",
                                                "player_hd/assets/catalogue.json", "player_hd/assets/anchors.json", "player_hd/previews", "player_hd/src"],
 "player_hd_part2_male_2x_4x.zip": ["player_hd/assets/male/2x", "player_hd/assets/male/4x"],
 "player_hd_part3_male_1x.zip": ["player_hd/assets/male/1x"],
 "player_hd_part4_female_2x_4x.zip": ["player_hd/assets/female/2x", "player_hd/assets/female/4x"],
 "player_hd_part5_female_1x.zip": ["player_hd/assets/female/1x"],
}
for z, srcs in parts.items():
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in srcs:
            if os.path.isfile(s):
                zf.write(s); continue
            for root, ds, fs in os.walk(s):
                if "__pycache__" in root:
                    continue
                for f in fs:
                    zf.write(os.path.join(root, f))
    mb = os.path.getsize(z) / 1e6
    print(z, round(mb, 2), "MB", "OVER 15MB!" if mb > 15 else "")
