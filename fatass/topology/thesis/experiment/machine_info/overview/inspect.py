import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from .overview import Overview as EnvInfo


def _run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _gpu_info() -> str:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    if not output:
        return "No NVIDIA GPU detected (nvidia-smi unavailable or failed)."
    lines = ["| Name | Memory | Driver |", "| --- | --- | --- |"]
    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        lines.append("| " + " | ".join(parts) + " |")
    return "\n".join(lines)


def _cuda_version() -> str:
    nvcc = _run(["nvcc", "--version"])
    if nvcc:
        for line in nvcc.splitlines():
            if "release" in line.lower():
                return line.strip()
    smi = _run(["nvidia-smi"])
    if smi:
        for line in smi.splitlines():
            if "CUDA Version" in line:
                return line.strip()
    return "Not found (nvcc/nvidia-smi unavailable)."


def _package_versions(packages: list[str]) -> str:
    lines = ["| Package | Version |", "| --- | --- |"]
    for pkg in packages:
        try:
            version = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            version = "not installed"
        lines.append(f"| {pkg} | {version} |")
    return "\n".join(lines)


def _memory_info() -> str:
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return f"{total / (1024 ** 3):.1f} GiB total"
    except (ValueError, OSError, AttributeError):
        return "Unknown"


def _disk_info() -> str:
    usage = shutil.disk_usage("/")
    return (
        f"{usage.total / (1024 ** 3):.1f} GiB total, "
        f"{usage.used / (1024 ** 3):.1f} GiB used, "
        f"{usage.free / (1024 ** 3):.1f} GiB free"
    )


def inspect():
    print("env_info.build: gathering OS/CPU/memory/disk info")
    os_section = (
        f"- **Platform**: {platform.platform()}\n"
        f"- **System**: {platform.system()} {platform.release()}\n"
        f"- **Machine**: {platform.machine()}\n"
        f"- **Processor**: {platform.processor() or 'Unknown'}\n"
        f"- **CPU count**: {os.cpu_count()}\n"
        f"- **Memory**: {_memory_info()}\n"
        f"- **Disk (/)**: {_disk_info()}\n"
    )

    print("env_info.build: gathering Python interpreter info")
    python_section = (
        f"- **Version**: {sys.version.replace(chr(10), ' ')}\n"
        f"- **Executable**: {sys.executable}\n"
    )

    print("env_info.build: gathering GPU/CUDA info")
    gpu_section = _gpu_info()
    cuda_section = _cuda_version()

    print("env_info.build: checking installed LLM-related packages")
    packages_section = _package_versions(
        [
            "torch",
            "transformers",
            "accelerate",
            "vllm",
            "deepspeed",
            "flash-attn",
            "bitsandbytes",
            "peft",
            "datasets",
            "sentencepiece",
            "numpy",
        ]
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    content = f"""# Environment Info

Generated: {timestamp}

## OS / Hardware

{os_section}
## Python

{python_section}
## GPU

{gpu_section}

**CUDA**: {cuda_section}

## Installed LLM-related packages

{packages_section}
"""

    print("env_info.build: writing _.md")
    (EnvInfo()._assets_dir() / "_.md").write_text(content, encoding="utf-8")
    print("env_info.build: done")
