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
