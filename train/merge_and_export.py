"""
train/merge_and_export.py
─────────────────────────
Merge the trained LoRA adapter into the base model, then convert + quantize to
GGUF Q4_K_M so the result drops straight into the CPU app at
    models/llm/phi-4-mini-instruct-q4_k_m.gguf
(the exact filename learning/ai_reasoner.py loads).

RUN THIS ON THE GPU VM after train_qlora.py.

Steps:
  1. Load base + adapter, merge_and_unload(), save a merged fp16 HF model.
  2. Convert merged model -> GGUF (fp16) via llama.cpp's convert_hf_to_gguf.py.
  3. Quantize GGUF fp16 -> Q4_K_M via llama.cpp's quantize binary.

llama.cpp is required for steps 2-3. If not found, step 1 still runs and the
script prints the exact commands to finish manually.

Usage
-----
    python train/merge_and_export.py
    python train/merge_and_export.py --llama-cpp /path/to/llama.cpp
"""

import os
import shutil
import argparse
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GGUF_NAME = "phi-4-mini-instruct-q4_k_m.gguf"


def parse_args():
    p = argparse.ArgumentParser(description="Merge LoRA adapter and export to GGUF Q4_K_M.")
    p.add_argument("--base", default="microsoft/Phi-4-mini-instruct")
    p.add_argument("--adapter", default=os.path.join(HERE, "out", "adapter"))
    p.add_argument("--merged-dir", default="/tmp/merged",
                   help="Temp dir for merged HF weights before GGUF (needs ~15 GB; use /tmp on GPU VMs)")
    p.add_argument("--gguf-out", default=os.path.join(ROOT, "models", "llm", GGUF_NAME))
    p.add_argument("--quant", default="Q4_K_M",
                   help="GGUF quantization (Q4_K_M ~2.5GB; Q5_K_M ~2.8GB better quality; Q6_K best). "
                        "Q5_K_M recommended if the CPU VM has headroom.")
    p.add_argument("--llama-cpp", default=os.environ.get("LLAMA_CPP_DIR", ""),
                   help="Path to a built llama.cpp checkout (for GGUF convert+quantize)")
    return p.parse_args()


def merge(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    if not os.path.isdir(args.adapter):
        raise SystemExit(f"Adapter not found at {args.adapter}. Run train_qlora.py first.")

    logger.info(f"Loading base model {args.base} (fp16) ...")
    base = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True,
    )
    logger.info(f"Applying adapter {args.adapter} and merging ...")
    model = PeftModel.from_pretrained(base, args.adapter)
    model = model.merge_and_unload()

    os.makedirs(args.merged_dir, exist_ok=True)
    model.save_pretrained(args.merged_dir, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.adapter, trust_remote_code=True).save_pretrained(args.merged_dir)
    logger.info(f"✅ Merged model saved -> {args.merged_dir}")


def to_gguf(args):
    convert = os.path.join(args.llama_cpp, "convert_hf_to_gguf.py")
    # quantize binary name/location varies across llama.cpp versions
    candidates = [
        os.path.join(args.llama_cpp, "llama-quantize"),
        os.path.join(args.llama_cpp, "build", "bin", "llama-quantize"),
        os.path.join(args.llama_cpp, "quantize"),
    ]
    quantize = next((c for c in candidates if os.path.exists(c)), None)

    fp16_gguf = os.path.join(args.merged_dir, "merged-f16.gguf")
    os.makedirs(os.path.dirname(args.gguf_out), exist_ok=True)

    if not args.llama_cpp or not os.path.exists(convert) or not quantize:
        logger.warning("llama.cpp not found — skipping GGUF conversion. Finish manually:")
        logger.warning(f"  git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make")
        logger.warning(f"  python convert_hf_to_gguf.py {args.merged_dir} --outfile {fp16_gguf} --outtype f16")
        logger.warning(f"  ./llama-quantize {fp16_gguf} {args.gguf_out} {args.quant}")
        return

    logger.info("Converting merged model -> GGUF (f16) ...")
    subprocess.run(["python", convert, args.merged_dir, "--outfile", fp16_gguf,
                    "--outtype", "f16"], check=True)

    logger.info(f"Quantizing GGUF -> {args.quant} ...")
    subprocess.run([quantize, fp16_gguf, args.gguf_out, args.quant], check=True)

    size_gb = os.path.getsize(args.gguf_out) / (1024 ** 3)
    logger.info(f"✅ GGUF written -> {args.gguf_out} ({size_gb:.2f} GB)")

    # Clean up large intermediate files to free disk space
    for f in [fp16_gguf, args.merged_dir]:
        try:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)
            logger.info(f"Cleaned up {f}")
        except Exception:
            pass

    logger.info("Copy this file to the CPU VM at models/llm/ and restart the backend.")


def main():
    args = parse_args()
    merge(args)
    to_gguf(args)


if __name__ == "__main__":
    main()
