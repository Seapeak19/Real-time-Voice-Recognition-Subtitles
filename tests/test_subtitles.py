from __future__ import annotations

from pathlib import Path

from subloom.models import CaptionSegment
from subloom.subtitles import build_plain_text, build_srt, format_timestamp, save_srt


def seg(seg_id="a", start=1.0, end=2.5, final=True, source="hello", translated="你好"):
    return CaptionSegment(
        id=seg_id,
        source_text=source,
        translated_text=translated,
        source_lang="en",
        target_lang="zh",
        start=start,
        end=end,
        is_final=final,
        revision=1,
    )


def test_timestamp():
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(65.4321) == "00:01:05,432"
    assert format_timestamp(-2) == "00:00:00,000"


def test_srt_skips_partials_and_uses_translation():
    content = build_srt([seg(final=False), seg("b", 3, 4, source="bye", translated="再见")])
    assert "hello" not in content
    assert "再见" in content
    assert "00:00:03,000 --> 00:00:04,000" in content
    assert content.startswith("1\n")


def test_srt_bilingual():
    content = build_srt([seg()], bilingual=True)
    assert "你好\nhello" in content


def test_srt_falls_back_to_source():
    content = build_srt([seg(translated="")])
    assert "hello" in content


def test_plain_text_and_save(tmp_path: Path):
    assert build_plain_text([seg()]) == "你好\n"
    target = save_srt(tmp_path / "out.srt", [seg()])
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "你好" in raw.decode("utf-8-sig")
