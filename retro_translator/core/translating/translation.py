"""Translation without AI: a glossary of game phrases, then Apertium (rules). Words Apertium does not know
stay as they are (character, place and move names)."""
import functools
import json
import os
import re
import subprocess
from retro_translator import DATA

# Apertium programs for Windows (official 3.10 build) and language pairs compiled with them (tools/build_pairs.sh).
# During development (WSL) the same .exe run through interop; in the executable they sit next to the program.
_JOINED = os.path.join(DATA, "apertium")  # only in the executable (Windows build of Apertium)
BIN = os.environ.get("APERTIUM_BIN", os.path.join(_JOINED, "bin") if os.path.isdir(_JOINED)
                     else os.path.expanduser("~/apertium-win/bin"))
APERTIUM_DATA = os.environ.get("APERTIUM_DATA", os.path.join(_JOINED, "data") if os.path.isdir(_JOINED)
                       else os.path.expanduser("~/apertium-win/data2"))
_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}  # windowed exe: each console child would open a terminal
SOURCE = "en"  # the game's language, found from the font (core/preparation.py, decipher)
# The offline neural model (neural.py) translates straight into each language: it measured better than the
# rule-based pairs (chrF 0.558 against 0.512 for English to Portuguese; French through Apertium left words untranslated).
# European Portuguese goes through Spanish and the rule-based es-pt pair, which has that variant; Spanish games use the
# es-pt pair, a close and accurate one.
ROUTES = {o: {d: ["neural-" + d] for d in ("pt", "es", "en", "fr")} for o in ("en", "fr", "ja", "zh")}
for o in ROUTES:
    ROUTES[o]["pt-PT"] = ["neural-es", "spa-por_PT"]
ROUTES["es"] = {"pt": ["spa-por"], "pt-PT": ["spa-por_PT"], "en": ["neural-en"], "fr": ["neural-fr"]}
for o in ROUTES:
    ROUTES[o][o] = []  # the game is already in that language


class _Route(dict):
    """Pairs from the game's language (SOURCE) to each target language."""
    def __getitem__(self, language):
        return ROUTES.get(SOURCE, {})[language]

    def __contains__(self, language):
        return language in ROUTES.get(SOURCE, {})


