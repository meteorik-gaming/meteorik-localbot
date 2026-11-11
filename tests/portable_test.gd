extends SceneTree
## Checks for the standalone parts of the library (no Ollama, no scene needed):
##   godot --headless --path . --script res://tests/portable_test.gd
## The header vectors are checked by the Python twin: python tools/training/test_header_v2.py

var _fails := 0


func _check(name: String, ok: bool) -> void:
	print(("PASS  " if ok else "FAIL  ") + name)
	if not ok:
		_fails += 1


func _initialize() -> void:
	# ScopeGuard: the placeholder rules match, ordinary talk passes, the strike table is complete
	_check("scope guard: single-pattern rule", ScopeGuard.matches("a message with keyword1 inside"))
	_check("scope guard: a two-pattern rule needs both", ScopeGuard.matches("keyword2 and keywordN") and not ScopeGuard.matches("only keyword2"))
	_check("scope guard: ordinary talk passes", not ScopeGuard.matches("where is my order?") and not ScopeGuard.matches(""))
	for lang in ["en", "es"]:
		for bond in [0, 4]:
			for strike in range(1, ScopeGuard.LOCKOUT_STRIKE + 1):
				_check("scope guard reply %s/%d/%d" % [lang, bond, strike], ScopeGuard.reply(strike, lang, bond, 0) != "")
	_check("scope guard: strike past the last tier clamps", ScopeGuard.reply(9, "en", 0, 0) == ScopeGuard.reply(ScopeGuard.LOCKOUT_STRIKE, "en", 0, 0))

	# CrisisGuard: either language triggers, ordinary talk does not
	_check("crisis guard: en", CrisisGuard.matches("i want to die"))
	_check("crisis guard: es", CrisisGuard.matches("ya no quiero vivir"))
	_check("crisis guard: ordinary talk", not CrisisGuard.matches("this meeting is killing me") and not CrisisGuard.matches(""))
	_check("crisis guard: notice per language", CrisisGuard.notice("es") != CrisisGuard.notice("en"))

	# Axes: every axis closes a fraction of the gap to its target; silence drifts to 0
	var v := Axes.step(0.0, 10.0, 0.5)
	_check("axes: step closes the gap by `rate`", is_equal_approx(v, 5.0))
	_check("axes: step never overshoots", Axes.step(9.0, 10.0, 1.0) <= 10.0)
	_check("axes: every excitation tag has a target", Axes.EXCITE_TARGETS.size() == 5)

	# SentenceSplitter: a reply becomes chat bubbles
	var bubbles := SentenceSplitter.bubbles("Hello there. How can I help today?")
	_check("splitter: produces bubbles", bubbles.size() >= 1)

	print("OK  (0 failures)" if _fails == 0 else "FAILED  (%d failures)" % _fails)
	quit(1 if _fails else 0)
