# CELL 0 -- download the models ONCE into Drive, on a CPU runtime (no GPU units burned).
# Run cell 1 first (needs BASE). Runtime > Change runtime type > CPU is enough.
# Saves in Drive models/:   ollama/  = the teacher (qwen3:14b, ~9 GB)
#                           hf/      = the 3 training bases (1.7B ~4 GB, 4B ~8 GB, 8B ~16 GB)
# Total ~37 GB: check your Drive space first (printed below). Already-downloaded things are skipped.
import os
import shutil
import subprocess
import time

import requests

TEACHER_MODEL = "qwen3:14b"
BASES = ["Qwen/Qwen3-1.7B", "Qwen/Qwen3-4B-Instruct-2507", "Qwen/Qwen3-8B"]
MODELS = BASE / "models"
(MODELS / "ollama").mkdir(parents=True, exist_ok=True)
(MODELS / "hf").mkdir(parents=True, exist_ok=True)

total, used, free = shutil.disk_usage(str(BASE))
print(f"Drive: {free / 1e9:.0f} GB free of {total / 1e9:.0f} GB (need ~37 GB)")

# 1) the teacher: pull on the local disk, then copy to Drive (Drive is slow for many writes)
LOCAL = "/content/ollama_models"
os.environ["OLLAMA_MODELS"] = LOCAL
def teacher_in_drive():
    blobs = (MODELS / "ollama" / "blobs")
    return blobs.exists() and any(f.stat().st_size > 1e9 for f in blobs.iterdir())     # the weights blob is ~9 GB


if not teacher_in_drive():
    subprocess.run("apt-get -qq install -y zstd", shell=True)
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    srv = subprocess.Popen(["ollama", "serve"], env=os.environ,
                           stdout=open("/content/ollama.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            requests.get("http://127.0.0.1:11434", timeout=1)
            break
        except Exception:
            time.sleep(1)
    subprocess.run(["ollama", "pull", TEACHER_MODEL], check=True)
    srv.terminate()
    shutil.copytree(LOCAL, MODELS / "ollama", dirs_exist_ok=True)
    print("teacher copied to Drive, biggest file:", max(f.stat().st_size for f in (MODELS / "ollama" / "blobs").iterdir()) / 1e9, "GB")
else:
    print("teacher already in Drive")

# 2) the training bases from Hugging Face (public, no token needed; HF_TOKEN in Secrets only avoids rate limits)
subprocess.run("pip -q install huggingface_hub", shell=True)
from huggingface_hub import snapshot_download

for repo in BASES:
    dest = MODELS / "hf" / repo.split("/")[1]
    if (dest / "config.json").exists():
        print(repo, "already in Drive")
        continue
    snapshot_download(repo_id=repo, local_dir=str(dest), allow_patterns=["*.json", "*.safetensors", "*.txt", "merges.txt"])
    print(repo, "-> Drive")

# Drive writes in the background: force everything to upload BEFORE you disconnect
from google.colab import drive
drive.flush_and_unmount()
print("\nDone and flushed to Drive. Now you can disconnect. Cell 2 copies the teacher from Drive instead of downloading it.")
