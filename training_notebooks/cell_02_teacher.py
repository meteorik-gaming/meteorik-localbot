# CELL 2 -- the teacher: Qwen3 14B served by Ollama inside Colab (Apache 2.0, same quant family the game uses).
# Needs a GPU runtime (L4 is enough, 22 GB). Takes ~8 min the first time of each session (install + ~9 GB
# download). No token needed. To use the 8B instead, set TEACHER = "qwen3:8b" and PARALLEL = "8".
import json
import os
import re
import subprocess
import time

import requests

TEACHER = "qwen3:14b"
PARALLEL = "6"        # simultaneous requests; 6 keeps the 14B + its context inside an L4's memory
URL = "http://127.0.0.1:11434"
os.environ["OLLAMA_NUM_PARALLEL"] = PARALLEL
os.environ["OLLAMA_KEEP_ALIVE"] = "24h"
os.environ["OLLAMA_MODELS"] = "/content/ollama_models"
_blobs = BASE / "models" / "ollama" / "blobs"
if _blobs.exists() and any(f.stat().st_size > 1e9 for f in _blobs.iterdir()):     # saved by cell 0: copy from Drive
    import shutil
    shutil.copytree(BASE / "models" / "ollama", "/content/ollama_models", dirs_exist_ok=True)
    print("teacher copied from Drive")

subprocess.run("apt-get -qq install -y zstd", shell=True)
subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
server = subprocess.Popen(["ollama", "serve"], env=os.environ,
                          stdout=open("/content/ollama.log", "w"), stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        requests.get(URL, timeout=1)
        break
    except Exception:
        time.sleep(1)
subprocess.run(["ollama", "pull", TEACHER], check=True)


THINK = False         # True = the teacher reasons before answering (slower, better at following the header)


def ask(system, user, temperature=0.9, max_tokens=1500, json_mode=True):
    body = {
        "model": TEACHER, "stream": False, "think": THINK,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": temperature, "num_predict": max_tokens + (3000 if THINK else 0),
                    "num_ctx": 8192 if THINK else 6144},     # thinking tokens count against both limits
    }
    if json_mode and not THINK:         # format=json can cut the thinking short, so with THINK we cut the JSON out below
        body["format"] = "json"
    r = requests.post(URL + "/api/chat", json=body, timeout=900)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    if THINK:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        if json_mode and "{" in text and "}" in text:
            text = text[text.index("{"): text.rindex("}") + 1]
    return text


print(ask("Reply with JSON only.", 'Give {"ok": true}', max_tokens=20))
print(subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout)   # PROCESSOR should say 100% GPU
