"""Offline neural translation for languages with no rule-based pair (Japanese, Chinese): M2M100 418M (MIT license)
converted to CTranslate2 int8, on the CPU. Japanese kana is written with kanji first (kana_kanji), or the model
misreads it. Output in Spanish; Apertium then gives Portuguese (Brazil or Portugal)."""
import os
import re
from retro_translator import DATA

MODEL = os.path.join(DATA, "neural", "m2m418")
_M = {}


def _model_dir():
    """The model folder. The executable carries it as a zip after its own files, so it is not unpacked again on every
    start (two thirds of the program): it is unpacked once per version into the user's folder, older copies go."""
    import sys
    if os.path.isdir(MODEL) or not getattr(sys, "frozen", False):
        return MODEL
    import shutil
    import zipfile
    from retro_translator import VERSION
    from retro_translator.core import preparation
    base = os.path.join(preparation.FOLDER, "neural")
    target = os.path.join(base, VERSION)
    if not os.path.exists(os.path.join(target, "done")):
        shutil.rmtree(base, ignore_errors=True)  # a copy of another version, or one cut short
        zipfile.ZipFile(sys.executable).extractall(target)
        open(os.path.join(target, "done"), "w").close()
    return os.path.join(target, "neural", "m2m418")


def _model():
    if not _M:
        import ctranslate2
        import sentencepiece
        path_ = _model_dir()
        _M["t"] = ctranslate2.Translator(path_, device="cpu", compute_type="int8")
        _M["s"] = sentencepiece.SentencePieceProcessor(os.path.join(path_, "sentencepiece.bpe.model"))
    return _M["t"], _M["s"]


def translate(sentences, source, target="es"):
    """One translation per sentence (empty ones stay empty)."""
    if source == "ja":
        from retro_translator.core.reading import kana_kanji
        sentences = [kana_kanji.convert(f) for f in sentences]
    t, s = _model()
    # one sentence at a time: given several, the model drops or garbles some ("Thank you! But..." -> "But...")
    parts = [re.findall(r".+?(?:[.!?]+[\"')]*(?=\s|$)|[。！？…]+[」』]*|[」』]|$)\s*", f.strip()) for f in sentences]
    flat = [p.strip() for ps in parts for p in ps if p.strip()]
    # a bare label ("いいえ") comes out doubled or contradicted ("No No", "No sí"); quoted, it is read as a label
    label = [source == "ja" and len(p) <= 8 and not re.search(r"[。！？…!?.]", p) for p in flat]
    toks = [[f"__{source}__"] + s.encode(f"「{p}」" if q else p, out_type=str) + ["</s>"] for p, q in zip(flat, label)]
    done = {}
    if toks:
        r = t.translate_batch(toks, target_prefix=[[f"__{target}__"]] * len(toks), beam_size=4,
                              max_decoding_length=256, max_batch_size=16)  # a whole game at once took 13 GB
        done = {k: s.decode(x.hypotheses[0][1:]) for k, x in enumerate(r)}
        done = {k: v.strip(" \"“”«»「」『』.") if label[k] else v for k, v in done.items()}
        # a word the model stutters ("Ah Ah Ah Ah") is said once, unless the source itself repeats ("ゴクゴク")
        done = {k: v if re.search(r"(..+)\1", flat[k]) else re.sub(r"(?i)\b(\w+)(?:[\s,]+\1\b){2,}", r"\1", v)
                for k, v in done.items()}
        # punctuation the model loops on ("¡¡¡¡¡") is said once; a sentence left with no letter is dropped
        done = {k: re.sub(r"[¡¿]\s*$", "", re.sub(r"([^\w\s])(?:\s*\1)+", r"\1", v)).strip() for k, v in done.items()}
        done = {k: v if re.search(r"\w", v) else "" for k, v in done.items()}
    out_, k = [], 0
    for ps in parts:
        n = sum(1 for p in ps if p.strip())
        t = " ".join(done[k + j] for j in range(n) if done[k + j])
        # the model leaves a space before punctuation ("Oh yeah . It"); French keeps it only before ? ! : ;
        out_.append(re.sub(r"\s+([.,])" if target == "fr" else r"\s+([.,!?;:])", r"\1", " ".join(t.split())))
        k += n
    return out_