PATH_ = _Route()
STEPS = {
    "eng-spa": [["lt-proc", "eng-spa.automorf.bin"], ["apertium-tagger", "-g", "eng-spa.prob"], ["apertium-pretransfer"],
                ["apertium-transfer", "-n", "apertium-eng-spa.eng-spa.genitive.t1x", "eng-spa.genitive.bin"],
                ["lt-proc", "-b", "eng-spa.autobil.bin"], ["lrx-proc", "-m", "eng-spa.autolex.bin"],
                ["apertium-transfer", "-b", "apertium-eng-spa.eng-spa.t1x", "eng-spa.t1x.bin"],
                ["apertium-interchunk", "apertium-eng-spa.eng-spa.t2x", "eng-spa.t2x.bin"],
                ["apertium-postchunk", "apertium-eng-spa.eng-spa.t3x", "eng-spa.t3x.bin"],
                ["lt-proc", "-g", "eng-spa.autogen.bin"], ["lt-proc", "-p", "eng-spa.autopgen.bin"]],
    "fra-spa": [["lt-proc", "fra-spa.automorf.bin"], ["apertium-tagger", "-g", "fra-spa.prob"], ["apertium-pretransfer"],
                ["lt-proc", "-b", "fra-spa.autobil.bin"], ["lrx-proc", "-m", "fra-spa.autolex.bin"],
                ["apertium-transfer", "-b", "apertium-fra-spa.fra-spa.t1x", "fra-spa.t1x.bin"],
                ["apertium-interchunk", "apertium-fra-spa.fra-spa.t2x", "fra-spa.t2x.bin"],
                ["apertium-postchunk", "apertium-fra-spa.fra-spa.t3x", "fra-spa.t3x.bin"],
                ["lt-proc", "-g", "fra-spa.autogen.bin"], ["lt-proc", "-p", "fra-spa.autopgen.bin"]],
    "spa-por_PT": [["lt-proc", "es-pt.automorf.bin"], ["apertium-tagger", "-g", "es-pt.prob"], ["apertium-pretransfer"],
                   ["lt-proc", "-b", "es-pt_PT.autobil.bin"], ["apertium-transfer", "-b", "es-pt_PT.t1x", "es-pt_PT.t1x.bin"],
                   ["lt-proc", "-g", "es-pt_PT.autogen.bin"], ["lt-proc", "-p", "es-pt_PT.autopgen.bin"]],
    # bilingual in its own step (lt-proc -b): the 3.10 transfer with the embedded bilingual lost the last tag
    "spa-por": [["lt-proc", "es-pt.automorf.bin"], ["apertium-tagger", "-g", "es-pt.prob"], ["apertium-pretransfer"],
                ["lt-proc", "-b", "es-pt_BR.autobil.bin"], ["apertium-transfer", "-b", "es-pt_BR.t1x", "es-pt_BR.t1x.bin"],
                ["lt-proc", "-g", "es-pt_BR.autogen.bin"], ["lt-proc", "-p", "es-pt_BR.autopgen.bin"]],
}
AFTER = {"pt": [(r"(?i)\beste tempo\b", lambda m: "Desta vez" if m.group(0)[0].isupper() else "desta vez"),  # "this time"
                 (r"(?i)\b(oh,?) nenhum\b", r"\1 não"),  # "oh no"
                 # a state takes "estar": "the box is empty" -> "está vazia", not "é vazia"
                 (r"(?i)\b([eé]) (vazi|chei|pront|abert|fechad|mort|cansad|ferid|livre|ocupad|perdid|salv)",
                  lambda m: ("Está " if m.group(1).isupper() else "está ") + m.group(2)),
                 (r"(?i)(\w)- (lhe|lhes|lo|la|los|las|me|te|se|nos)\b", r"\1-\2"),  # loose clitic hyphen
                 (r"\bImprensa\b", "Aperte"), (r"\bimprensa\b", "aperte"), (r"\bIMPRENSA\b", "APERTE"),
                 # Spanish "fuera" after a verb is the adverb (out), not the verb "ser"
                 (r"(?i)(\w-(?:lo|la|los|las|lhe|lhes|me|te|se|nos)) (fosse)\b",
                  lambda m: m.group(1) + " " + ("FORA" if m.group(2).isupper() else "fora")),
                 (r"\bPulsar\b", "Aperte"), (r"\bpulsar\b", "aperte"), (r"\bPULSAR\b", "APERTE"),  # "press" in a game is a button
                 (r"(?i)\b(em|de|a|o|para|com|que|e) \1\b", r"\1"), (r"\bvoss([ao]s?)\b", r"su\1"), (r"\bVoss([ao]s?)\b", r"Su\1"), (r"\bsuo\b", "seu"),
                 (r"\bsuos\b", "seus"), (r"\bSuo\b", "Seu"), (r"\bSuos\b", "Seus"),
                 (r"\bGraças!", "Obrigado!"), (r"\bgraças!", "obrigado!"),
                 # a place needs "estar": "a princesa é em outro castelo" -> "está em"
                 (r"\bé (em|no|na|nos|nas|num|numa)\b", r"está \1"), (r"\bÉ (EM|NO|NA|NOS|NAS)\b", r"ESTÁ \1"),
                 (r"\bsão (em|no|na|nos|nas)\b", r"estão \1"),
                 # Spanish the second pair does not know and lets through: Portuguese spelling (SELECCIONAR -> SELECIONAR)
                 (r"(?i)(\w)(c)c(i[oó]n)", r"\1\2\3"), (r"\bLL", "CH"), (r"\bLl", "Ch"), (r"\bll", "ch"), (r"ñ", "nh"), (r"Ñ", "NH")]}


def _glossary(language):
    path_ = os.path.join(DATA, "glossary", f"{language}.json")
    return json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}


@functools.lru_cache(None)
def _route(p):
    if os.name == "nt":
        return p
    return subprocess.run(["wslpath", "-w", p], capture_output=True, text=True).stdout.strip()


def _apertium(text, pairs):
    if pairs.startswith("neural-"):  # offline neural model (neural.py) into that language, one line per sentence
        from retro_translator.core.translating import neural
        lines = [re.sub(r"\s*\.$", "", l) for l in text.split("\n")]
        return "\n".join(t + " ." for t in neural.translate(lines, SOURCE, pairs.split("-")[1]))
    for attempt in range(3):  # a program start can fail once under load (WSL interop, antivirus): try again
        try:
            return _apertium_rules(text, pairs)
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise


