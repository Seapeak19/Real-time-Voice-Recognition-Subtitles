from __future__ import annotations

from subloom.languages import (
    BY_CODE,
    from_whisper,
    get_language,
    is_rtl,
    language_name,
    nllb_code,
    normalize_code,
    whisper_code,
)


def test_normalize_aliases():
    assert normalize_code("zh-CN") == "zh"
    assert normalize_code("zh_TW") == "zh-Hant"
    assert normalize_code("pt-BR") == "pt"
    assert normalize_code("iw") == "he"
    assert normalize_code("tl") == "fil"


def test_whisper_mapping_keeps_simplified_chinese():
    assert from_whisper("zh").code == "zh"
    assert from_whisper("tl").code == "fil"
    assert from_whisper("en").code == "en"


def test_nllb_codes():
    assert nllb_code("zh") == "zho_Hans"
    assert nllb_code("zh-Hant") == "zho_Hant"
    assert nllb_code("en") == "eng_Latn"
    assert nllb_code("ja") == "jpn_Jpan"


def test_display_and_rtl():
    assert language_name("ja") == "日语"
    assert language_name("ja", "en") == "Japanese"
    assert is_rtl("ar")
    assert not is_rtl("en")


def test_unknown_code_is_safe():
    assert get_language("not-a-language") is None
    assert normalize_code("not-a-language") == "not-a-language"
    assert language_name("xx") == "xx"


def test_all_targets_have_unique_codes():
    codes = [lang.code for lang in BY_CODE.values()]
    assert len(codes) == len(set(codes))
    assert whisper_code("zh-Hant") == "zh"
