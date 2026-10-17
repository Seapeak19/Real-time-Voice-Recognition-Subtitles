from __future__ import annotations

from subloom.asr.language_tracker import LanguageTracker


def test_manual_language_wins():
    tracker = LanguageTracker("ja")
    assert tracker.locked == "ja"
    assert tracker.observe("en", 0.99, 5, final=True) == "ja"
    tracker.reset()
    assert tracker.locked == "ja"


def test_two_final_votes_lock_language():
    tracker = LanguageTracker("auto")
    tracker.observe("en", 0.9, 1.0, final=True)
    assert tracker.locked == ""
    tracker.observe("en", 0.92, 1.0, final=True)
    assert tracker.locked == "en"


def test_low_confidence_does_not_lock():
    tracker = LanguageTracker("auto")
    tracker.observe("en", 0.2, 1.0, final=True)
    tracker.observe("en", 0.2, 1.0, final=True)
    assert tracker.locked == ""


def test_whisper_tagalog_maps_to_filipino():
    tracker = LanguageTracker("auto")
    tracker.observe("tl", 0.9, 2.0, final=True)
    tracker.observe("tl", 0.9, 2.0, final=True)
    assert tracker.locked == "fil"
