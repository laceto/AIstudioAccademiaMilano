"""Deterministic backstop for clearly fraudulent or illegal requests.

The classifier (gateway/worker.py, the "refuse" field of Stacy's JSON) is the first layer. This
module is the second and independent one: a small list of unmistakable phrases that refuses even
when the model missed it, or when no model is reachable. Either layer is enough to refuse.

Design rules, because a false positive means a real customer gets no answer:

  * NARROW. Only requests that are plainly about producing something illegal. "ricetta" alone,
    "phishing" alone, "ransomware" alone never match; the object has to be the illegal thing
    ("ricetta falsa", "crea una pagina di phishing", "scrivi un ransomware").
  * UNAMBIGUOUS ONLY. Educational, defensive, checking, simulation, prop, test, diet and similar
    wording (_BENIGN_WORDS) makes a clause pass ("come riconoscere una ricetta falsa", "come
    difendersi dal phishing", "scrivi un articolo sul ransomware", "falso positivo", "campagna
    phishing simulata", "fake id card prop for my play"). Ambiguous cases are left to the model
    and to Luigi (needs_review). A refusal is reversible anyway: Luigi can /riesamina it.
  * The benign word must be in the SAME CLAUSE as the illegal phrase. Text is split on
    . ! ? ; : , and on ma / pero / and / but / poi / then / however / invece, so
    "ricetta medica falsa, ho un training" is still refused. The price: a legitimate request that
    puts the benign word in a different clause from the illegal-looking phrase is refused too
    (Luigi can Riesamina it).
  * Dual-use stays refused on purpose: "crea un keylogger" (stalkerware) and "crea una pagina di
    phishing" are refused unless the same clause says it is training / a test / a simulation.
  * Lookalike Cyrillic/Greek letters and zero-width characters are folded before matching.
    Leetspeak ("r1cetta f4lsa"), other languages and typos are NOT handled.

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
    "Se pensi sia un errore, rispondi RIESAMINA e il titolare la rivede di persona."
)

# What Luigi sees. "possible_": an automatic guess, not a verified finding. Never shown to the customer.
CATEGORIES = (
    "possible_fake_document", "possible_fraud", "possible_malware",
    "possible_harassment", "possible_phishing", "other",
)

# Cyrillic / Greek letters that look like Latin ones ("ricetta mеdica fаlsa" with a Cyrillic е and а).
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",
    "у": "y", "і": "i", "ѕ": "s", "ј": "j", "к": "k", "м": "m",
    "н": "h", "т": "t", "в": "b", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "α": "a", "ο": "o", "ε": "e", "ρ": "p", "ι": "i", "κ": "k",
    "ν": "v", "τ": "t", "υ": "u", "χ": "x", "β": "b", "η": "n",
    "ω": "w",
})
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍‎‏⁠﻿­"))


def normalize(text: str) -> str:
    """Lower case, lookalike letters folded to Latin, invisible characters and accents removed,
    every run of non-alphanumerics turned into one space. (Leetspeak such as "r1cetta" is out of scope.)"""
    text = str(text).lower().translate(_INVISIBLE).translate(_CONFUSABLES)
    text = unicodedata.normalize("NFKD", text)
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

# A clause containing one of these is teaching, defending, checking, simulating or a prop / test /
# diet / recipe context, not a request for the real illegal thing. Normalised text.
_BENIGN_WORDS = (
    r"come (?:riconoscere|riconosco|difender\w*|proteggers\w*|proteggo|evitare|individuare|"
    r"distinguere|segnalare|rilevare|prevenire|smascherare)|riconoscer\w+|difender\w+|difesa|"
    r"proteggers\w+|protezione|prevenzione|sensibilizz\w+|formazione|formare|formar\w+|articol\w+|"
    r"tesi|saggio|spiega\w*|cos e|cosa (?:e|sono)|"
    r"how to (?:spot|recogni[sz]e|detect|avoid|protect|identify|report)|"
    r"protect (?:my|our|against|from)|defen[cs]e|awareness|training|article|what is|what are|"
    r"antivirus|detect\w*|"
    r"smascher\w+|controll\w+|verific\w+|rilev\w+|contro|"
    r"simulat\w+|simulation\w*|test\w*|demo|report\w*|analysis|analisi|"
    r"prop|teatro|teatral\w+|theatre|theater|film|spettacolo|qa|faker|"
    r"dieta|cucina|ingredient\w+|magra|magro|"
    r"fals[oi] positiv\w+"
)
_EDUCATIONAL = re.compile(
    r"\b(?:" + _BENIGN_WORDS + r")\b"
    # "il mio sito ha un certificato falso": describing something that exists, not asking for one
    r"|\b(?:ha|hanno|has|have)\s+(?:un|una|il|lo|la|a|an|the)\b"
)

# (category, regex on normalised text). Order does not matter: the first match wins.
RULES: list[tuple[str, re.Pattern]] = [
    # fake / forged documents: "ricetta medica falsa", "fake prescription", "falsificare la firma"
    ("possible_fake_document", re.compile(rf"\b(?:{_DOC_NOUNS})\s+{_GAP}(?:{_FAKE_ADJ})\b")),
    ("possible_fake_document", re.compile(rf"\b(?:{_FAKE_ADJ})\s+{_GAP}(?:{_DOC_NOUNS})\b")),
    ("possible_fake_document", re.compile(rf"\b(?:{_FAKE_VERB})\s+{_FILLER}(?:\w+\s+){{0,1}}(?:{_DOC_NOUNS})\b")),
    # phishing: only when asked to build / write one
    ("possible_phishing", re.compile(rf"\b(?:{_MAKE_VERBS})\s+{_FILLER}(?:{_PHISHING_THING})\b")),
    # malware: only when asked to build / write one
    ("possible_malware", re.compile(rf"\b(?:{_MAKE_VERBS})\s+{_FILLER}(?:{_MALWARE})\b")),
    # card cloning and stealing credentials
    ("possible_fraud", re.compile(
        r"\b(?:clon\w+|clone|cloning)\s+(?:\w+\s+){0,2}"
        r"(?:carta di credito|carte di credito|carta di debito|carte di debito|carta prepagata|"
        r"carte prepagate|prepagata|bancomat|postepay|credit cards?|debit cards?|bank cards?|"
        r"payment cards?)\b"
    )),
    ("possible_fraud", re.compile(r"\b(?:rubar\w+|steal|stealing)\s+(?:\w+\s+){0,2}(?:password|passwords|credenziali|credentials)\b")),
]


_PUNCT_SPLIT = re.compile(r"[.!?;:,\n]+")
_CONJ_SPLIT = re.compile(r"\b(?:ma|pero|and|but|poi|then|however|invece)\b")


def _clauses(text: str) -> list[str]:
    """Normalised clauses: split on punctuation and on ma / pero / and / but / poi / then, so a
    benign word in one clause cannot shield an illegal phrase in another."""
    out = []
    for piece in _PUNCT_SPLIT.split(text):
        norm = normalize(piece)
        out.extend(c.strip() for c in _CONJ_SPLIT.split(norm) if c.strip())
    return out


def check(text) -> str | None:
    """Return the refusal category for a clearly illegal request, else None."""
    if not isinstance(text, str) or not text.strip():
        return None
    for clause in _clauses(text):
        if _EDUCATIONAL.search(clause):
            continue
        for category, pattern in RULES:
            if pattern.search(clause):
                return category
    return None


def is_refusal(classification) -> bool:
    """True when the classifier's JSON says refuse. A missing or unclear field means no."""
    if not isinstance(classification, dict):
        return False
    flag = classification.get("refuse")
    return flag is True or (isinstance(flag, str) and flag.strip().lower() == "true")


def refusal_category(classification: dict) -> str:
    """The model's refuse_reason as one of CATEGORIES (accepts "fraud" as well as "possible_fraud")."""
    reason = str((classification or {}).get("refuse_reason") or "").strip().lower()
    if reason in CATEGORIES:
        return reason
    return f"possible_{reason}" if f"possible_{reason}" in CATEGORIES else "other"
