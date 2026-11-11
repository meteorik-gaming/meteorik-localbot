# CELL 5b -- come back to a finished batch WITHOUT a GPU (to validate / review / read your ratings).
# Use a CPU runtime (Runtime > Change runtime type > CPU): it burns almost no compute units.
# Order after reconnecting:  0  ->  1  ->  3  ->  5b (this one)  ->  6  ->  (7 for a new review file)  ->  8
# Set BATCH to the batch you generated in cell 5. Cells 2, 4 and 5 are NOT needed.
DRAFTS = BASE / "drafts" / f"{BATCH}_{LANG}.jsonl"
assert DRAFTS.exists(), f"No drafts found at {DRAFTS}"
print("batch", BATCH, "->", DRAFTS.name, sum(1 for _ in open(DRAFTS, encoding="utf-8")), "rows")
