import utils
import json
import os

print("Memulai sensor ulang seluruh komentar...")

matches = utils.load_matches()
updated_count = 0

for m in matches:
    if "comments" in m:
        for c in m["comments"]:
            old_comment = c["comment"]
            old_name = c["name"]
            
            c["comment"] = utils.censor_text(old_comment)
            c["name"] = utils.censor_text(old_name)
            
            if old_comment != c["comment"] or old_name != c["name"]:
                updated_count += 1

if updated_count > 0:
    utils.save_matches(matches)
    print(f"Selesai! Berhasil mensensor ulang {updated_count} komentar/nama yang berisi kata-kata kasar.")
else:
    print("Selesai! Tidak ada komentar lama yang perlu disensor.")
