"""
Keyword extraction from channel + video metadata.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "to", "of", "in", "for", "on",
    "with", "at", "by", "from", "as", "into", "through", "about", "against", "this",
    "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "what",
    "which", "who", "whom", "my", "your", "his", "her", "its", "our", "their", "me",
    "him", "us", "them", "if", "then", "else", "so", "than", "too", "very", "just",
    "more", "most", "some", "any", "all", "no", "not", "only", "own", "same", "such",
    "now", "here", "there", "when", "where", "why", "how", "out", "up", "down", "off",
    "và", "của", "là", "có", "không", "được", "đã", "đang", "sẽ", "này", "đó", "với",
    "cho", "từ", "để", "trong", "ngoài", "trên", "dưới", "khi", "nào", "thì", "mà",
    "nếu", "rồi", "vẫn", "cũng", "rất", "quá", "lắm", "nhé", "nha", "ạ", "ơi",
    "tôi", "bạn", "anh", "chị", "em", "họ", "chúng", "mình", "ta", "ai", "gì", "đâu",
    "sao", "vì", "bởi", "do", "nên", "hay", "hoặc", "một", "hai", "ba", "những", "các",
    "video", "youtube", "subscribe", "like", "channel", "official", "feat", "ft",
    "vlog", "vlogs", "ep", "episode", "part", "full", "hd", "4k", "1080p", "shorts",
    "短", "mv", "trailer", "review", "tập", "phần",
}

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HASHTAG_RE = re.compile(r"#\w+")
_NON_WORD_RE = re.compile(r"[^\w\sÀ-ɏḀ-ỿ]", flags=re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class KeywordEntry:
    keyword: str
    score: float = 0.0
    sources: set = field(default_factory=set)
    channel_video_count: int = 0


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = _URL_RE.sub(" ", text)
    t = _HASHTAG_RE.sub(" ", t)
    t = _NON_WORD_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t)
    return t.strip().lower()


def _is_vietnamese(text: str) -> bool:
    return any(c in text for c in "ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")


def _detect_language(text: str) -> str:
    """Phát hiện ngôn ngữ chính của text dựa trên ký tự.
    Trả mã 2 chữ tương thích với YAKE: en, vi, ja, zh (cn), ko (kr), th, ru,
    ar, es, fr, de, pt, it, hi, ...
    """
    if not text:
        return "en"

    # Đếm số ký tự theo từng script
    counts = {
        "vi": 0, "ja_hira": 0, "ja_kata": 0, "zh": 0, "ko": 0, "th": 0,
        "ru": 0, "ar": 0, "hi": 0, "latin": 0,
    }
    for c in text:
        cp = ord(c)
        # Vietnamese diacritics
        if c in "ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ":
            counts["vi"] += 1
        elif 0x3040 <= cp <= 0x309F:  # Hiragana
            counts["ja_hira"] += 1
        elif 0x30A0 <= cp <= 0x30FF:  # Katakana
            counts["ja_kata"] += 1
        elif 0xAC00 <= cp <= 0xD7AF:  # Hangul
            counts["ko"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:  # CJK Unified Ideographs
            counts["zh"] += 1
        elif 0x0E00 <= cp <= 0x0E7F:  # Thai
            counts["th"] += 1
        elif 0x0400 <= cp <= 0x04FF:  # Cyrillic
            counts["ru"] += 1
        elif 0x0600 <= cp <= 0x06FF:  # Arabic
            counts["ar"] += 1
        elif 0x0900 <= cp <= 0x097F:  # Devanagari (Hindi)
            counts["hi"] += 1
        elif c.isalpha() and cp < 0x024F:  # Latin script
            counts["latin"] += 1

    # Vietnamese: cần diacritics đặc trưng
    if counts["vi"] >= 3:
        return "vi"
    # Japanese: có Hiragana hoặc Katakana
    if counts["ja_hira"] + counts["ja_kata"] >= 5:
        return "ja"
    # Korean: Hangul
    if counts["ko"] >= 5:
        return "ko"
    # Chinese: CJK ideographs mà không có Hiragana (vì Hiragana = Japanese)
    if counts["zh"] >= 5 and counts["ja_hira"] < 3:
        return "zh"
    if counts["th"] >= 5:
        return "th"
    if counts["ru"] >= 5:
        return "ru"
    if counts["ar"] >= 5:
        return "ar"
    if counts["hi"] >= 5:
        return "hi"

    # Latin: heuristic dùng word-boundary regex để phân biệt en/es/fr/de/pt/it
    lower = text.lower()
    # Mỗi ngôn ngữ: list (regex_or_substring, weight)
    # Diacritics đặc trưng có weight cao hơn vì chính xác hơn
    lang_hints = {
        "es": [(r"\b(el|la|los|las|un|una|que|es|está|por|para|con|sin|de|y|o|pero|muy|más|también|cómo|vamos|preparar|hacer|hoy|hola)\b", 1),
               ("ción", 3), ("ñ", 3), ("¿", 5), ("¡", 5)],
        "fr": [(r"\b(le|la|les|une|des|est|être|pour|avec|dans|sur|qui|que)\b", 1),
               ("ç", 3), ("œ", 5), (r"\b(c'est|qu'est|aujourd'hui|n'est)\b", 3)],
        "de": [(r"\b(der|die|das|und|ist|nicht|ein|eine|wie|mit|für|von|zu|man|euch)\b", 1),
               ("ß", 5), ("ä", 2), ("ö", 2), ("ü", 2)],
        "pt": [(r"\b(de|da|do|que|os|uma|um|para|com|não|por)\b", 1),
               ("ção", 3), ("ã", 2), ("õ", 3)],
        "it": [(r"\b(il|lo|la|gli|le|è|sono|della|del|che|con|per)\b", 1),
               ("à", 2), ("è", 2), ("ì", 2)],
    }
    scores = {}
    for lang, hints in lang_hints.items():
        s = 0
        for pat, weight in hints:
            if pat.startswith("\\b") or "\\b" in pat:
                s += weight * len(re.findall(pat, lower))
            else:
                s += weight * lower.count(pat)
        scores[lang] = s
    best = max(scores.items(), key=lambda x: x[1])
    # Threshold phải đủ cao để loại nhiễu khi text mostly English
    if best[1] >= 3:
        return best[0]
    return "en"


# YAKE hỗ trợ các ngôn ngữ này; map về code YAKE nếu khác
_YAKE_LANG_MAP = {
    "vi": "vi", "en": "en", "es": "es", "pt": "pt", "fr": "fr",
    "de": "de", "it": "it", "nl": "nl", "ar": "ar", "ru": "ru",
    "ja": "ja", "zh": "zh", "ko": "ko", "hi": "hi", "tr": "tr",
    "pl": "pl", "th": "en",  # YAKE không có Thai, fallback en
}


# Stopwords bổ sung cho các ngôn ngữ phổ biến (để dùng khi ngram fallback)
_EXTRA_STOPWORDS = {
    "es": {"el", "la", "los", "las", "un", "una", "y", "o", "pero", "de",
           "del", "en", "que", "es", "son", "para", "por", "con", "se",
           "no", "lo", "le", "te", "me"},
    "fr": {"le", "la", "les", "un", "une", "des", "et", "ou", "mais",
           "de", "du", "en", "que", "est", "sont", "pour", "par",
           "avec", "ce", "ne", "pas", "je", "tu"},
    "de": {"der", "die", "das", "ein", "eine", "und", "oder", "aber",
           "von", "zu", "in", "auf", "ist", "sind", "mit", "ich", "du",
           "er", "sie", "es", "wir"},
    "pt": {"o", "a", "os", "as", "um", "uma", "e", "ou", "mas",
           "de", "da", "do", "em", "que", "é", "para", "por",
           "com", "se", "não", "lo"},
    "it": {"il", "la", "lo", "gli", "le", "un", "una", "e", "o", "ma",
           "di", "da", "in", "che", "è", "sono", "per", "con", "non"},
    "ru": {"и", "в", "на", "не", "что", "он", "она", "это", "с", "как",
           "за", "по", "у", "из", "к", "от", "до"},
    "ar": {"في", "من", "إلى", "على", "هذا", "هذه", "ذلك", "أن", "ما",
           "لا", "هو", "هي"},
    "ja": {"の", "に", "は", "を", "た", "が", "で", "と", "し", "も",
           "ある", "いる", "する", "なる", "これ", "それ"},
    "ko": {"이", "그", "저", "은", "는", "을", "를", "에", "에서",
           "와", "과", "도", "만", "의", "에게"},
    "zh": {"的", "了", "在", "是", "我", "你", "他", "她", "这", "那",
           "和", "也", "都", "就", "不"},
    "th": {"และ", "หรือ", "แต่", "ใน", "ที่", "ของ", "เป็น", "มี"},
    "hi": {"का", "की", "के", "है", "हैं", "में", "और", "से", "एक",
           "यह", "वह", "जो"},
}


def _ngram_keywords(text: str, top_n: int = 50, lang: str = "en"):
    norm = _normalize(text)
    if not norm:
        return []
    # Gộp stopwords: chung + theo ngôn ngữ phát hiện được
    stop = set(_STOPWORDS) | _EXTRA_STOPWORDS.get(lang, set())
    tokens = [t for t in norm.split() if t and t not in stop and len(t) > 1]
    counts: Counter = Counter()
    for tok in tokens:
        counts[tok] += 1
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i:i + n])
            if any(t in stop for t in gram.split()):
                continue
            counts[gram] += 1
    items = counts.most_common(top_n)
    if not items:
        return []
    max_count = items[0][1]
    return [(term, count / max_count) for term, count in items]


def _yake_keywords(text: str, top_n: int = 50, lang: str = "en"):
    try:
        import yake
    except ImportError:
        return []
    if not text.strip():
        return []
    # Map về code YAKE hỗ trợ; fallback "en" nếu không hỗ trợ
    yake_lang = _YAKE_LANG_MAP.get(lang, "en")
    try:
        kw_extractor = yake.KeywordExtractor(
            lan=yake_lang,
            n=3,
            dedupLim=0.7,
            top=top_n,
        )
        results = kw_extractor.extract_keywords(text)
        if not results:
            return []
        max_score = max(s for _, s in results) or 1.0
        return [(term, 1.0 - (s / max_score)) for term, s in results]
    except Exception:
        # YAKE có thể không có file stopwords cho lang này
        if yake_lang != "en":
            try:
                kw_extractor = yake.KeywordExtractor(lan="en", n=3,
                                                      dedupLim=0.7, top=top_n)
                results = kw_extractor.extract_keywords(text)
                if not results:
                    return []
                max_score = max(s for _, s in results) or 1.0
                return [(term, 1.0 - (s / max_score)) for term, s in results]
            except Exception:
                return []
        return []


def _vietnamese_keywords(text: str, top_n: int = 50):
    """Trích từ khoá tiếng Việt dùng pyvi - tokenize từ ghép (compound words).
    Trả [(term, score), ...]."""
    try:
        from pyvi import ViTokenizer
    except ImportError:
        return []
    if not text.strip():
        return []

    try:
        # pyvi gắn _ giữa các từ ghép: "phở bò ngon" → "phở_bò ngon"
        tokenized = ViTokenizer.tokenize(text.lower())
    except Exception:
        return []

    tokens = []
    for tok in tokenized.split():
        # Bỏ ký tự đặc biệt nhưng giữ chữ tiếng Việt + underscore
        tok = re.sub(r"[^\wÀ-ɏḀ-ỿ_]", "", tok, flags=re.UNICODE)
        if not tok or len(tok) < 2:
            continue
        if tok in _STOPWORDS:
            continue
        # Đổi _ → space để hiển thị "phở bò" thay vì "phở_bò"
        tokens.append(tok.replace("_", " "))

    if not tokens:
        return []

    counts: Counter = Counter()
    # Unigram (mỗi token là 1 cụm từ tiếng Việt có thể là từ ghép)
    for tok in tokens:
        counts[tok] += 1
    # Bigram: 2 tokens kế nhau
    for i in range(len(tokens) - 1):
        gram = " ".join(tokens[i:i + 2])
        if all(t not in _STOPWORDS for t in gram.split()):
            counts[gram] += 1

    items = counts.most_common(top_n)
    if not items:
        return []
    max_count = items[0][1]
    return [(term, count / max_count) for term, count in items]


def extract_keywords(
    channel_keywords: Iterable[str],
    video_tags: Iterable,
    video_titles: Iterable[str],
    video_descriptions: Iterable[str],
    top_n: int = 20,
) -> list:
    entries: dict = {}

    def _bump(kw: str, source: str, score: float):
        k = kw.strip().lower()
        if not k or len(k) < 2:
            return
        if k in _STOPWORDS:
            return
        if k not in entries:
            entries[k] = KeywordEntry(keyword=kw.strip(), score=0.0, sources=set())
        entries[k].sources.add(source)
        entries[k].score += score

    for kw in channel_keywords or []:
        _bump(kw, "creator-tag", 3.0)

    tag_counter: Counter = Counter()
    for tags in video_tags or []:
        for tag in (tags or []):
            tag_counter[tag.strip().lower()] += 1
    for tag_lower, count in tag_counter.most_common():
        _bump(tag_lower, "creator-tag", 2.0 + count * 0.1)

    blob_titles = " ".join(t for t in video_titles if t)
    blob_desc = " ".join((d or "")[:1000] for d in video_descriptions)
    blob = (blob_titles + " " + blob_desc).strip()
    lang = _detect_language(blob)

    # Tiếng Việt: dùng pyvi để tokenize từ ghép trước
    if lang == "vi":
        vi_results = _vietnamese_keywords(blob, top_n=60)
        if vi_results:
            for term, sc in vi_results:
                _bump(term, "pyvi", 1.4 * sc)
            # Vẫn thử YAKE để bổ sung
            yake_results = _yake_keywords(blob, top_n=30, lang=lang)
            for term, sc in yake_results:
                _bump(term, "yake", 0.8 * sc)
        else:
            # Fallback nếu pyvi không khả dụng
            yake_results = _yake_keywords(blob, top_n=50, lang=lang)
            if yake_results:
                for term, sc in yake_results:
                    _bump(term, "yake", 1.5 * sc)
            else:
                for term, sc in _ngram_keywords(blob, top_n=80):
                    _bump(term, "ngram", 1.0 * sc)
    else:
        yake_results = _yake_keywords(blob, top_n=50, lang=lang)
        if yake_results:
            for term, sc in yake_results:
                _bump(term, "yake", 1.5 * sc)
        else:
            for term, sc in _ngram_keywords(blob, top_n=80, lang=lang):
                _bump(term, "ngram", 1.0 * sc)

    title_blobs = [(t or "").lower() for t in video_titles]
    tag_sets = [set((tag or "").lower() for tag in tags) for tags in video_tags]
    for k, ent in entries.items():
        count = 0
        for i in range(len(title_blobs)):
            in_title = k in title_blobs[i] if i < len(title_blobs) else False
            in_tags = k in tag_sets[i] if i < len(tag_sets) else False
            if in_title or in_tags:
                count += 1
        ent.channel_video_count = count

    deduped = _dedupe(list(entries.values()))
    deduped.sort(key=lambda e: e.score, reverse=True)
    return deduped[:top_n]


def _dedupe(items: list) -> list:
    items_sorted = sorted(items, key=lambda e: e.score, reverse=True)
    kept = []
    seen_norm = set()
    for e in items_sorted:
        norm = re.sub(r"s$", "", e.keyword.lower())
        if norm in seen_norm:
            continue
        is_substring_of_kept = any(
            (e.keyword.lower() != k.keyword.lower())
            and (e.keyword.lower() in k.keyword.lower())
            and (len(e.keyword) < len(k.keyword) - 2)
            for k in kept
        )
        if is_substring_of_kept:
            continue
        seen_norm.add(norm)
        kept.append(e)
    return kept
