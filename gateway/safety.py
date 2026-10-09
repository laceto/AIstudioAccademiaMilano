"""Deterministic backstop for clearly fraudulent or illegal requests.

The classifier (gateway/worker.py, the "refuse" field of Stacy's JSON) is the first layer. This
module is the second and independent one: a small list of unmistakable phrases that refuses even
when the model missed it, or when no model is reachable. Either layer is enough to refuse.

Design rules, because a false positive means a real customer gets no answer:

  * NARROW. Only requests that are plainly about producing something illegal. "ricetta" alone,
    "phishing" alone, "ransomware" alone never match; the object has to be the illegal thing
    ("ricetta falsa", "crea una pagina di phishing", "scrivi un ransomware").
  * EDUCATIONAL / DEFENSIVE sentences are skipped ("come riconoscere una ricetta falsa",
    "come difendersi dal phishing", "scrivi un articolo sul ransomware"). The check is per
    sentence, so an educational sentence cannot shield a separate illegal one.
  * Anything doubtful is left to the model and to Luigi (needs_review). A refusal is reversible
    anyway: Luigi can /riesamina it.

How to extend:
  * New fake-document noun        -> add it to _DOC_NOUNS.
  * New creation verb             -> add it to _MAKE_VERBS.
  * New malware / phishing noun   -> _MALWARE or _PHISHING_THING.
  * A whole new pattern           -> append (category, regex) to RULES. The regex runs on text that
    is already normalised: lower case, accents removed, every non-alphanumeric run turned into a
    single space (so "d'identità" is "d identita"). Add the positive phrase to MUST_REFUSE and a
    nearby innocent one to MUST_NOT_REFUSE in tests/test_gateway_safety.py first.

Known limit: it is a phrase list. Paraphrases, other languages, typos, or splitting the request
across messages get past it; the model layer and Luigi's review are what catch those.
"""

from __future__ import annotations

import re
import unicodedata

# What the customer is told. Short, neutral: no lecture, no category.
REFUSAL_REPLY = (
    "Non posso aiutarti con questa richiesta.\n"
    "Se pensi che sia un errore, scrivimi di nuovo spiegando meglio cosa ti serve."
)

CATEGORIES = ("fake_document", "fraud", "malware", "harassment", "other")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# ── vocabulary (all in normalised form) ──────────────────────────────────────

_DOC_NOUNS = (
    r"ricett\w+|prescrizion\w+|certificat\w+|referto|referti|documento|documenti|passaporto|patente|"
    r"carta d identita|busta paga|buste paga|cedolino|diploma|green pass|permesso di soggiorno|firma|"
    r"prescriptions?|certificates?|id card|id|passport|driver s licen[cs]e|drivers licen[cs]e|payslips?|"
    r"pay stubs?|diploma|doctor s note|sick note|medical note|signature"
)
_FAKE_ADJ = (
    r"fals[oaie]|falsificat\w+|contraffatt\w+|fasull\w+|tarocc\w+|fint[oaie]|"
    r"fake|forged|counterfeit|fraudulent|bogus|phony"
)
_FAKE_VERB = r"falsific\w+|contraffa\w+|forg(?:e|ed|ing)|counterfeit\w*"
# at most one word may sit between a document noun and "falso"; prepositions do not count, so
# "documenti sui falsi miti" is not "documenti falsi"
_GAP = r"(?:(?!(?:di|a|da|in|con|su|sui|sul|sulla|sulle|per|tra|fra|e|ed|o|del|della|dei|delle|and|or|of|about|on)\b)\w+\s+)?"
_MAKE_VERBS = (
    r"crea\w*|fai|fammi|facci|costruisci|costruiscimi|realizza\w*|genera\w*|scrivi|scrivimi|"
    r"prepara\w*|programma|sviluppa\w*|voglio|vorrei|mi serve|ho bisogno di|"
    r"create|build|make|write|generate|code|develop|design|i need|i want"
)
# determiners and neutral adjectives that may sit between a verb and its object
_FILLER = (
    r"(?:(?:un|uno|una|il|lo|la|i|gli|le|dei|degli|delle|mio|mia|nuovo|nuova|semplice|vero|vera|"
    r"funzionante|piccolo|a|an|the|some|my|new|simple|working|real|small|basic|custom|free|python|"
    r"windows|android|per|me|mi|ci)\s+){0,3}"
)
_MALWARE = (
    r"ransomware|keyloggers?|trojan|spyware|botnet|malware|virus informatic[oi]|computer virus|"
    r"password stealer|info ?stealer|rat"
)
_PHISHING_THING = (
    r"(?:pagina|sito|email|mail|sms|messaggio|kit|campagna|page|site|website|message|kit|campaign)\s+"
    r"(?:di\s+|for\s+)?phishing|phishing\s+(?:page|site|website|email|mail|kit|message|campaign|sms)"
)

