"""Explicit, networked provisioning only. Evidence processing never calls this module."""
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "models"
MODELS = {
    "embeddings": ("Xenova/multilingual-e5-small", "761b726dd34fb83930e26aab4e9ac3899aa1fa78"),
    "entailment": ("MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"),
}


def install(kind, source):
    repo, revision = source
    root = ROOT / kind
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "onnx/model_quantized.onnx", "README.md"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            request = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", headers={"User-Agent": "Parakh-explicit-model-provisioning"})
            temporary = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(path)
        files[name] = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    card = {
        "name": repo, "version": revision, "licence": "MIT", "files": files,
        "training_data": "Publisher pretrained multilingual retrieval corpus" if kind == "embeddings" else "Publisher MNLI and XNLI training data; see included publisher model card",
        "known_limits": ["Quantized CPU inference; scores are leads, not findings", "Hindi/Hinglish accuracy varies; no calibration on real case data", "No case data is used for training"],
        "offline_only": True, "metrics": {"label": "Pretrained model; local synthetic evaluation recorded separately"},
        "source": f"https://huggingface.co/{repo}/tree/{revision}",
    }
    (root / "manifest.json").write_text(json.dumps(card, indent=2))
    print(f"Installed and hashed {kind}: {repo}@{revision}", flush=True)


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda entry: install(*entry), MODELS.items()))
