"""Windows CUDA runtime discovery for CTranslate2.

The PyPI CTranslate2 wheel does not bundle cuBLAS/cuDNN.  If the optional
``nvidia-*`` wheels are installed we preload their DLLs explicitly; merely
calling ``os.add_dll_directory`` is not enough on Windows because CTranslate2
loads its dependencies lazily by name.  Users with a full CUDA toolkit on PATH
continue to work without the optional wheels.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import sysconfig
from pathlib import Path

log = logging.getLogger(__name__)

_configured = False
_cuda_ok: bool | None = None
_cuda_error = ""
_dll_handles: list[object] = []
_loaded_dlls: list[object] = []
_dirs_cache: list[Path] | None = None

# Loaded in dependency order.  Missing entries are skipped.
_DLL_NAMES = (
    "cublasLt64_12.dll",
    "cublas64_12.dll",
    "cudnn64_9.dll",
    "cudnn_graph64_9.dll",
    "cudnn_ops64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
)


def _site_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    try:
        roots.append(Path(sysconfig.get_paths()["purelib"]))
    except Exception:
        pass
    try:
        roots.append(Path(sysconfig.get_paths()["platlib"]))
    except Exception:
        pass
    for entry in sys.path:
        if entry and entry.endswith("site-packages"):
            roots.append(Path(entry))
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen and root.is_dir():
            seen.add(key)
            unique.append(root)
    return unique


def _nvidia_bin_dirs() -> list[Path]:
    global _dirs_cache
    if _dirs_cache is not None:
        return _dirs_cache
    dirs: list[Path] = []
    for root in _site_roots():
        nvidia = root / "nvidia"
        if not nvidia.is_dir():
            continue
        for package in ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime", "cufft", "curand"):
            candidate = nvidia / package / "bin"
            if candidate.is_dir():
                dirs.append(candidate)
    # A system CUDA toolkit may also be available.
    for env in ("CUDA_PATH", "CUDA_HOME"):
        value = os.environ.get(env)
        if value:
            candidate = Path(value) / "bin"
            if candidate.is_dir():
                dirs.append(candidate)
    _dirs_cache = dirs
    return dirs


def configure() -> None:
    global _configured
    if _configured or sys.platform != "win32":
        _configured = True
        return
    _configured = True
    for path in _nvidia_bin_dirs():
        try:
            _dll_handles.append(os.add_dll_directory(str(path)))
        except OSError:
            log.debug("Could not add DLL directory %s", path, exc_info=True)
    for name in _DLL_NAMES:
        for directory in _nvidia_bin_dirs():
            candidate = directory / name
            if not candidate.is_file():
                continue
            try:
                _loaded_dlls.append(ctypes.WinDLL(str(candidate)))
                break
            except OSError as exc:
                log.debug("Could not preload %s: %s", candidate, exc)
    if _loaded_dlls:
        log.info("Preloaded CUDA runtime DLLs from nvidia wheels")


def _dll_loadable(name: str) -> bool:
    try:
        ctypes.WinDLL(name)
        return True
    except OSError:
        return False


def cuda_ready() -> tuple[bool, str]:
    """Return ``(usable, reason)`` without allocating a model."""
    global _cuda_ok, _cuda_error
    if _cuda_ok is not None:
        return _cuda_ok, _cuda_error
    if sys.platform != "win32":
        # macOS has no CUDA; Linux wheels usually carry proper RUNPATHs.
        try:
            import ctranslate2

            _cuda_ok = ctranslate2.get_cuda_device_count() > 0
            _cuda_error = "" if _cuda_ok else "未检测到 CUDA 设备"
        except Exception as exc:
            _cuda_ok = False
            _cuda_error = f"CUDA 不可用：{exc}"
        return _cuda_ok, _cuda_error
    configure()
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() <= 0:
            _cuda_ok = False
            _cuda_error = "未检测到 NVIDIA CUDA 设备"
            return _cuda_ok, _cuda_error
        # get_supported_compute_types() can succeed even when the lazy-loaded
        # cuBLAS/cuDNN DLLs are absent, so verify the core libraries explicitly.
        has_cublas = any(_dll_loadable(name) for name in ("cublas64_12.dll", "cublas64_11.dll"))
        has_cudnn = any(_dll_loadable(name) for name in ("cudnn64_9.dll", "cudnn64_8.dll"))
        if not has_cublas or not has_cudnn:
            missing = []
            if not has_cublas:
                missing.append("cuBLAS")
            if not has_cudnn:
                missing.append("cuDNN")
            _cuda_ok = False
            _cuda_error = f"缺少 CUDA 运行库：{' / '.join(missing)}"
            return _cuda_ok, _cuda_error
        # This validates that the CUDA backend can be initialised, but not
        # every lazily-loaded DLL.  The preload above covers the common case.
        types = ctranslate2.get_supported_compute_types("cuda")
        if not types:
            raise RuntimeError("CUDA 后端没有可用的计算精度")
        _cuda_ok = True
        _cuda_error = ""
    except Exception as exc:
        _cuda_ok = False
        _cuda_error = str(exc)
        log.warning("CUDA runtime unavailable: %s", exc)
    return _cuda_ok, _cuda_error


def cuda_device_count() -> int:
    configure()
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def install_hint() -> str:
    if getattr(sys, "frozen", False):
        return (
            "当前运行的是 CPU 安装包，它不包含 CUDA 运行库。\n"
            "请改用 GPU 版安装包，或使用源码版：\n"
            "  python -m subloom\n"
            "也可以在设置中把计算设备改为“自动”或 CPU。"
        )
    return (
        "GPU 加速需要 CUDA 12 运行库。Windows 可执行：\n"
        '  pip install "subloom[gpu]"\n'
        "或只安装：pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
    )
