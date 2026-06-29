# GATE Mentor — LLM Fine-tuning Package

This folder is **self-contained**. The workflow is split across two machines:

- **CPU VM (8 GB / 4 vCPU)** — collect data and build the dataset. No GPU needed.
- **GPU VM (rented briefly)** — run the actual fine-tune, export a GGUF, copy it back.

The fine-tuned model drops into `models/llm/phi-4-mini-instruct-q4_k_m.gguf` — the
exact filename `learning/ai_reasoner.py` loads — so **no app code changes** are needed.

---

## Step 1 — On the CPU VM: collect data + build the dataset

```bash
# 1a. Get raw content (drop PDFs under knowledge/official/pyqs and knowledge/textbooks first)
python scripts/data/collect_pdfs.py                 # PDF -> cleaned .txt (+ optional --ingest)
python scripts/data/scrape_syllabus.py              # writes the GATE DA syllabus markdown

# 1b. Turn PYQ text into structured JSON, then REVIEW the output
python scripts/data/parse_pyqs.py knowledge/official/pyqs/<paper>.txt --year 2024
#     -> review knowledge/official/pyqs/parsed/*.json and fill in null answer/solution

# 1c. Build the chat dataset (reads all structured PYQ JSON)
python train/build_dataset.py
#     -> train/data/train.jsonl  +  train/data/val.jsonl
```

> Quality gate: `build_dataset.py` only emits examples for PYQs that have an
> `answer` (and ideally a `solution`). Garbage in → no example out, on purpose.

Then copy the whole `train/` folder (including `train/data/*.jsonl`) to the GPU VM.

---

## Step 2 — On the GPU VM: fine-tune

```bash
python -m venv venv && source venv/bin/activate
pip install -r train/requirements-gpu.txt          # CUDA torch + peft + trl + bitsandbytes

python train/train_qlora.py                         # -> train/out/adapter/
#   tune with: --epochs 3 --batch-size 2 --grad-accum 8 --lr 2e-4
```

Fits a single 16 GB GPU. On 12 GB use `--batch-size 1`.

---

## Step 3 — On the GPU VM: merge + export to GGUF

```bash
# Build llama.cpp once (needed for GGUF conversion):
git clone https://github.com/ggerganov/llama.cpp && (cd llama.cpp && make)

python train/merge_and_export.py --llama-cpp ./llama.cpp
#   -> models/llm/phi-4-mini-instruct-q4_k_m.gguf
```

If you skip `--llama-cpp`, the script still produces the merged HF model and
prints the exact two commands to finish the GGUF conversion manually.

---

## Step 4 — Back on the CPU VM: use it

```bash
# Copy the produced .gguf to:
#   models/llm/phi-4-mini-instruct-q4_k_m.gguf
uvicorn presentation.api:app --host 0.0.0.0 --port 8000 --reload
```

`ai_reasoner.py` auto-loads that file and exits MOCK mode. Verify via `/chat`.

---

## File map

| File | Runs on | Purpose |
|------|---------|---------|
| `build_dataset.py` | CPU | PYQ JSON → chat JSONL (`data/train.jsonl`, `data/val.jsonl`) |
| `train_qlora.py` | GPU | QLoRA SFT of Phi-4-mini → `out/adapter/` |
| `merge_and_export.py` | GPU | Merge adapter + convert/quantize → GGUF Q4_K_M |
| `requirements-gpu.txt` | GPU | CUDA training deps (keep off the CPU VM) |

## Notes on hardware

Fine-tuning Phi-4-mini (3.8B params) is **not** attempted on the 8 GB CPU VM —
it would OOM or take weeks. The CPU VM only prepares data; the GPU does the math.
For improving retrieval **without** a GPU, see `scripts/finetune_embeddings.py`
(fine-tunes the 109M embedding model — that one is CPU-feasible).
