import random
from textutil import FUNC_WORDS, NEG, sentence_split

def summarize_functional_effect(text, max_sentences=3, gene_hint=None, variant_hint=None):
    if not text.strip():
        return "No functional-effect evidence found."
    sents = sentence_split(text)
    scored = []
    gh = (gene_hint or "").lower()
    vh = (variant_hint or "").lower()
    for i, s in enumerate(sents):
        s_low = s.lower()
        score = 0
        if FUNC_WORDS.search(s): score += 5
        if gh and gh in s_low: score += 2
        if vh and vh in s_low: score += 3
        if NEG.search(s): score -= 2
        if len(s) < 350: score += 0.5
        scored.append((score, i, s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [t for t in scored if t[0] > 0][:max_sentences] or scored[:max_sentences]
    top.sort(key=lambda x: x[1])
    out = [s if s.endswith(('.', '!', '?')) else s + '.' for _,_,s in top][:max_sentences]
    return " ".join(out)
