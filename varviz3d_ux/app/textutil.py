import re

EFFECT_VERBS = r"(increase|decrease|reduce|impair|disrupt|abolish|enhance|alter|affect|modulat|activate|inhibit|stabiliz|destabiliz|misfold|aggregate|bind|binding|splice|truncat|frameshift|clearance)"
EFFECT_TARGETS = r"(activity|function|functional|binding|affinity|expression|splicing|stability|structure|folding|aggregation|localization|trafficking|receptor|clearance|lipid|cholesterol|signaling|uptake)"
CLINICAL_NOISE = r"(odds ratio|risk|association|gwas|meta[- ]analysis|p\s*<|patients?|controls?)"
ASSAY_HINTS = r"(in vitro|in vivo|cell[- ]based|binding assay|western blot|mutagenesis)"

FUNC_RE   = re.compile(rf"\b{EFFECT_VERBS}\b", re.I)
TARGET_RE = re.compile(rf"\b{EFFECT_TARGETS}\b", re.I)
NOISE_RE  = re.compile(rf"\b{CLINICAL_NOISE}\b", re.I)
ASSAY_RE  = re.compile(ASSAY_HINTS, re.I)
PROX_RE   = re.compile(rf"({EFFECT_VERBS})(?:\W+\w+){{0,6}}\W+({EFFECT_TARGETS})", re.I)
FUNC_WORDS = PROX_RE
NEG = re.compile(r"(no effect|does not|did not|not associated|unchanged)", re.I)

def sentence_split(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text.strip()) if s.strip()]
