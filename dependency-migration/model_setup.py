"""Prepare pinned local model assets outside measured workflow execution."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time


VLM_WEIGHTS = {
    "openvino_language_model.bin": 13929177378,
    "openvino_text_embeddings_model.bin": 1271895044,
    "openvino_vision_embeddings_model.bin": 1776440,
    "openvino_vision_embeddings_merger_model.bin": 457529956,
    "openvino_vision_embeddings_pos_model.bin": 2658820,
    "openvino_tokenizer.bin": 9631159,
    "openvino_detokenizer.bin": 3828184,
}


MODELS = {
    "qwen3.8-27b-ov": {
        "repo": "Morteza89/qwen3.8-27b-int4-ov",
        "revision": "0b379da0a1b2aa7987693b253724f19ad82928f1",
        "directory": "morteza89-qwen3.8-27b-int4-ov",
        "xml": "openvino_language_model.xml",
        "weights": VLM_WEIGHTS,
    },
    "OpenVINO/Qwen3-8B-int8-ov": {
        "repo": "OpenVINO/Qwen3-8B-int8-ov",
        "revision": "f82c978d714abc9c398efa361827a76d3cae5473",
        "directory": "qwen3-8b-int8",
        "xml": "openvino_model.xml",
        "weights": {"openvino_model.bin": 8196774677, "openvino_tokenizer.bin": 5588835, "openvino_detokenizer.bin": 2189717},
    },
    "qwen3-coder-30b-a3b-ov": {
        "repo": "OpenVINO/Qwen3-Coder-30B-A3B-Instruct-int4-ov",
        "revision": "21140c68a63012da511fe50656319e00be2f6542",
        "directory": "qwen3-coder-30b-a3b-int4-ov",
        "xml": "openvino_model.xml",
        "weights": {"openvino_model.bin": 16314043317, "openvino_tokenizer.bin": 5588835, "openvino_detokenizer.bin": 2189717},
    },
    "qwen38-fable5-int4": {
        "repo": "Morteza89/qwen3.8-27b-fable-5-coding-distilled-int4-ov",
        "revision": "6a84fb7b49812848f4541b84ae45307ad4c1fb8d",
        "directory": "qwen3.8-27b-fable-5-coding-distilled-int4-ov",
        "xml": "openvino_language_model.xml",
        "weights": VLM_WEIGHTS,
    },
}

RECEIPT = ".workflow-model-ready.json"
PENDING = ".workflow-model-download.pending"


def log(message):
    print(message, flush=True)


def safe_file(directory, name):
    target = (directory / name).resolve()
    if not target.is_relative_to(directory.resolve()):
        raise ValueError("Model manifest contains an unsafe path")
    return target


def required_files(model):
    required = {name: None for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "generation_config.json")}
    for name, size in model["weights"].items():
        required[name] = size
        required[str(Path(name).with_suffix(".xml"))] = None
    if model["xml"] == "openvino_language_model.xml":
        required["preprocessor_config.json"] = None
        required["processor_config.json"] = None
    return required


def complete(directory, model):
    if (directory / PENDING).exists():
        return False
    for name, size in required_files(model).items():
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0 or (size is not None and path.stat().st_size != size):
            return False
    receipt = directory / RECEIPT
    if receipt.exists():
        try:
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            return (
                saved["repo"] == model["repo"]
                and saved["revision"] == model["revision"]
                and bool(saved["files"])
                and all(safe_file(directory, name).is_file() and safe_file(directory, name).stat().st_size == size
                        for name, size in saved["files"].items())
            )
        except (OSError, ValueError, KeyError, TypeError):
            return False
    return True


def prepare(model_id, models_root):
    from filelock import FileLock, Timeout

    model = MODELS[model_id]
    directory = Path(models_root).resolve() / model["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(directory / ".workflow-model-setup.lock"), timeout=0):
            if complete(directory, model):
                log(f"Local model files are already available: {directory}")
                return
            log(f"Please wait: downloading the selected model from https://huggingface.co/{model['repo']}")
            log(f"Pinned revision: {model['revision']}. Destination: {directory}")
            log("Model downloads can be many GB. This preparation is outside the task time budget.")
            download(model, directory)
    except Timeout as error:
        raise RuntimeError("Another controller is preparing this model. Wait for it to finish, then retry.") from error


def download(model, directory):
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    from huggingface_hub import HfApi, hf_hub_download
    from tqdm.auto import tqdm

    class LogProgress(tqdm):
        def display(self, msg=None, pos=None):
            now = time.monotonic()
            if now - getattr(self, "last_log", 0) < 2 and self.n != self.total:
                return
            self.last_log = now
            if self.total:
                log(f"  {self.desc}: {self.n / self.total:.0%} ({self.n:,.0f}/{self.total:,.0f} {self.unit})")

    api = HfApi(endpoint="https://huggingface.co", token=False)
    info = api.model_info(model["repo"], revision=model["revision"], files_metadata=True)
    if info.sha != model["revision"]:
        raise RuntimeError("Hugging Face returned a different revision; download stopped.")
    files = {entry.rfilename: entry.size for entry in info.siblings}
    if not files or any(not isinstance(size, int) or size < 0 for size in files.values()):
        raise RuntimeError("Hugging Face did not return a complete file-size manifest.")
    if any(name not in files or files[name] == 0 or (size is not None and files[name] != size)
           for name, size in required_files(model).items()):
        raise RuntimeError("The pinned model manifest does not match the required runtime assets.")
    for name in files:
        safe_file(directory, name)
    missing_bytes = sum(size for name, size in files.items()
                        if not (directory / name).is_file() or (directory / name).stat().st_size != size)
    if shutil.disk_usage(directory).free < missing_bytes + 256 * 1024 * 1024:
        raise RuntimeError(f"Insufficient disk space: allow {missing_bytes / 1024 ** 3:.1f} GiB plus 256 MiB free, then retry.")
    (directory / PENDING).touch()
    log(f"Downloading/checking {len(files)} files ({sum(files.values()) / 1024 ** 3:.1f} GiB total). Interrupted transfers resume on retry.")
    for index, (name, size) in enumerate(files.items(), 1):
        log(f"File {index}/{len(files)}: {name} ({size / 1024 ** 2:.1f} MiB)")
        target = safe_file(directory, name)
        hf_hub_download(repo_id=model["repo"], filename=name, revision=model["revision"],
                        local_dir=directory, endpoint="https://huggingface.co", token=False,
                        force_download=target.is_file() and target.stat().st_size != size,
                        tqdm_class=LogProgress)
        if safe_file(directory, name).stat().st_size != size:
            raise RuntimeError(f"Downloaded file size mismatch: {name}. Retry preparation.")
        log(f"Completed file {index}/{len(files)}: {name}")
    receipt = directory / (RECEIPT + ".tmp")
    receipt.write_text(json.dumps({"repo": model["repo"], "revision": model["revision"], "files": files}), encoding="utf-8")
    receipt.replace(directory / RECEIPT)
    (directory / PENDING).unlink()
    log("Model download complete. Local model assets are ready.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.model, args.models_root)
    except Exception as error:
        log(f"Model preparation failed ({type(error).__name__}): {error}")
        log("No model server was started. Check the network and free disk space, then click Start selected local model to retry.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())