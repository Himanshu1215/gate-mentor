"""
train/train_qlora.py
────────────────────
QLoRA supervised fine-tune of microsoft/Phi-4-mini-instruct on the GATE chat
dataset. RUN THIS ON THE GPU VM (not the 8 GB CPU box).

Pipeline: 4-bit base (bitsandbytes) + LoRA adapters (peft) + SFTTrainer (trl).
Fits comfortably on a single 16 GB GPU; works on 12 GB with batch size 1.

Inputs : train/data/train.jsonl, train/data/val.jsonl  (built by build_dataset.py)
Output : train/out/adapter/   (LoRA adapter — feed to merge_and_export.py)

Usage
-----
    python train/train_qlora.py
    python train/train_qlora.py --epochs 3 --batch-size 2 --lr 2e-4
    python train/train_qlora.py --base microsoft/Phi-4-mini-instruct
"""

import os
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HERE = os.path.dirname(__file__)
DEFAULT_TRAIN = os.path.join(HERE, "data", "train.jsonl")
DEFAULT_VAL = os.path.join(HERE, "data", "val.jsonl")
DEFAULT_OUT = os.path.join(HERE, "out")


def parse_args():
    p = argparse.ArgumentParser(description="QLoRA fine-tune Phi-4-mini on GATE data.")
    p.add_argument("--base", default="microsoft/Phi-4-mini-instruct", help="HF base model repo")
    p.add_argument("--train-file", default=DEFAULT_TRAIN)
    p.add_argument("--val-file", default=DEFAULT_VAL)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=8, help="effective batch = batch-size * grad-accum")
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--max-seq-len", type=int, default=2048)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    return p.parse_args()


def main():
    args = parse_args()

    # Heavy imports inside main so `--help` works on the CPU VM before shipping.
    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    if not os.path.exists(args.train_file):
        raise SystemExit(
            f"Missing {args.train_file}. Run build_dataset.py on the CPU VM first "
            "and copy the train/ folder over."
        )

    logger.info(f"Loading dataset: {args.train_file}")
    data_files = {"train": args.train_file}
    if os.path.exists(args.val_file) and os.path.getsize(args.val_file) > 0:
        data_files["validation"] = args.val_file
    ds = load_dataset("json", data_files=data_files)

    logger.info(f"Loading tokenizer + 4-bit base model: {args.base}")
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    sft_config = SFTConfig(
        output_dir=args.out_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="epoch" if "validation" in ds else "no",
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_seq_length=args.max_seq_len,
        packing=False,
        report_to="none",
    )

    # SFTTrainer applies the tokenizer's chat template to the "messages" field.
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=ds["train"],
        eval_dataset=ds.get("validation"),
        peft_config=lora,
        processing_class=tokenizer,
    )

    logger.info("Starting QLoRA training ...")
    trainer.train()

    adapter_dir = os.path.join(args.out_dir, "adapter")
    trainer.save_model(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    logger.info(f"✅ Adapter saved -> {adapter_dir}")
    logger.info("Next: python train/merge_and_export.py")


if __name__ == "__main__":
    main()