def _apertium_rules(text, pairs):
    value_ = subprocess.run([os.path.join(BIN, "apertium-destxt.exe")], input=text.encode("utf-8"),
                          capture_output=True, check=True, **_NO_WINDOW).stdout
    for k, (prog, *args) in enumerate(STEPS[pairs]):
        args = [_route(os.path.join(APERTIUM_DATA, a)) if os.path.exists(os.path.join(APERTIUM_DATA, a)) else a
                for a in args]
        value_ = subprocess.run([os.path.join(BIN, prog + ".exe")] + args, input=value_, capture_output=True,
                              check=True, **_NO_WINDOW).stdout
    out_ = subprocess.run([os.path.join(BIN, "apertium-retxt.exe")], input=value_, capture_output=True, check=True, **_NO_WINDOW).stdout
    return out_.decode("utf-8").strip()


def _rare(word, language):
    """A word the second pair left untranslated that is not a common word of the language ("destreza" is
    Portuguese too, "parón" is not)."""
    from wordfreq import zipf_frequency
    return zipf_frequency(word.lower(), language) < 2.5


def _back(spanish, original):
    """The English word of `original` that the first pair turned into `spanish` (or the Spanish word, if none)."""
    words = list(dict.fromkeys(re.findall(r"[A-Za-z']+", original)))
    read_ones = _apertium("\n".join(p.lower() + " ." for p in words), PATH_["es"][0]).split("\n")
    for p, l in zip(words, read_ones):
        if re.sub(r"[*#@.\s]", "", l).lower() == spanish.lower():
            return p
    return spanish


def _terms(language):
    if language not in _TERMS:
        path_ = os.path.join(DATA, "rules", f"{language}.terms.json")
        _TERMS[language] = json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}
    return _TERMS[language]


_TERMS = {}


def unknowns(texts, language="pt"):
    """For each sentence, the words Apertium does not know (marked with *) in the first pair. A single pass."""
    lines = _apertium("\n".join(" ".join(t.split()).lower() for t in texts), PATH_[language][0]).split("\n")
    if len(lines) != len(texts):
        lines = [_apertium(" ".join(t.split()).lower(), PATH_[language][0]) for t in texts]
    return [re.findall(r"\*(\w+)", l) for l in lines]


def _case_like(original, translated_):
    letters = [c for c in original if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return translated_.upper()
    return translated_[:1].upper() + translated_[1:] if original[:1].isupper() else translated_


def _rules(language):
    path_ = os.path.join(DATA, "rules", f"{language}.json")
    return json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}


def translate(text, language="pt"):
    return translate_batch([text], language)[0]


# what game fonts do not have: typographic quotes, ligatures, the French space before ?!:;
PLAIN = [(r"«\s*", '"'), (r"\s*»", '"'), ("[“”„]", '"'), ("[‘’‚]", "'"), ("œ", "oe"), ("Œ", "OE"), ("æ", "ae"),
         ("Æ", "AE"), (r"\s+([?!:;])", r"\1")]


@functools.lru_cache(maxsize=8192)
def _unknown(word):
    """A word the English dictionary does not have: a name ("Mardan", "Layton"), not a rare word ("coughs")."""
    from retro_translator.core.reading import decipher
    global _DIC
    if _DIC is None:
        _DIC = decipher.Dictionary("en")
    return _DIC(word.lower()) <= -3


_DIC = None


def _prepare(text):
    """All-uppercase text in sentence case (all caps reads as acronyms; title case made every word a name to the
    model: "Identify Yourselves" -> "Enterprises"). A word English does not use stays capitalized: a name."""
    t = " ".join(text.split())
    if t.upper() != t:
        return t
    out_, start = [], True
    for w in t.split(" "):
        core = re.sub(r"[^A-Za-z]", "", w.split("'")[0])
        low = w.lower()
        if start or core == "I" or (len(core) >= 3 and _unknown(core)):
            low = re.sub(r"[a-z]", lambda m: m.group(0).upper(), low, count=1)
        out_.append(low)
        start = bool(re.search(r"[.!?:]$", w))
    return " ".join(out_)


def _names(text):
    """A capitalized word that English barely uses is a name ("the one called Nei"; "MARDAN" even at the start of a
    sentence): our mark keeps it from being translated."""
    if text.upper() == text:
        return text
    from wordfreq import zipf_frequency

    def mark(m):
        start = not text[:m.start()].strip() or re.search(r"[.!?]\s*$", text[:m.start()])
        f = zipf_frequency(m.group(0).lower(), "en")
        return "QQ" + m.group(0) + "QQ" if f < 2 and len(m.group(0)) >= 3 or (f < 3 and not start) else m.group(0)
    return re.sub(r"\b[A-Z][a-z]+\b", mark, text)


