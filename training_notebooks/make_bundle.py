"""Run locally (python training_notebooks/make_bundle.py).

Copies the two files Colab needs into training_notebooks/_upload/project/, keeping the
folder layout header_v2.py expects (it finds data/header_spec.json three levels up).
Upload the whole `project` folder to Drive: My Drive/localbot-training/seeds/project/
Re-run and re-upload whenever data/header_spec.json changes.
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(__file__).resolve().parent / "_upload" / "project"
FILES = ["data/header_spec.json", "tools/training/header_v2.py"]

for rel in FILES:
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / rel, dst)
    print("copied", rel)
print("\nUpload:", OUT, "->  Drive: localbot-training/seeds/project/")
