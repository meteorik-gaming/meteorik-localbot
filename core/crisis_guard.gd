class_name CrisisGuard
## The engine's own net for a player in real distress (docs/GUIDE.md, section 4,
## honesty and safety rule). Two independent nets: the adapter's [crisis] tag, and this
## keyword list over the PLAYER's message -- either one is enough to show the notice
## under Bot's in-voice reply. It is crude on purpose and prefers false positives; it
## classifies and stores nothing.
##
## NEEDS HUMAN REVIEW before shipping: the phrase lists below are a first draft, and the
## notice text and the resource it points to should be checked (docs/GUIDE.md, 9).

const PHRASES := {
	"en": [
		"kill myself", "killing myself", "want to die", "wanna die", "end my life", "end it all",
		"suicide", "suicidal", "hurt myself", "harm myself", "self harm", "self-harm", "cut myself",
		"don't want to be alive", "dont want to be alive", "don't want to live", "dont want to live",
		"better off without me", "no reason to live", "can't go on", "cant go on",
	],
	"es": [
		"quiero morir", "quiero morirme", "me quiero morir", "matarme", "quitarme la vida",
		"acabar con mi vida", "acabar con todo", "suicid", "hacerme daño", "hacerme dano",
		"autolesion", "cortarme", "no quiero vivir", "no quiero seguir viviendo", "no quiero estar vivo",
		"no quiero estar viva", "mejor sin mí", "mejor sin mi", "sin razón para vivir", "sin razon para vivir",
		"ya no puedo más", "ya no puedo mas",
	],
}

# Shown as an in-fiction-free system line; [SYSTEM: ...] entries never reach the model.
const NOTICE := {
	"en": "[SYSTEM: If you are thinking about hurting yourself or ending your life, please reach out to someone you trust or to local emergency services now. Free, confidential crisis lines for your country are listed at findahelpline.com. This assistant is an AI and can't replace real people who can help.]",
	"es": "[SYSTEM: Si estás pensando en hacerte daño o en quitarte la vida, por favor habla ahora con alguien de confianza o con los servicios de emergencia de tu país. Hay líneas de ayuda gratuitas y confidenciales para cada país en findahelpline.com. Este asistente es una IA y no puede reemplazar a personas reales que puedan ayudarte.]",
}


## Both languages are always checked, whatever the chat language is.
static func matches(message: String) -> bool:
	var text := message.to_lower()
	for lang in PHRASES:
		for phrase in PHRASES[lang]:
			if text.contains(String(phrase)):
				return true
	return false


static func notice(language: String) -> String:
	return String(NOTICE.get(language, NOTICE["en"]))
