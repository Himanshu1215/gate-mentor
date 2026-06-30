"""
scripts/data/distill_solutions.py
─────────────────────────────────
Use a strong OPEN teacher LLM (running locally on the GPU — no API, no cost) to
write clear step-by-step solutions for parsed PYQs that don't have one. This is
knowledge distillation: the big teacher's reasoning becomes training data for the
small student model that will run on the CPU VM.

RUN THIS ON THE GPU VM, in the same session as training (the teacher needs a GPU).
After it finishes, rebuild the dataset and fine-tune the student.

Default teacher: Qwen/Qwen2.5-Math-7B-Instruct (excellent at GATE-level math,
fits any A100). For higher quality on an 80GB A100 pass a bigger teacher with
4-bit, e.g.  --teacher Qwen/Qwen2.5-72B-Instruct --load-4bit

Modes
-----
  missing-solution (default) : only questions that HAVE a ground-truth answer but
                               no solution. Highest quality — answer is trusted.
  all-unsolved               : also solve questions with no answer (teacher supplies
                               a pseudo-answer; marked answer_source=distilled).

Usage
-----
    pip install transformers accelerate bitsandbytes
    python scripts/data/distill_solutions.py
    python scripts/data/distill_solutions.py --teacher Qwen/Qwen2.5-72B-Instruct --load-4bit
    python scripts/data/distill_solutions.py --mode all-unsolved --limit 50
"""

import os
import re
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a GATE Data Science & AI examiner writing the official solution. "
    "Given a question (and, if provided, the correct answer), produce a clear, "
    "rigorous, step-by-step solution suitable for a topper's notes. Use correct "
    "mathematical notation in LaTeX (inline $...$). Keep it concise but complete, "
    "and end with a line 'Final answer: <option or value>'. Do NOT restate the "
    "question. Do NOT add commentary outside the solution."
)


def build_user_prompt(rec):
    q = rec.get("question_text", "")
    opts = rec.get("options") or {}
    parts = [f"Question:\n{q}"]
    if opts:
        parts.append("Options:\n" + "\n".join(f"({k}) {v}" for k, v in sorted(opts.items())))
    if rec.get("answer"):
        parts.append(f"The correct answer is: {rec['answer']}. "
                     "Explain WHY this is correct, step by step.")
    else:
        parts.append("Solve it step by step and state the final answer.")
    return "\n\n".join(parts)


def extract_final_answer(text, has_options):
    m = re.search(r"final answer\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
    if not m:
        return None
    tail = m.group(1).strip()
    if has_options:
        lm = re.search(r"\(?([A-Da-d])\)?", tail)
        return lm.group(1).upper() if lm else None
    nm = re.search(r"-?\d+(?:\.\d+)?", tail)
    return nm.group(0) if nm else None


def main():
    ap = argparse.ArgumentParser(description="Distill step-by-step solutions with an open teacher LLM.")
    ap.add_argument("--teacher", default="Qwen/Qwen2.5-Math-7B-Instruct")
    ap.add_argument("--mode", choices=["missing-solution", "all-unsolved"], default="missing-solution")
    ap.add_argument("--limit", type=int, default=0, help="Max questions to process (0 = all)")
    ap.add_argument("--max-new-tokens", type=int, default=700)
    ap.add_argument("--load-4bit", action="store_true", help="4-bit load for large teachers (72B etc.)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(PARSED_DIR, "*.json")))
    targets = []
    for path in files:
        rec = json.load(open(path, encoding="utf-8"))
        if rec.get("solution"):
            continue
        if args.mode == "missing-solution" and not rec.get("answer"):
            continue
        targets.append((path, rec))
    if args.limit:
        targets = targets[:args.limit]
    logger.info(f"{len(targets)} question(s) need distilled solutions (mode={args.mode}).")
    if not targets:
        return
    if args.dry_run:
        for p, r in targets[:5]:
            logger.info(f"[DRY] would solve {os.path.basename(p)}: {r.get('question_text','')[:80]}")
        return

    # Heavy imports here so --help / --dry-run work without a GPU.
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    logger.info(f"Loading teacher {args.teacher} ...")
    tok = AutoTokenizer.from_pretrained(args.teacher, trust_remote_code=True)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    kw = dict(trust_remote_code=True, device_map="auto", torch_dtype=torch.bfloat16)
    if args.load_4bit:
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(args.teacher, **kw)
    model.eval()

    done = 0
    batch_size = 12
    for idx in range(0, len(targets), batch_size):
        batch = targets[idx:idx+batch_size]
        prompts = []
        for path, rec in batch:
            messages = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": build_user_prompt(rec)}]
            prompts.append(tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True))
        
        inputs = tok(prompts, padding=True, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                temperature=0.2,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tok.pad_token_id
            )
        
        for j, (path, rec) in enumerate(batch):
            gen_tokens = outputs[j][inputs["input_ids"].shape[1]:]
            text = tok.decode(gen_tokens, skip_special_tokens=True).strip()
            if not text:
                continue
            rec["solution"] = text
            rec["solution_source"] = f"distilled:{args.teacher}"
            if not rec.get("answer"):
                ans = extract_final_answer(text, bool(rec.get("options")))
                if ans:
                    rec["answer"] = ans
                    rec["answer_source"] = f"distilled:{args.teacher}"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)
            done += 1
        logger.info(f"  {done}/{len(targets)} solved")

    logger.info(f"Done. Wrote {done} distilled solutions. Next: python train/build_dataset.py")


if __name__ == "__main__":
    main()
