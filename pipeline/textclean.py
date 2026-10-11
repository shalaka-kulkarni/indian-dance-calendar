"""Tidy listing text so it reads like an editor checked it, without changing
what it says.

Titles arrive exactly as each venue or listing site publishes them, and some of
those sites damage them on the way. Sulekha capitalises the first letter of
every word, which flattens NY to "Ny", NYC to "Nyc" and DJ to "Dj", and
capitalises every "In", "Of" and "With". Organisers misspell the city
("Niew York", "Newyork"). Arena calendars append search tags ("Tickets NJ").
WordPress feeds leave HTML codes ("&amp;", "&#8217;") and sometimes whole
escaped tags in the text.

Everything here is a fixed, reviewable substitution. Nothing is generated or
guessed: a word this module does not recognise passes through untouched.
"""

from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
# Pictographs and their joiners. Listing sites decorate titles with them
# ("🎃11th Annual ..."); they carry no information on a calendar.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]+"
)
_SPACE = re.compile(r"\s+")

# "Niew York", "Niewyork", "Newyork", "NewYork", "New-york" -> New York.
_NEW_YORK = re.compile(r"\bn(?:ie|ei|e)w[\s-]*york\b", re.I)
_NEW_JERSEY = re.compile(r"\bnew[\s-]*jers(?:e)?y\b", re.I)

# Acronyms as a capitalise-every-word filter leaves them. Only these exact
# damaged forms are restored; "Us", "Li" and "Mc" are real words or names and
# are deliberately absent.
_ACRONYMS = {
    "Ny": "NY", "Nyc": "NYC", "Nj": "NJ", "Dj": "DJ", "Djs": "DJs",
    "Usa": "USA", "Uk": "UK", "Ubs": "UBS", "Vip": "VIP", "Lic": "LIC",
    "Ddlj": "DDLJ",
}
_ACRONYM_WORD = re.compile(r"\b(" + "|".join(_ACRONYMS) + r")\b")
# "Nye" is a surname as often as New Year's Eve; restore it only before a year
# or a party word.
_NYE = re.compile(r"\bNye(?=\s+(?:20\d\d|Party|Bash|Gala|Night|Celebration)\b)")
_AR_RAHMAN = re.compile(r"\bA\.?\s?R\.?\s+Rahman\b|\bAr\s+Rahman\b")

# "J A Jayant", "K S Vishnudev" -> "J.A. Jayant", "K.S. Vishnudev": two or
# three lone capitals in a row, followed by a name.
_INITIALS = re.compile(r"\b((?:[A-Z]\.?\s){2,3})(?=[A-Z][a-z])")

# Search tags arena calendars append to page titles.
_SEO_TAIL = re.compile(
    r"(?:\s+Tickets\s+(?:NJ|NY|NYC|New Jersey|New York)"
    r"|\s*[|–-]\s*Tickets?(?:\s+(?:&|and)\s+Info)?)\s*$",
    re.I,
)

# A hyphen with spaces on both sides is being used as a dash.
_SPACED_HYPHEN = re.compile(r"(?<=\S) - (?=\S)")

# Words a style guide keeps lower case inside a title.
_MINOR = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "the", "to", "vs", "via", "with",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z'’.]*")
# After these, a new phrase starts and its first word keeps its capital.
_PHRASE_BREAK = re.compile(r"(?:^|[:–—|(“\"!?]|\s-)\s*$")


def plain(text: str) -> str:
    """Decode HTML codes (twice: some feeds escape their markup) and drop tags."""
    text = html.unescape(html.unescape(text or ""))
    return _SPACE.sub(" ", _TAG.sub(" ", text)).strip()


def _is_mechanical_title_case(text: str) -> bool:
    """True when every word starts with a capital and a minor word is among
    them — the mark of a capitalise-every-word filter, not an editor."""
    if not re.search(r"[a-z]", text):
        return False  # all capitals is a deliberate style; leave it
    words = _WORD.findall(text)
    if len(words) < 3 or not all(w[0].isupper() for w in words):
        return False
    return any(w.lower().rstrip(".") in _MINOR for w in words[1:-1])


def _lower_minor_words(text: str) -> str:
    matches = list(_WORD.finditer(text))
    if not matches:
        return text
    out, last = [], 0
    for i, m in enumerate(matches):
        word = m.group(0)
        key = word.lower()
        keep = (
            i == 0
            or i == len(matches) - 1
            or key not in _MINOR
            or _PHRASE_BREAK.search(text[: m.start()])
        )
        out.append(text[last : m.start()])
        out.append(word if keep else key)
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _initials(m: re.Match) -> str:
    letters = re.findall(r"[A-Z]", m.group(1))
    return ".".join(letters) + ". "


def _common(text: str) -> str:
    text = _EMOJI.sub(" ", plain(text))
    text = _SPACE.sub(" ", text).strip()
    text = _NEW_YORK.sub(lambda m: "NEW YORK" if m.group(0).isupper() else "New York", text)
    text = _NEW_JERSEY.sub(lambda m: "NEW JERSEY" if m.group(0).isupper() else "New Jersey", text)
    text = _ACRONYM_WORD.sub(lambda m: _ACRONYMS[m.group(1)], text)
    text = _NYE.sub("NYE", text)
    text = _AR_RAHMAN.sub("A.R. Rahman", text)
    text = _INITIALS.sub(_initials, text)
    text = _SPACED_HYPHEN.sub(" – ", text)
    if _is_mechanical_title_case(text):
        text = _lower_minor_words(text)
    return text


def clean_title(text: str) -> str:
    text = _SEO_TAIL.sub("", _common(text))
    return text.strip(" ,;:|–—-").strip()


def clean_venue(text: str) -> str:
    return _common(text).strip(" ,;:|–—-").strip()


def clean_description(text: str) -> str:
    return plain(text)
