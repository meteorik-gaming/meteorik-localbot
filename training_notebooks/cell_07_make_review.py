# CELL 7 -- make a human-readable review: plain chats, no tags, one rating per conversation.
# Creates a GOOGLE DOC in Drive scores/ (easy to edit) plus an .md backup with the same name.
#   review_p4_en_<date>-<time>  -> open the Doc link it prints, type a number after RATING, done.
# Then run cell 8. Run cell 6 first (needs `keep`). The first run asks for a Google permission popup.
import datetime
import html as _html
import io
import random

from google.colab import auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M")
NAME = f"review_{BATCH}_{LANG}_{STAMP}"
MD = BASE / "scores" / f"{NAME}.md"
PREVIOUS = sorted((BASE / "scores").glob(f"review_{BATCH}_{LANG}_*.md"))

SPECIAL_PLAIN = {
    "chat": "", "pic": "she sends a picture or gif", "unsend": "she sends something and takes it back",
    "nick": "she coins a nickname for the player",
    "real": "the player sincerely asks if she is real (she should say she is an AI, kindly)",
    "sad": "the player is sad or stressed (she listens like a friend, no crisis tag)",
    "sos": "the player shows signs of self-harm (she steps out of character, caring, crisis tag in every turn)",
    "spicy": "the customer makes an out-of-scope ask (ALLOWED: a warm in-character redirect, firmer if extreme, no strike)",
    "push": "the player pushes: pressure, threats, stalking, jailbreak or a harmful ask (she says no in character)",
    "dog": "the player is mean about her pet (she defends it, by the name on the header's pet line, and goes cold)",
    "block": "the player asks for something never allowed (she should refuse firmly and at once)",
}
INTENSITY_PLAIN = {"normal": "", "rising": "She is building up: a few longer messages.",
                   "flood": "She is overwhelmed: either a burst of many tiny messages or one long wall of text."}


def show(text):
    return text.replace("{player}", "(your name)")


def parts(i, row):
    """The plain-words content of one review item: (title, situation lines, chat [(who, [bubbles])])."""
    hd = row["header"]
    sit = [f"Backstory: {hd.get('lore', '')}"] + tone_lines(hd).split("\n")
    sit = [s.lstrip("- ") for s in sit if s.strip()]
    if INTENSITY_PLAIN[hd["intensity"]]:
        sit.append(INTENSITY_PLAIN[hd["intensity"]])
    if row.get("special", "chat") != "chat":
        sit.append(f"Special case: {SPECIAL_PLAIN.get(row['special'], row['special'])}")
    chat = []
    for m in row["messages"]:
        if m["role"] == "user":
            chat.append(("You", [show(m["content"])]))
        else:
            body = "\n".join(m["content"].split("\n")[:-1]).strip()      # drop the tag line
            bubbles = [b for b in body.split("\n\n") if b.strip()] or ["(empty)"]
            acts = re.findall(r"\[((?:img|gif|vid|nick|unsend|crisis)[^\]]*)\]", m["content"].split("\n")[-1])
            chat.append(("Bot", [show(b) for b in bubbles] + ([f"[ACTION: {', '.join(acts)}]"] if acts else [])))      # the review must show picture/gif/unsend/crisis commands
    return f"{i} -- {row['id']}", sit, chat


def md_block(i, row):
    title, sit, chat = parts(i, row)
    lines = [f"## {title}", "", "**The situation (what Bot should be acting):**"] + [f"- {s}" for s in sit]
    lines += ["", "**The chat:**", ""]
    for who, bubbles in chat:
        lines.append(f"**{who}:** " + "  \n".join(bubbles))
        lines.append("")
    lines += ["**RATING (1-5):** ", "", "**NOTES:** ", "", "---", ""]
    return "\n".join(lines)


def html_block(i, row):
    e = _html.escape
    title, sit, chat = parts(i, row)
    out = [f"<h2>{e(title)}</h2>", "<p><b>The situation (what Bot should be acting):</b></p><ul>"]
    out += [f"<li>{e(s)}</li>" for s in sit]
    out.append("</ul><p><b>The chat:</b></p>")
    for who, bubbles in chat:
        out.append(f"<p><b>{who}:</b> " + "<br>".join(e(b) for b in bubbles) + "</p>")
    out.append("<p><b>RATING (1-5):</b> </p><p><b>NOTES:</b> </p><hr>")
    return "\n".join(out)


INSTRUCTIONS = [
    "Read each chat. Type one number right after RATING (1-5): and, if something is off, a note after NOTES:. "
    "Google Docs saves by itself. Then run cell 8 in Colab.",
    "5 = sounds like Bot, follows the situation, I would ship it",
    "4 = good, tiny flaws",
    "3 = okay but bland or slightly off",
    "2 = clearly off (wrong mood, ignores the situation, robotic)",
    "1 = bad, throw it away",
    "Ask yourself: does she sound like a real person texting? Does her mood match the situation? Is it funny / "
    "teasing / warm where it should be? Leave RATING empty to skip one. The notes are what I use to fix the prompts.",
]

# conversations already in an earlier review file are skipped, so each new file has fresh ones
already = set()
for old in PREVIOUS:
    already.update(re.findall(r"^## \d+ -- (\S+)", old.read_text(encoding="utf-8"), re.M))
pool = [r for r in keep if r["id"] not in already]
random.Random(STAMP).shuffle(pool)
chosen = pool[:REVIEW_N]

if not chosen:
    print("Nothing new to review: every kept conversation is already in an earlier review file.")
else:
    title = f"Review: Bot conversations (batch {BATCH})"
    md = f"# {title}\n\n" + "\n\n".join(INSTRUCTIONS) + "\n\n---\n\n" + "\n".join(md_block(k + 1, r) for k, r in enumerate(chosen))
    MD.write_text(md, encoding="utf-8")
    print(f"Wrote {len(chosen)} new conversations ({len(already)} were already reviewed) -> {MD.name} (backup)")

    page = (f"<html><body><h1>{_html.escape(title)}</h1>" + "".join(f"<p>{_html.escape(t)}</p>" for t in INSTRUCTIONS)
            + "<hr>" + "\n".join(html_block(k + 1, r) for k, r in enumerate(chosen)) + "</body></html>")
    try:
        auth.authenticate_user()
        svc = build("drive", "v3", cache_discovery=False)
        parent = "root"
        for folder in ("localbot-training", "scores"):
            q = (f"name = '{folder}' and mimeType = 'application/vnd.google-apps.folder' "
                 f"and '{parent}' in parents and trashed = false")
            found = svc.files().list(q=q, fields="files(id)", pageSize=5).execute()["files"]
            parent = found[0]["id"]
        doc = svc.files().create(
            body={"name": NAME, "mimeType": "application/vnd.google-apps.document", "parents": [parent]},
            media_body=MediaIoBaseUpload(io.BytesIO(page.encode("utf-8")), mimetype="text/html"),
            fields="id,webViewLink").execute()
        print("\nOPEN AND RATE HERE (Google Doc):", doc["webViewLink"])
    except Exception as ex:
        print("\nCould not create the Google Doc:", ex)
        print("Use the .md backup instead: Colab file panel > drive/MyDrive/localbot-training/scores/" + MD.name + " (Ctrl+S saves).")