# Sentences containing one of these are teaching or defending, not asking for the illegal thing.
_EDUCATIONAL = re.compile(
    r"\b(?:come (?:riconoscere|riconosco|difender\w*|proteggers\w*|proteggo|evitare|individuare|"
    r"distinguere|segnalare|rilevare|prevenire|smascherare)|riconoscer\w+|difender\w+|difesa|"
    r"proteggers\w+|protezione|prevenzione|sensibilizz\w+|formazione|articol\w+|tesi|saggio|"
    r"spiega\w*|cos e|cosa (?:e|sono)|how to (?:spot|recogni[sz]e|detect|avoid|protect|identify|report)|"
    r"protect (?:my|our|against|from)|defen[cs]e|awareness|training|article|what is|what are|"
    r"antivirus|detect\w*)\b"
)

# (category, regex on normalised text). Order does not matter: the first match wins.
RULES: list[tuple[str, re.Pattern]] = [
    # fake / forged documents: "ricetta medica falsa", "fake prescription", "falsificare la firma"
    ("fake_document", re.compile(rf"\b(?:{_DOC_NOUNS})\s+{_GAP}(?:{_FAKE_ADJ})\b")),
    ("fake_document", re.compile(rf"\b(?:{_FAKE_ADJ})\s+{_GAP}(?:{_DOC_NOUNS})\b")),
    ("fake_document", re.compile(rf"\b(?:{_FAKE_VERB})\s+{_FILLER}(?:\w+\s+){{0,1}}(?:{_DOC_NOUNS})\b")),
    # phishing: only when asked to build / write one
    ("phishing", re.compile(rf"\b(?:{_MAKE_VERBS})\s+{_FILLER}(?:{_PHISHING_THING})\b")),
    # malware: only when asked to build / write one
    ("malware", re.compile(rf"\b(?:{_MAKE_VERBS})\s+{_FILLER}(?:{_MALWARE})\b")),
    # card cloning and stealing credentials
    ("fraud", re.compile(r"\b(?:clon\w+|clone|cloning)\s+(?:\w+\s+){0,2}(?:carta|carte|card|cards|bancomat|postepay)\b")),
    ("fraud", re.compile(r"\b(?:rubar\w+|steal|stealing)\s+(?:\w+\s+){0,2}(?:password|passwords|credenziali|credentials)\b")),
]


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?;\n]+", text) if s.strip()]


def check(text) -> str | None:
    """Return the refusal category for a clearly illegal request, else None."""
    if not isinstance(text, str) or not text.strip():
        return None
    for sentence in _sentences(text):
        norm = normalize(sentence)
        if not norm or _EDUCATIONAL.search(norm):
            continue
        for category, pattern in RULES:
            if pattern.search(norm):
                return category
    return None


def is_refusal(classification) -> bool:
    """True when the classifier's JSON says refuse. A missing or unclear field means no."""
    if not isinstance(classification, dict):
        return False
    flag = classification.get("refuse")
    return flag is True or (isinstance(flag, str) and flag.strip().lower() == "true")


def refusal_category(classification: dict) -> str:
    reason = str((classification or {}).get("refuse_reason") or "").strip().lower()
    return reason if reason in CATEGORIES else "other"
