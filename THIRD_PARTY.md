# Third-party ML components

The Step 5A baseline runs fully offline. Generated model cards record the exact seed and label all results **on synthetic data**.

| Component | Use | Licence |
| --- | --- | --- |
| scikit-learn | Gradient-boosted baseline, isotonic calibration, PR-AUC and calibration curve | BSD-3-Clause |
| NumPy | Numeric arrays and deterministic metric preparation | BSD-3-Clause |
| joblib | Local model artifact serialization supplied by scikit-learn | BSD-3-Clause |
| SHAP | Optional local per-row tree explanations; disabled unless explicitly enabled | MIT |

The Step 6 Hinglish classifier uses scikit-learn TF-IDF character n-gram embeddings, logistic regression and isotonic calibration. It downloads no weights or data.

No weights are downloaded at runtime. The generated artifact is loaded only after its SHA-256 matches the model card.

| Component | Use | Licence |
| --- | --- | --- |
| [multilingual-e5-small / ONNX conversion](https://huggingface.co/Xenova/multilingual-e5-small) | Offline multilingual retrieval and classifier features; pinned revision in provisioning script | MIT (original intfloat/multilingual-e5-small) |
| [mDeBERTa-v3-base-mnli-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) | Conservative multilingual claim entailment checks, quantized ONNX | MIT |
| ONNX Runtime / Hugging Face tokenizers | Local inference / tokenisation | MIT / Apache-2.0 |
| [Qwen2.5 1.5B Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | Local Ollama generation; model digest shown on every answer | Apache-2.0 |
| Ollama | Loopback-only model server; explicitly provisioned, cloud disabled | MIT; bundled native dependencies retain their included notices |
| Tesseract / tessdata | English and Hindi OCR; local runtime and language data | Apache-2.0; Leptonica BSD-style |
| PyMuPDF | PDF text geometry and rasterisation of scanned pages | AGPL-3.0 or Artifex commercial licence; retain licence and meet distribution/service obligations |
| AnyAscii | Offline Unicode transliteration for alias blocking | ISC |
| PyJWT | Signed JWT access and refresh claims | MIT |

The alias matcher computes exact interventional Shapley values over all 128 coalitions of its seven features. It does not require the optional SHAP package. Its fixed baseline comes from generated training cases, never the Riya pack. The classifier explains embedding predictions with bounded word occlusion. Model cards distinguish synthetic evaluation from real-world accuracy.
