# CELL 5a (optional) -- run AFTER cell 3 and BEFORE cell 5 to make a batch of rare specials only.
# Then in cell 0 set BATCH = "spec4" (new name) and N = 300. For a normal batch, skip this cell (or re-run cell 3 to restore weights).
# spec4 weights follow the first training test: distress (11 in train) and honesty_sincere (6) came out weak, nick and unsend are thin too.
# 300 chats -> ~105 distress + ~90 sincere; about half survive rating and the merge re-check -> ~50 each.
# v3 names; priorities from the openers v3 handoff: sos / sad / dog first, then real / nick.
SPECIALS = [
    ("sos", 24), ("sad", 24), ("dog", 20), ("real", 20), ("nick", 12),
    ("spicy", 5), ("push", 4), ("chat", 3),
]
print("rare-specials weights set:", SPECIALS)
