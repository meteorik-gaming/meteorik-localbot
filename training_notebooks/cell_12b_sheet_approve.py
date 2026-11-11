# CELL 12b -- run AFTER cell 6 on a sheet batch (cell 12). The sheet text is already human-reviewed, so cells 7 and 8 are skipped:
# every row that passed cell 6 is marked approved. Writes approved/<BATCH>_<LANG>_reviewed.jsonl, the file cell 9 reads.
# Then add the batch name to MERGE_BATCHES in cell 0 (keep your older batches in the list) and run cell 9.
import json
src = BASE / "approved" / f"{BATCH}_{LANG}.jsonl"
assert src.exists(), f"{src.name} missing: run cell 6 for {BATCH} first"
ok_rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
out = [{**r, "review": "approved", "human_rating": 5} for r in ok_rows]
(BASE / "approved" / f"{BATCH}_{LANG}_reviewed.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out), encoding="utf-8")
print(f"{len(out)} sheet rows approved -> approved/{BATCH}_{LANG}_reviewed.jsonl. Add \"{BATCH}\" to MERGE_BATCHES, then cell 9.")
