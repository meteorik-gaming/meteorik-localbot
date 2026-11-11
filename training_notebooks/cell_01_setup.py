# CELL 1 -- setup. Runtime > Change runtime type > GPU (L4 for generation) BEFORE running.
import pathlib
import subprocess
import sys

from google.colab import drive

drive.mount("/content/drive")

BASE = pathlib.Path("/content/drive/MyDrive/localbot-training")
for d in ["adapters", "approved", "drafts", "scores", "seeds", "tests"]:
    (BASE / d).mkdir(exist_ok=True)

PROJECT = BASE / "seeds" / "project"   # uploaded with make_bundle.py
assert (PROJECT / "data" / "header_spec.json").exists(), (
    "Upload training_notebooks/_upload/project to Drive: localbot-training/seeds/project")
sys.path.insert(0, str(PROJECT / "tools" / "training"))
import header_v2 as h   # the same band rules the game uses

try:
    print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"],
                         capture_output=True, text=True).stdout)
except FileNotFoundError:
    print("No GPU on this runtime (fine for reviewing: cells 1, 3, 5b, 6, 8 do not need one)")
print("band check:", h.band("bond", 70), h.heat_band(30, 5.0), h.time_band(23.5))
