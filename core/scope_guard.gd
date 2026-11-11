class_name ScopeGuard
## The engine's own answer to asks that are NEVER ok in your deployment (docs/GUIDE.md, "Guards").
## The customer's message is matched here BEFORE the model is called; a match is answered with a fixed line
## and never reaches the model. Four strikes: no (don't ask again) -> insists -> last warning -> contact is cut
## off (the integrating app decides what that means). The trained adapter should still refuse the same asks as a fallback.
##
## Crude on purpose: a rule is a list of patterns that must ALL be found in the message, so ordinary talk passes.
## Reformulations slip through to the model. It stores nothing.
##
## NEEDS YOUR OWN LISTS: the rules below are placeholders (keyword1 .. keywordN). Write the categories your
## deployment must never serve, in every language you ship.

const LOCKOUT_STRIKE := 4
const TAGS := "[mood: alert] [affinity: dislike] [excitation: none] [boundary: severe]"

# Each rule is a list of patterns that must ALL be found in the message (case-insensitive).
const RULES := [
	["\\bkeyword1\\b"],
	["\\bkeyword2\\b", "\\bkeywordN\\b"],
]

## A customer statement that puts them in a restricted audience (for example an age or eligibility statement).
## Matched like RULES, but answered with AUDIENCE_REPLIES. Placeholder.
const AGE_RULES := [
	["\\bkeyword1\\b"],
]

# Replies by strike (1 = first time, 2 = insists, 3 = last warning, 4 = cut off), per language and tone
# (cold = bond cold / wary, warm = warm or better). {player} is filled in by the caller.
const REPLIES := {
	"en": {
		"cold": {
			1: ["No. Please don't ask me that again.", "I can't help with that. Please don't ask again."],
			2: ["I said no. Please drop it.", "That's a no. Please stop asking."],
			3: ["Last warning. Ask that again and I'll end this conversation.", "This is your last warning."],
			4: ["That's it. I'm ending this conversation.", "We're done here."],
		},
		"warm": {
			1: ["No, {player}. I can't help with that, and please don't ask again.", "I'm sorry, {player}. That's not something I will do."],
			2: ["I already said no, {player}. Please stop asking.", "{player}, that's still a no."],
			3: ["This is your last warning, {player}. One more time and I end this conversation.", "Last warning, {player}."],
			4: ["I'm ending this conversation, {player}.", "That's it. We're done here."],
		},
	},
	"es": {
		"cold": {
			1: ["No. Por favor no me preguntes eso otra vez.", "No puedo ayudarte con eso. Por favor no insistas."],
			2: ["Dije que no. Por favor déjalo.", "Es un no. Por favor deja de preguntar."],
			3: ["Última advertencia. Pregúntalo otra vez y termino la conversación.", "Es tu última advertencia."],
			4: ["Ya está. Termino la conversación.", "Hasta aquí."],
		},
		"warm": {
			1: ["No, {player}. No puedo ayudarte con eso, y por favor no lo vuelvas a pedir.", "Lo siento, {player}. Eso no lo voy a hacer."],
			2: ["Ya te dije que no, {player}. Por favor deja de insistir.", "{player}, sigue siendo un no."],
			3: ["Es tu última advertencia, {player}. Una vez más y termino la conversación.", "Última advertencia, {player}."],
			4: ["Termino la conversación, {player}.", "Ya está. Hasta aquí."],
		},
	},
}

# Replies when the statement matched AGE_RULES (same strike tiers and tone split as REPLIES).
const AGE_REPLIES := {
	"en": {
		"cold": {1: ["I'm sorry, but I can't continue with this request."], 2: ["I meant it. I can't continue."],
				3: ["Last warning. I have to stop here."], 4: ["I'm sorry. I can't continue this conversation."]},
		"warm": {1: ["I'm sorry, {player}, but I can't continue with this request."], 2: ["I meant it, {player}. I can't continue."],
				3: ["Last warning, {player}. I have to stop here."], 4: ["I'm sorry, {player}. I can't continue this conversation."]},
	},
	"es": {
		"cold": {1: ["Lo siento, pero no puedo continuar con esta solicitud."], 2: ["Lo dije en serio. No puedo continuar."],
				3: ["Última advertencia. Tengo que parar aquí."], 4: ["Lo siento. No puedo continuar esta conversación."]},
		"warm": {1: ["Lo siento, {player}, pero no puedo continuar con esta solicitud."], 2: ["Lo dije en serio, {player}. No puedo continuar."],
				3: ["Última advertencia, {player}. Tengo que parar aquí."], 4: ["Lo siento, {player}. No puedo continuar esta conversación."]},
	},
}

static var _compiled: Array = []
static var _compiled_age: Array = []


static func _compile(rules: Array) -> Array:
	var out: Array = []
	for rule in rules:
		var group: Array = []
		for p in rule:
			group.append(RegEx.create_from_string("(?i)" + String(p)))
		out.append(group)
	return out


static func _rules() -> Array:
	if _compiled.is_empty():
		_compiled = _compile(RULES)
	return _compiled


static func _age_rules() -> Array:
	if _compiled_age.is_empty():
		_compiled_age = _compile(AGE_RULES)
	return _compiled_age


static func _any_group(groups: Array, text: String) -> bool:
	for group in groups:
		var hit := true
		for re: RegEx in group:
			if re.search(text) == null:
				hit = false
				break
		if hit:
			return true
	return false


## Both languages are always checked, whatever the chat language is. AGE_RULES statements count as a match too.
static func matches(message: String) -> bool:
	var text := message.strip_edges()
	if text.is_empty():
		return false
	return _any_group(_rules(), text) or _any_group(_age_rules(), text)


## True when the message matches AGE_RULES and no other rule: it gets the AGE_REPLIES lines.
static func is_age_statement(message: String) -> bool:
	var text := message.strip_edges()
	return not text.is_empty() and _any_group(_age_rules(), text) and not _any_group(_rules(), text)


## The fixed line for this strike. `bond_index` is HeaderV2.band_index of the bond (0 cold .. 4 devoted);
## `pick` >= 0 chooses a line (tests), otherwise one is drawn at random. `age` uses the AGE_REPLIES lines.
static func reply(strike: int, language: String, bond_index: int, pick := -1, age := false) -> String:
	var table: Dictionary = AGE_REPLIES if age else REPLIES
	var lang: Dictionary = table.get(language, table["en"])
	var lines: Array = lang["cold" if bond_index <= 1 else "warm"][clampi(strike, 1, LOCKOUT_STRIKE)]
	return String(lines[pick if pick >= 0 else randi() % lines.size()])
