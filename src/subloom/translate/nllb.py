"""Offline translation with NLLB-200 distilled 600M (CTranslate2)."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Sequence
from pathlib import Path

from ..asr.cuda_runtime import cuda_ready
from ..config import LocalTranslationConfig
from ..languages import nllb_code
from ..models import ModelNotReadyError, TranslationError, UnknownLanguageError
from ..paths import models_dir
from .base import Translator

log = logging.getLogger(__name__)

NLLB_REPO = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
NLLB_DIR_NAME = "nllb-200-distilled-600M-ct2-int8"
NLLB_FILES = (
    "config.json",
    "model.bin",
    "sentencepiece.bpe.model",
    "shared_vocabulary.txt",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
NLLB_SIZE_HINT = "约 650 MB"
NLLB_LICENSE = "CC BY-NC 4.0（仅限非商业用途）"

_CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def local_model_dir(config: LocalTranslationConfig | None = None) -> Path:
    if config and config.model_dir:
        return Path(config.model_dir).expanduser()
    return models_dir() / "translation" / NLLB_DIR_NAME


def local_model_available(config: LocalTranslationConfig | None = None) -> bool:
    target = local_model_dir(config)
    return (target / "model.bin").is_file() and (target / "sentencepiece.bpe.model").is_file()


def download_local_model(progress=None, config: LocalTranslationConfig | None = None) -> Path:
    target = local_model_dir(config)
    if local_model_available(config):
        return target
    target.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(f"正在下载本地翻译模型（{NLLB_SIZE_HINT}）…")
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=NLLB_REPO,
            local_dir=str(target),
            allow_patterns=list(NLLB_FILES),
        )
    except Exception as exc:
        raise ModelNotReadyError(f"本地翻译模型下载失败：{exc}") from exc
    if not local_model_available(config):
        raise ModelNotReadyError("模型下载完成，但文件不完整，请重试。")
    if progress:
        progress("本地翻译模型已就绪。")
    return target


def _clean_translation(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+([，。！？；：、）】」』》])", r"\1", text)
    text = re.sub(r"([（【「『《])\s+", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


class NLLBTranslator(Translator):
    name = "local"

    def __init__(self, config: LocalTranslationConfig):
        self.config = config
        self._translator = None
        self._sp = None
        self._lock = threading.RLock()
        self._device = "cpu"
        self._compute_type = "int8"

    @property
    def available(self) -> bool:
        return local_model_available(self.config)

    def status(self) -> tuple[bool, str]:
        if self.available:
            return True, f"NLLB-200 600M · 已下载（{NLLB_SIZE_HINT}）"
        return False, f"NLLB-200 600M · 未下载（{NLLB_SIZE_HINT}，{NLLB_LICENSE}）"

    def _resolve_runtime(self) -> tuple[str, str]:
        device = "cuda" if cuda_ready()[0] else "cpu"
        if self.config.compute_type and self.config.compute_type != "auto":
            return device, self.config.compute_type
        return device, ("int8_float16" if device == "cuda" else "int8")

    def load(self, progress=None) -> None:
        with self._lock:
            if self._translator is not None:
                return
            if not self.available:
                raise ModelNotReadyError(
                    "本地翻译模型尚未下载。\n请在设置中下载 NLLB 模型，或配置云端翻译 API。"
                )
            target = local_model_dir(self.config)
            device, compute_type = self._resolve_runtime()
            if progress:
                progress(f"正在加载本地翻译模型（{device} / {compute_type}）…")
            try:
                import ctranslate2
                import sentencepiece

                sp = sentencepiece.SentencePieceProcessor()
                # Loading from a path fails when the user's data directory
                # contains non-ASCII characters on Windows; the serialized
                # proto path avoids the narrow-string filesystem API.
                sp.load_from_serialized_proto(
                    (target / "sentencepiece.bpe.model").read_bytes()
                )
                translator = ctranslate2.Translator(
                    str(target),
                    device=device,
                    compute_type=compute_type,
                    inter_threads=1,
                    intra_threads=4,
                )
            except Exception as exc:
                if compute_type != "int8":
                    try:
                        import ctranslate2
                        import sentencepiece

                        sp = sentencepiece.SentencePieceProcessor()
                        sp.load_from_serialized_proto(
                            (target / "sentencepiece.bpe.model").read_bytes()
                        )
                        translator = ctranslate2.Translator(
                            str(target),
                            device=device,
                            compute_type="int8",
                            inter_threads=1,
                            intra_threads=4,
                        )
                        compute_type = "int8"
                    except Exception as retry_exc:
                        raise ModelNotReadyError(f"无法加载本地翻译模型：{retry_exc}") from exc
                else:
                    raise ModelNotReadyError(f"无法加载本地翻译模型：{exc}") from exc
            self._sp = sp
            self._translator = translator
            self._device = device
            self._compute_type = compute_type
            log.info("NLLB loaded on %s (%s)", device, compute_type)

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Sequence[tuple[str, str]] = (),
    ) -> str:
        del context  # NLLB is sentence-level; context is intentionally ignored.
        if source_lang == target_lang:
            return text
        with self._lock:
            self.load()
            assert self._translator is not None and self._sp is not None
            try:
                src = nllb_code(source_lang)
                tgt = nllb_code(target_lang)
            except UnknownLanguageError as exc:
                raise TranslationError(
                    f"本地 NLLB 不支持该语言：{source_lang} → {target_lang}"
                ) from exc
            # NLLB is trained with a source-language token and EOS.  The
            # target language is supplied as a decoder prefix.
            tokens = [src] + self._sp.encode_as_pieces(text) + ["</s>"]
            if len(tokens) > self.config.max_input_tokens:
                tokens = tokens[: self.config.max_input_tokens - 1] + ["</s>"]
            try:
                results = self._translator.translate_batch(
                    [tokens],
                    target_prefix=[[tgt]],
                    beam_size=max(1, self.config.beam_size),
                    max_batch_size=1,
                    batch_type="examples",
                    max_decoding_length=512,
                    return_scores=False,
                )
            except Exception as exc:
                raise TranslationError(f"本地翻译失败：{exc}") from exc
            if not results or not results[0].hypotheses:
                raise TranslationError("本地翻译没有返回结果。")
            output = list(results[0].hypotheses[0])
            if output and output[0] == tgt:
                output = output[1:]
            try:
                translated = self._sp.decode(output)
            except Exception as exc:
                raise TranslationError(f"本地翻译解码失败：{exc}") from exc
            translated = _clean_translation(translated)
            if not translated:
                raise TranslationError("本地翻译返回了空文本。")
            return translated

    def close(self) -> None:
        with self._lock:
            self._translator = None
            self._sp = None
