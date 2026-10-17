from __future__ import annotations

from subloom.models import CaptionSegment
from subloom.transcript import TranscriptStore


def segment(revision=1, final=False, translated=""):
    return CaptionSegment(
        id="s1",
        source_text="hello",
        translated_text=translated,
        source_lang="en",
        target_lang="zh",
        start=0,
        end=1,
        is_final=final,
        revision=revision,
    )


def test_partial_then_final_then_translation():
    store = TranscriptStore()
    store.upsert(segment(1, False))
    store.upsert(segment(2, True))
    store.upsert(segment(2, True, "你好"))
    assert len(store.segments) == 1
    assert store.segments[0].is_final
    assert store.segments[0].translated_text == "你好"


def test_stale_translation_is_ignored():
    store = TranscriptStore()
    store.upsert(segment(2, True))
    store.upsert(segment(2, True, "你好"))
    store.upsert(segment(1, False, "旧翻译"))
    assert store.segments[0].translated_text == "你好"


def test_new_hypothesis_clears_old_translation():
    store = TranscriptStore()
    store.upsert(segment(1, False, "第一版"))
    store.upsert(segment(2, False))
    assert store.segments[0].translated_text == ""


def test_exports_only_final():
    store = TranscriptStore()
    store.upsert(segment(1, False, "草稿"))
    store.upsert(segment(2, True, "完成"))
    assert "草稿" not in store.srt()
    assert "完成" in store.srt()
