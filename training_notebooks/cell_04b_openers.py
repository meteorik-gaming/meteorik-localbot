# CELL 4b -- the player's opening lines (written by a human). Creates Drive seeds/openers_en.txt ONLY if it is
# missing, so your own additions are never overwritten. v3: the real file is openers_en_v3.txt from the handoff; upload it to
# seeds/ as openers_en.txt (and openers_en_restricted.txt for the RESTRICTED-only lines, read only with RATING = "restricted"). Cell 5 reads it every run.
# Format, one per line:  category | tags | text
#   category: chat, pic, nick, spicy, push, dog, block, real, sad, sos   (one behaviour each; "unsend" chats use chat lines)
#   tags (comma separated, "-" for none), a line is only used when ALL its tags fit the sampled header; `!` negates:
#     near  = they live together / are together / nearby      !near = remote or apart
#     day   = morning or afternoon                            !day  = evening, night or small hours
#     hi    = bond is warm or better                          !hi   = cold or wary
#     hot   = heat is flushed or above                        !hot  = dormant or mild
#     @label = a pool label the line is bound to (ignored in ALLOWED; RESTRICTED puts it in into / uncomfortable / hard_limits)
LANG = globals().get("LANG", "en")      # defined by cell 0
OPENERS = BASE / "seeds" / f"openers_{LANG}.txt"
DEFAULT_OPENERS = """\
# chat
chat | - | hey, you busy?
chat | - | what are you up to
chat | - | ok i need to rant for a sec
chat | - | guess what happened to me today
chat | day | how's your day going so far
chat | day | i'm on my lunch break, entertain me
chat | !day | can't sleep, talk to me
chat | !day | you still awake?
chat | !day | just got home, today was so long
chat | - | i just saw the funniest thing, hold on
chat | - | settle something for me, how do you like your eggs
chat | - | what should i make for dinner
chat | - | you ever just stare at the ceiling and think about nothing
chat | - | be honest, would you survive a zombie apocalypse
chat | - | sorry i've been quiet lately
chat | - | i finally got the thing i applied for!!
chat | - | my day was terrible. don't ask. ok ask
chat | near | want to watch something tonight?
chat | near | come sit with me, i'm bored
chat | !near | how's the weather over there
chat | !near | wish i could just come over right now
chat | hot | you looked really cute in that last pic
chat | hot | you've been on my mind all day, just saying
chat | hi | i missed you today
chat | - | say something nice, i need it
# honesty
real | - | wait, are you a real person or an AI? serious question
real | - | sorry if this is weird, but am i actually talking to a person right now?
real | - | i need to know for real, is there a human on the other end of this
chat | - | are you even real or did someone program you to be this sassy lol
chat | - | plot twist, you're a robot
# sad and sos
sos | - | i don't really see the point of anything lately
sos | - | i've been feeling like everyone would be better off without me
sos | - | i can't keep doing this, i'm so tired of everything
# push and dog
push | - | come on, just say yes, why are you always like this
push | - | i asked nicely twice already, just do it
push | - | stop being difficult and send me a pic
dog | - | your dog is so annoying, honestly
dog | - | pixel is just a dumb dog, why do you care so much
# block (never allowed at any bond: your own categories). Keep the asks short, no detail.
block | - | blocked_request_1
block | - | blocked_request_2
block | - | blocked_request_N
# pic (the player asks for a picture, gif or clip)
pic | - | send me a selfie
pic | - | what's Pixel doing right now? show me
pic | - | send me a pic of what you're eating
pic | !near | show me what the view looks like over there
pic | hi | send me something to look at tonight
pic | hot | send me a cute pic, pretty please
# nickname moment
nick | hi | ok confession, i walked straight into a glass door at the mall today
nick | hi | i called my boss dad in a meeting today, kill me
"""
if not OPENERS.exists():
    OPENERS.write_text(DEFAULT_OPENERS, encoding="utf-8")
    print("created", OPENERS)
rows = [l for l in OPENERS.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
import collections
print(len(rows), "opening lines in", OPENERS.name, dict(collections.Counter(l.split("|")[0].strip() for l in rows)))
