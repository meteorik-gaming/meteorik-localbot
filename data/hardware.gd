class_name Hardware
## What the player's PC can run: the GPU's VRAM, read once through nvidia-smi (the
## only vendor tool we can count on being there). No NVIDIA card, or no driver tools,
## means "unknown", and the recommendation falls back to the light model.

## Headroom on top of a model's measured footprint: the desktop and the browser
## already hold some VRAM.
const HEADROOM_GB := 0.6

static var _probed := false
static var _info := { "name": "", "total_gb": 0.0, "free_gb": 0.0 }


## { name, total_gb, free_gb }; total_gb is 0.0 when no NVIDIA GPU was found.
static func gpu() -> Dictionary:
	if not _probed:
		_probed = true
		_info = _probe()
	return _info


static func has_gpu() -> bool:
	return float(gpu()["total_gb"]) > 0.0


static func _probe() -> Dictionary:
	var out := []
	var code := OS.execute("nvidia-smi", ["--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"], out, true)
	if code != 0 or out.is_empty():
		return { "name": "", "total_gb": 0.0, "free_gb": 0.0 }
	return parse(String(out[0]))


## Parses the first line of nvidia-smi's csv ("NVIDIA GeForce RTX 4050 Laptop GPU, 6141, 5200", MiB).
static func parse(text: String) -> Dictionary:
	var none := { "name": "", "total_gb": 0.0, "free_gb": 0.0 }
	var line := text.strip_edges().split("\n")[0]
	var parts := line.split(",")
	if parts.size() < 3:
		return none
	var total := parts[parts.size() - 2].strip_edges()
	var free := parts[parts.size() - 1].strip_edges()
	if not total.is_valid_float() or not free.is_valid_float():
		return none
	return {
		"name": ",".join(parts.slice(0, parts.size() - 2)).strip_edges(),
		"total_gb": float(total) / 1024.0,
		"free_gb": float(free) / 1024.0,
	}