def _tail(text):
    """The ending punctuation of a text ("...", "!", "?"): the model drops or changes it ("Respond." -> "Responda →")."""
    m = re.search(r"[.!?…]+$", text)
    return m.group(0) if m else ""


def translate_batch(texts, language="pt", with_rules=True):
    """Several sentences in a single Apertium pass (one per line): starting the programs is what costs."""
    # a button label ("A: SELECT LETTER", "C- CANCEL", "A:SELECT" with the colon read as a dash) keeps its letter:
    # alone, "A" is read as an article
    from wordfreq import zipf_frequency
    keys = [re.match(r"[A-Z]\s?[:-]\s+(?=\S)|[ABCXYZLR]\s?[:-](?=[A-Z]{2})", t) for t in texts]
    keys = [k if k and (k.group(0)[-1] != "-" or zipf_frequency(t.split()[0].lower().replace("-", ""), "en") < 1)
            else None for k, t in zip(keys, texts)]  # "X-RAY" is a word ("xray"), not the X button ("aselect")
    # the font table may read an apostrophe or a colon as a dash ("CAPTAIN-S NAME-"): the model reads them as they are
    # meant, and the dash comes back at the end so the game's own glyph draws it
    dash = [bool(re.search(r"[A-Za-z]-[Ss]\b|[A-Za-z]-$", t)) for t in texts]
    if any(dash):
        out_ = translate_batch([re.sub(r"(?<=[A-Za-z])-$", ":", re.sub(r"(?<=[A-Za-z])-(?=[Ss]\b)", "'", t)) if d
                                else t for t, d in zip(texts, dash)], language, with_rules)
        return [re.sub(r":$", "-", o) if d and o else o for o, d in zip(out_, dash)]
    if any(keys):
        out_ = translate_batch([t[k.end():] if k else t for t, k in zip(texts, keys)], language, with_rules)
        return [k.group(0) + o if k and o is not None else o for o, k in zip(out_, keys)]
    item = [len(t.split()) <= 6 and not re.search(r"[.!?,;]", t) for t in texts]  # a menu item, not a sentence
    # numbers of a menu item as 2, 3, ... in their order and put back after: "SAVE AS GAME 1" and "... GAME 2" come
    # out alike (each number alone sways the model); 0 and 1 stay, they change the grammar around them
    nums = [re.findall(r"\d+", t) if i else [] for t, i in zip(texts, item)]
    plain = [re.sub(r"\d+", lambda m, c=iter(range(2, 99)): str(next(c)), t) if n and all(int(x) > 1 for x in n)
             and len(set(n)) == len(n) else t for t, n in zip(texts, nums)]
    if plain != list(texts):
        out_ = translate_batch(plain, language, with_rules)
        for i, (o, n, p) in enumerate(zip(out_, nums, plain)):
            if o is None or p == texts[i]:
                continue
            got = re.findall(r"\d+", o)
            if sorted(got) == [str(k) for k in range(2, 2 + len(n))]:
                out_[i] = re.sub(r"\d+", lambda m, n=n: n[int(m.group(0)) - 2], o)
            else:  # the model dropped or doubled a number: the item as it is
                out_[i] = translate_batch([texts[i]], language, with_rules)[0] if not nums[i] else o
        return out_
    gloss = _glossary(language.split("-")[0])  # Portuguese of Portugal shares the Brazilian terms
    # a menu item that starts with a verb of the game glossary ("ERASE GAME 1"): the verb in the game's sense (alone,
    # the model reads "erase" as switching off), the rest translated
    verb = [i and len(t.split()) > 1 and re.fullmatch(r"[^\W\d]+(ar|er|ir|re)", gloss.get(t.split()[0].lower(), "") or "")
            and " ".join(t.lower().split()) not in gloss for t, i in zip(texts, item)]
    if any(verb):
        rest = translate_batch([t.split(None, 1)[1] if v else t for t, v in zip(texts, verb)], language, with_rules)
        return [_case_like(t.split()[0], gloss[t.split()[0].lower()]) + " " + r if v and r is not None else r
                for t, v, r in zip(texts, verb, rest)]
    out_ = [None] * len(texts)
    rest = []
    for i, t in enumerate(texts):
        key_ = " ".join(t.lower().split())
        if SOURCE != "en":  # glossary and learned terms are English keys
            pass
        elif key_ in gloss:
            out_[i] = _case_like(t, gloss[key_])
        elif _terms(language.split("-")[0]).get(key_):  # menu item in the video game sense (learn_terms.py)
            out_[i] = _case_like(t, _terms(language.split("-")[0])[key_])
        if out_[i] is not None:
            continue
        if language not in PATH_ or language == SOURCE or (re.fullmatch(r"[A-Za-z]{3,}", t.strip()) and
                                                         _unknown(t.strip())):
            out_[i] = t  # a name alone ("MARDAN") stays as it is: translated, it gets an article ("EL MARDAN")
        else:
            rest.append(i)
    if not rest:
        return out_
    # A line break is just a space to Apertium and the transfer moves words from one sentence to another:
    # " ." at the end of each holds the boundary
    tails = {i: _tail(texts[i]) for i in rest}  # put back as they came after the model
    prepared = [_names(_prepare(texts[i][:len(texts[i]) - len(tails[i])] if tails[i] and texts[i].strip(".!?…")
                                else texts[i])) for i in rest]
    current = "\n".join(p + " ." for p in prepared)
    for k, pairs in enumerate(PATH_[language]):
        current = _apertium(current, pairs)
        if k == 0 and len(PATH_[language]) > 1:  # unknown words do not survive the second pair: protect them with our own mark
            current = re.sub(r"\*(?!QQ)(\w+)", lambda m: "QQ" + m.group(1) + "QQ", current)
    lines = [re.sub(r"\s*\.\s*$", "", l.strip()) for l in current.split("\n")]
    if len(lines) != len(rest):  # Apertium joined or split lines: sentence by sentence
        for i in rest:
            out_[i] = translate_batch([texts[i]], language)[0] if len(rest) > 1 else texts[i]
        return out_
    rules = _rules(language)
    for i, current in zip(rest, lines):
        if len(PATH_[language]) > 1 and len(texts[i].split()) <= 3 and any(
                _rare(w, language) for w in re.findall(r"(?<!\*)\*(\w+)", current) if not w.startswith("QQ")):
            out_[i] = texts[i]  # a short item with a word the second pair lacks would show Spanish ("STOP" -> "PARÓN")
            continue
        rare = [w for w in re.findall(r"(?<!\*)\*(\w+)", current) if not w.startswith("QQ") and _rare(w, language)]
        if rare and len(PATH_[language]) > 1:  # longer text: only that word goes back to the English it came from
            current = re.sub(r"(?<!\*)\*(\w+)", lambda m: _back(m.group(1), texts[i]) if m.group(1) in rare
                           else "*" + m.group(1), current)
        current = re.sub(r"(?i)QQ(\w+?)QQ", r"\1", current)  # unknown words stay as they are (mostly names)
        for w in re.findall(r"QQ(\w+?)QQ", prepared[rest.index(i)]):  # the model may mangle the mark ("MardanQ")
            current = re.sub(rf"(?i)Q*{re.escape(w)}Q*", w, current)
        current = re.sub(r"Q{2,}", "", current)
        current = re.sub(r"[*#@](\w)", r"\1", current).strip()  # unknown word mark: the original word stays
        for src, to in AFTER.get(language.split("-")[0], []):
            current = re.sub(src, to, current)
        if rules and with_rules:  # learned during development (learn_rules.py), general language knowledge
            from retro_translator.core.translating import learn_rules
            current = learn_rules.join_(learn_rules.apply(learn_rules.tokens(current, box=True), rules))
        for src, to in PLAIN:
            current = re.sub(src, to, current)
        if tails[i] and texts[i].strip(".!?…"):
            current = re.sub(r"[\s.!?…→:;,]+$", "", current) + tails[i]
        elif not tails[i]:  # no full stop in the text (a line of a longer message): none added
            current = re.sub(r"\s*[.…→]+$", "", current)
        if len(texts[i].split()) == 1 and len(current.split()) == 2:  # a lone word gains no article ("O ANDROID")
            current = re.sub(r"(?i)^(o|a|os|as|el|la|los|las|le|les|un|une|uma|um)\s+", "", current)
        doubled = re.search(r"(?i)\b(\w{3,}) \1\b", current)  # "TÍTULO TÍTULO": the model stuttered
        if doubled and not re.search(r"(?i)\b(\w{3,}) \1\b", texts[i]):
            current = texts[i]
        if len(texts[i].split()) >= 6 and len(current.split()) < 0.4 * len(texts[i].split()):
            current = texts[i]  # the model collapsed ("THE THRYNN CONCERN THEMSELVES ..." -> "THRYNN."): the original
        out_[i] = _case_like(texts[i], current)
    return out_
