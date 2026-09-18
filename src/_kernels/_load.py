"""Lazy loader for the compiled CUDA extension."""
from __future__ import annotations

import glob
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE / "_build"


def load_ext(name: str, sources: list[str]):
    """Load a pre-built .so if present, otherwise JIT-compile via PyTorch."""
    pattern = str(BUILD_DIR / f"{name}.*.so")
    prebuilt = glob.glob(pattern)
    if prebuilt:
        spec = importlib.util.spec_from_file_location(name, prebuilt[0])
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    from torch.utils.cpp_extension import load
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return load(
        name=name,
        sources=[str(HERE / s) for s in sources],
        extra_include_paths=[str(HERE)],
        extra_cuda_cflags=["-O3"],
        verbose=False,
        build_directory=str(BUILD_DIR),
    )


_box_ext = None


def get_box_ext():
    global _box_ext
    if _box_ext is None:
        _box_ext = load_ext(
            "bt_box",
            ["box_kernel.cu", "box_leader_kernel.cu", "box_kernel.cpp"],
        )
    return _box_ext
