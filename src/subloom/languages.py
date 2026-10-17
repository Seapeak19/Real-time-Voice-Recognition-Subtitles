"""Language registry shared by ASR, translation, and the UI.

Internal codes intentionally follow Whisper's short codes (``zh``, ``en`` …).
NLLB uses BCP-47-like codes (``zho_Hans``), which are mapped here so the rest
of the app never has to care about either model's idiosyncrasies.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import UnknownLanguageError


@dataclass(frozen=True, slots=True)
class Language:
    code: str
    name_zh: str
    name_en: str
    nllb: str
    whisper: str = ""
    rtl: bool = False

    @property
    def whisper_code(self) -> str:
        return self.whisper or self.code


# Ordered roughly by likely audience.  Add a row here to expose a new target
# language in both the ASR and translation layers.
LANGUAGES: tuple[Language, ...] = (
    Language("zh", "简体中文", "Chinese (Simplified)", "zho_Hans"),
    Language("zh-Hant", "繁體中文", "Chinese (Traditional)", "zho_Hant", whisper="zh"),
    Language("en", "英语", "English", "eng_Latn"),
    Language("ja", "日语", "Japanese", "jpn_Jpan"),
    Language("ko", "韩语", "Korean", "kor_Hang"),
    Language("es", "西班牙语", "Spanish", "spa_Latn"),
    Language("fr", "法语", "French", "fra_Latn"),
    Language("de", "德语", "German", "deu_Latn"),
    Language("ru", "俄语", "Russian", "rus_Cyrl"),
    Language("pt", "葡萄牙语", "Portuguese", "por_Latn"),
    Language("it", "意大利语", "Italian", "ita_Latn"),
    Language("ar", "阿拉伯语", "Arabic", "arb_Arab", rtl=True),
    Language("hi", "印地语", "Hindi", "hin_Deva"),
    Language("th", "泰语", "Thai", "tha_Thai"),
    Language("vi", "越南语", "Vietnamese", "vie_Latn"),
    Language("id", "印度尼西亚语", "Indonesian", "ind_Latn"),
    Language("tr", "土耳其语", "Turkish", "tur_Latn"),
    Language("nl", "荷兰语", "Dutch", "nld_Latn"),
    Language("pl", "波兰语", "Polish", "pol_Latn"),
    Language("uk", "乌克兰语", "Ukrainian", "ukr_Cyrl"),
    Language("sv", "瑞典语", "Swedish", "swe_Latn"),
    Language("ms", "马来语", "Malay", "zsm_Latn"),
    Language("fa", "波斯语", "Persian", "pes_Arab", rtl=True),
    Language("he", "希伯来语", "Hebrew", "heb_Hebr", rtl=True),
    Language("el", "希腊语", "Greek", "ell_Grek"),
    Language("cs", "捷克语", "Czech", "ces_Latn"),
    Language("da", "丹麦语", "Danish", "dan_Latn"),
    Language("fi", "芬兰语", "Finnish", "fin_Latn"),
    Language("no", "挪威语", "Norwegian", "nob_Latn"),
    Language("ro", "罗马尼亚语", "Romanian", "ron_Latn"),
    Language("hu", "匈牙利语", "Hungarian", "hun_Latn"),
    Language("bg", "保加利亚语", "Bulgarian", "bul_Cyrl"),
    Language("sk", "斯洛伐克语", "Slovak", "slk_Latn"),
    Language("hr", "克罗地亚语", "Croatian", "hrv_Latn"),
    Language("sr", "塞尔维亚语", "Serbian", "srp_Cyrl"),
    Language("sl", "斯洛文尼亚语", "Slovenian", "slv_Latn"),
    Language("ca", "加泰罗尼亚语", "Catalan", "cat_Latn"),
    Language("fil", "菲律宾语", "Filipino", "tgl_Latn", whisper="tl"),
    Language("sw", "斯瓦希里语", "Swahili", "swh_Latn"),
    Language("ta", "泰米尔语", "Tamil", "tam_Taml"),
    Language("te", "泰卢固语", "Telugu", "tel_Telu"),
    Language("ur", "乌尔都语", "Urdu", "urd_Arab", rtl=True),
    Language("bn", "孟加拉语", "Bengali", "ben_Beng"),
    Language("et", "爱沙尼亚语", "Estonian", "est_Latn"),
    Language("lt", "立陶宛语", "Lithuanian", "lit_Latn"),
    Language("lv", "拉脱维亚语", "Latvian", "lvs_Latn"),
    Language("is", "冰岛语", "Icelandic", "isl_Latn"),
    Language("mk", "马其顿语", "Macedonian", "mkd_Cyrl"),
    Language("sq", "阿尔巴尼亚语", "Albanian", "sqi_Latn"),
    Language("af", "南非荷兰语", "Afrikaans", "afr_Latn"),
)

BY_CODE: dict[str, Language] = {lang.code: lang for lang in LANGUAGES}
# Whisper reports ``tl`` for Tagalog/Filipino, while our public code is ``fil``.
BY_WHISPER: dict[str, Language] = {}
for _lang in LANGUAGES:
    BY_WHISPER.setdefault(_lang.whisper_code, _lang)
BY_WHISPER["zh"] = BY_CODE["zh"]
BY_WHISPER["tl"] = BY_CODE["fil"]

TARGET_LANGUAGES: tuple[Language, ...] = LANGUAGES
DEFAULT_TARGET = "zh"

_ALIASES = {
    "cmn": "zh",
    "zh-cn": "zh",
    "zh-hans": "zh",
    "zh-sg": "zh",
    "zh-tw": "zh-Hant",
    "zh-hk": "zh-Hant",
    "zh-hant": "zh-Hant",
    "iw": "he",
    "in": "id",
    "nb": "no",
    "nn": "no",
    "pt-br": "pt",
    "es-419": "es",
    "tl": "fil",
    "jw": "id",
}


def normalize_code(code: str | None) -> str:
    """Normalize a language code to one used by this project."""
    if not code:
        return ""
    raw = code.strip().replace("_", "-")
    lower = raw.lower()
    if lower in _ALIASES:
        return _ALIASES[lower]
    if raw in BY_CODE:
        return raw
    if lower in BY_CODE:
        return lower
    base = lower.split("-", 1)[0]
    if base in BY_CODE:
        return base
    return lower


def get_language(code: str | None) -> Language | None:
    normalized = normalize_code(code)
    return BY_CODE.get(normalized)


def require_language(code: str | None) -> Language:
    lang = get_language(code)
    if lang is None:
        raise UnknownLanguageError(f"Unsupported language code: {code!r}")
    return lang


def from_whisper(code: str | None) -> Language | None:
    if not code:
        return None
    return BY_WHISPER.get(code.lower())


def language_name(code: str | None, ui: str = "zh") -> str:
    lang = get_language(code)
    if lang is None:
        return code or "未知"
    return lang.name_en if ui == "en" else lang.name_zh


def nllb_code(code: str | None) -> str:
    return require_language(code).nllb


def whisper_code(code: str | None) -> str | None:
    lang = get_language(code)
    return lang.whisper_code if lang else None


def is_rtl(code: str | None) -> bool:
    lang = get_language(code)
    return bool(lang and lang.rtl)


def language_choices() -> list[tuple[str, str]]:
    """Return ``(label, code)`` pairs for combo boxes."""
    return [(f"{lang.name_zh}  ·  {lang.name_en}", lang.code) for lang in TARGET_LANGUAGES]
