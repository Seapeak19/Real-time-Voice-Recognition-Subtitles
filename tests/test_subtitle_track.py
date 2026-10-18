from __future__ import annotations

from pathlib import Path

from subloom.subtitle_track import (
    SubtitleTrackPlayer,
    parse_subtitle_file,
    parse_timestamp,
)


def test_parse_srt(tmp_path: Path):
    path = tmp_path / "sample.srt"
    path.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello <i>world</i>\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nSecond line\n",
        encoding="utf-8",
    )
    cues = parse_subtitle_file(path)
    assert len(cues) == 2
    assert cues[0].start == 1.0
    assert cues[0].end == 3.5
    assert cues[0].text == "Hello world"
    assert cues[1].text == "Second line"


def test_parse_vtt(tmp_path: Path):
    path = tmp_path / "sample.vtt"
    path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\n你好，世界\n",
        encoding="utf-8",
    )
    cues = parse_subtitle_file(path)
    assert len(cues) == 1
    assert cues[0].start == 1.0
    assert cues[0].end == 2.5
    assert cues[0].text == "你好，世界"


def test_parse_ass(tmp_path: Path):
    path = tmp_path / "sample.ass"
    path.write_text(
        "[Script Info]\nTitle: test\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:02.50,Default,,0,0,0,,{\\i1}Hello,{\\i0} world\n",
        encoding="utf-8",
    )
    cues = parse_subtitle_file(path)
    assert len(cues) == 1
    assert cues[0].start == 1.0
    assert cues[0].end == 2.5
    assert cues[0].text == "Hello, world"


def test_parse_utf16_srt(tmp_path: Path):
    path = tmp_path / "utf16.srt"
    path.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n你好，世界\n",
        encoding="utf-16",
    )
    cues = parse_subtitle_file(path)
    assert len(cues) == 1
    assert cues[0].text == "你好，世界"


def test_parse_timestamp_accepts_srt_and_ass():
    assert parse_timestamp("00:00:01,500") == 1.5
    assert parse_timestamp("0:00:01.50") == 1.5
    assert parse_timestamp("01:02.250") == 62.25


def test_player_cue_at():
    from subloom.subtitle_track import SubtitleCue

    player = SubtitleTrackPlayer()
    player.set_cues(
        [
            SubtitleCue(1.0, 2.0, "first"),
            SubtitleCue(3.0, 4.0, "second"),
        ]
    )
    assert player.cue_at(0.5)[1] is None
    assert player.cue_at(1.5)[1].text == "first"  # type: ignore[union-attr]
    assert player.cue_at(3.5)[1].text == "second"  # type: ignore[union-attr]
    assert player.cue_at(5.0)[1] is None
