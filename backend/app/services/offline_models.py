"""Hash-checked local ONNX inference. There is deliberately no download API here."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2] / "data" / "models"


class ModelUnavailable(RuntimeError):
    pass


class OfflineModel:
    def __init__(self, kind: str):
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise ModelUnavailable("Install the offline-ml Python dependencies") from exc
        ort.disable_telemetry_events()
        root = ROOT / kind
        try:
            self.card = json.loads((root / "manifest.json").read_text())
            for name, expected in self.card["files"].items():
                path = (root / name).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ModelUnavailable("Invalid model manifest path")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                        raise ModelUnavailable(f"Model checksum mismatch: {kind}/{name}")
            self.config = json.loads((root / "config.json").read_text())
            self.tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
            self.tokenizer.enable_truncation(max_length=512)
            self.tokenizer.enable_padding(pad_id=int(self.config.get("pad_token_id", 0)))
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            self.session = ort.InferenceSession(str(root / "onnx" / "model_quantized.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
        except (OSError, ValueError, KeyError) as exc:
            raise ModelUnavailable(f"Offline {kind} model is not provisioned: {exc}") from exc
        self.kind = kind
        self.card["artifact_sha256"] = self.card["files"]["onnx/model_quantized.onnx"]
        self.card["runtime"] = ort.__version__

    def _run(self, texts):
        encoded = self.tokenizer.encode_batch(texts)
        inputs = {"input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
                  "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
                  "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64)}
        accepted = {item.name for item in self.session.get_inputs()}
        outputs = self.session.run(None, {key: value for key, value in inputs.items() if key in accepted})
        return outputs[0], inputs["attention_mask"]

    def embed(self, texts: list[str], query: bool = False) -> np.ndarray:
        results = []
        for start in range(0, len(texts)):
            values = [("query: " if query else "passage: ") + text for text in texts[start:start + 1]]
            hidden, mask = self._run(values)
            pooled = (hidden * mask[:, :, None]).sum(axis=1) / np.maximum(mask.sum(axis=1)[:, None], 1)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            results.append(pooled.astype(np.float32))
        return np.concatenate(results) if results else np.empty((0, int(self.config.get("hidden_size", 384))), dtype=np.float32)

    def entail(self, premise: str, hypothesis: str) -> dict:
        logits, _ = self._run([(premise, hypothesis)])
        probabilities = np.exp(logits[0] - np.max(logits[0]))
        probabilities /= probabilities.sum()
        mapping = self.config.get("id2label", {})
        labels = {str(mapping.get(str(index), index)).casefold(): round(float(value), 6) for index, value in enumerate(probabilities)}
        return {"entailment": labels.get("entailment", 0.0), "contradiction": labels.get("contradiction", 1.0),
                "neutral": labels.get("neutral", 0.0), "model": self.card["name"], "version": self.card["version"],
                "limits": "Uncalibrated pretrained NLI score; used conservatively alongside exact value and citation checks"}


@lru_cache(maxsize=2)
def local_model(kind: str) -> OfflineModel:
    return OfflineModel(kind)
