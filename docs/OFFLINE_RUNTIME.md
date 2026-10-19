# Offline T1 setup and validation

Run from the repository root using Python 3.11. Native runtimes and weights are excluded from Git. Provision them explicitly once, then process evidence offline.

```sh
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m app.cli migrate
python -m scripts.install_offline_models
python -m scripts.evaluate_offline_models
python -m scripts.prepare_models
python -m app.cli step6-model
```

Install Tesseract 5 with both `eng` and `hin` language data. The project-local `.runtime/ocr/bin/tesseract` takes precedence over PATH. Check `tesseract --list-langs`. Embedded PDF text retains page word geometry; scanned pages are rendered to temporary images and OCR runs page by page. OCR text becomes a searchable derived event with `ocr:document` provenance. Originals are only read.

Install Ollama from its official distribution. In a separate backend terminal run `python -m scripts.start_local_llm`. Then explicitly provision `OLLAMA_HOST=127.0.0.1:11436 ollama pull qwen2.5:1.5b`. If using the bundled executable, use `.runtime/ollama` instead of `ollama`. The launcher stores weights in `backend/data/models/ollama`, disables cloud, binds loopback and selects CPU inference. Configure `LOCAL_LLM_PROVIDER=ollama`, `LOCAL_LLM_MODEL=qwen2.5:1.5b`, `OLLAMA_BASE_URL=http://127.0.0.1:11436`. Restart an existing backend after installing dependencies or changing settings. Use the existing `make backend` and `make frontend` commands to start the application.

In the assistant choose Answer, Summary or Translate. Translation retains originals. Generated claims require exact retrieved citations, preserved values and conservative pretrained NLI support. One failed repair returns “No supporting evidence found.” Missing generation runtime uses labelled source excerpts; missing translation runtime refuses. Runtime code has no model-download operation, ignores proxy variables and rejects cloud-backed model tags and non-loopback URLs. No model trains on uploaded evidence.

For large cases run `python -m scripts.index_embeddings --case-id CASE_ID --seconds 300`. It resumes content-hashed vector shards. Cold large builds never block interactive search: SQL FTS, counts, facets and histograms remain available while incomplete vector coverage is reported. The event table loads 1,000 rows initially, loads more cursor pages on demand and uses a virtual list. Counts and IST histogram buckets cover all matching rows, including unloaded pages; the prior UTC histogram remains compatible.

The alias setup generates 600 varied cases, separates entire cases between training, calibration and test, and stores metrics. Exact interventional SHAP explains seven features. Every merge/unmerge records its feature label in the audit log. Feedback changes review priority without silently retraining on the hand-checked Riya case.

Clock sampling uses seed 914026, a shared clock-error draw per device and bounded execution. Adjacent-event ordering probabilities and intervals respond to clock confidence. Replay uses reconciled derived order, preserving source timestamps and bytes. Timing alone does not establish cause.

```sh
# Repository root, with backend virtual environment activated:
make lint test
cd backend
PARAKH_TEST_MODELS=1 python -m pytest tests/test_completed_t1.py::test_real_offline_embeddings_nli_and_scanned_receipt -q
python -m scripts.benchmark_search --rows 100000
cd ..
make smoke
```

`docs/validation/offline-models.json` is a tiny synthetic smoke evaluation, not a deployment-accuracy estimate. Its strict NLI threshold can reject true claims; this false-refusal limit is recorded. Alias and classifier cards separately store held-out synthetic-case metrics and calibration curves. Advanced T2/T3 capabilities labelled planned remain future work. Model licences and PyMuPDF's AGPL/commercial terms are recorded in `THIRD_PARTY.md`.
