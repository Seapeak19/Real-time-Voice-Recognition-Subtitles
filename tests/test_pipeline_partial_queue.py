from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from subloom.config import AppConfig
from subloom.models import CaptionSegment
from subloom.pipeline import CaptionPipeline, PipelineCallbacks


def make_segment(text: str, revision: int) -> CaptionSegment:
    return CaptionSegment(
        id="segment-1",
        source_text=text,
        source_lang="en",
        target_lang="zh",
        start=0.0,
        end=1.0,
        is_final=False,
        revision=revision,
    )


def test_partial_queue_keeps_only_latest():
    pipeline = CaptionPipeline(AppConfig(), PipelineCallbacks(on_segment=lambda _: None))
    pipeline._translation_enabled = True
    pipeline._target_lang = "zh"
    pipeline._partial_executor = ThreadPoolExecutor(max_workers=1)
    calls: queue.Queue[str] = queue.Queue()
    first_started = threading.Event()
    release_first = threading.Event()

    def fake_job(segment: CaptionSegment, context) -> None:
        calls.put(segment.source_text)
        if segment.source_text == "First sentence":
            first_started.set()
            release_first.wait(2.0)

    pipeline._translate_job = fake_job
    try:
        pipeline._revision["segment-1"] = 1
        pipeline._partial_translation_at["segment-1"] = 0.0
        pipeline._maybe_submit_partial(make_segment("First sentence", 1))
        assert first_started.wait(2.0)

        for revision, text in ((2, "Second sentence"), (3, "Third sentence")):
            pipeline._revision["segment-1"] = revision
            pipeline._partial_translation_at["segment-1"] = 0.0
            pipeline._partial_translation_text.pop("segment-1", None)
            pipeline._maybe_submit_partial(make_segment(text, revision))

        release_first.set()
        assert calls.get(timeout=2.0) == "First sentence"
        assert calls.get(timeout=2.0) == "Third sentence"
        assert calls.empty()
    finally:
        release_first.set()
        if pipeline._partial_executor is not None:
            pipeline._partial_executor.shutdown(wait=True)
        pipeline.translator.close()
        pipeline.asr.close()
