"""
Training pipeline for the custom decoder-only transformer.

Features:
- AdamW optimizer with cosine annealing LR scheduler
- Gradient clipping for training stability
- Checkpoint saving/loading
- Training & validation loss tracking
- Mixed precision training (optional)
- Health Q&A dataset loading
"""

import json
import math
import os
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from app.transformer.model import DecoderOnlyTransformer, TransformerConfig
from app.transformer.tokenizer_utils import TokenizerWrapper


# ==========================================
# Dataset
# ==========================================

class HealthQADataset(Dataset):
    """
    Dataset for health Q&A pairs.
    Loads from a JSON file with format:
    [
        {"question": "...", "answer": "..."},
        ...
    ]
    """

    def __init__(
        self,
        data_path: str,
        tokenizer: TokenizerWrapper,
        max_length: int = 256,
    ):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.samples = []

        # Load data
        with open(data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Tokenize all samples
        for item in raw_data:
            text = tokenizer.format_health_qa(item["question"], item["answer"])
            token_ids = tokenizer.encode(text, max_length=max_length)

            if len(token_ids) >= 2:  # Need at least 2 tokens for input/target
                self.samples.append(token_ids)

        print(f"Loaded {len(self.samples)} training samples from {data_path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        token_ids = self.samples[idx]

        # Pad or truncate to max_length
        if len(token_ids) < self.max_length:
            padding = [self.tokenizer.pad_token_id] * (self.max_length - len(token_ids))
            token_ids = token_ids + padding

        token_ids = token_ids[: self.max_length]

        # Input: all tokens except last
        # Target: all tokens except first (shifted by 1)
        input_ids = torch.tensor(token_ids[:-1], dtype=torch.long)
        targets = torch.tensor(token_ids[1:], dtype=torch.long)

        # Mask padding in targets (set to -1 so cross_entropy ignores them)
        targets[targets == self.tokenizer.pad_token_id] = -1

        return {"input_ids": input_ids, "targets": targets}


# ==========================================
# Training Loop
# ==========================================

class Trainer:
    """Training pipeline for the decoder-only transformer."""

    def __init__(
        self,
        model: DecoderOnlyTransformer,
        train_dataset: HealthQADataset,
        val_dataset: HealthQADataset | None = None,
        lr: float = 3e-4,
        weight_decay: float = 0.1,
        batch_size: int = 16,
        epochs: int = 50,
        grad_clip: float = 1.0,
        checkpoint_dir: str = "./data/checkpoints",
        device: str = "auto",
    ):
        # Determine device
        if device == "auto":
            self.device = torch.device(
                "cuda" if torch.cuda.is_available()
                else "mps" if torch.backends.mps.is_available()
                else "cpu"
            )
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.epochs = epochs
        self.grad_clip = grad_clip
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Dataloaders
        self.train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True, drop_last=True
        )
        self.val_loader = (
            DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
            if val_dataset else None
        )

        # Optimizer: AdamW with weight decay
        self.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
            betas=(0.9, 0.95),
        )

        # LR Scheduler: Cosine annealing with warmup
        total_steps = len(self.train_loader) * epochs
        warmup_steps = min(100, total_steps // 10)
        self.scheduler = torch.optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=lr,
            total_steps=total_steps,
            pct_start=warmup_steps / total_steps,
            anneal_strategy="cos",
        )

        # Tracking
        self.train_losses = []
        self.val_losses = []
        self.best_val_loss = float("inf")

        print(f"Training on device: {self.device}")
        print(f"Total training steps: {total_steps}")
        print(f"Warmup steps: {warmup_steps}")

    def train(self) -> dict:
        """Run the full training loop."""
        print("\n" + "=" * 60)
        print("Starting Training")
        print("=" * 60)

        start_time = time.time()

        for epoch in range(1, self.epochs + 1):
            # Training epoch
            train_loss = self._train_epoch(epoch)
            self.train_losses.append(train_loss)

            # Validation
            val_loss = None
            if self.val_loader:
                val_loss = self._validate()
                self.val_losses.append(val_loss)

            # Logging
            elapsed = time.time() - start_time
            lr = self.optimizer.param_groups[0]["lr"]
            log_msg = (
                f"Epoch {epoch:3d}/{self.epochs} | "
                f"Train Loss: {train_loss:.4f} | "
            )
            if val_loss is not None:
                log_msg += f"Val Loss: {val_loss:.4f} | "
            log_msg += f"LR: {lr:.2e} | Time: {elapsed:.0f}s"
            print(log_msg)

            # Save checkpoint if best validation loss
            if val_loss is not None and val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self._save_checkpoint(epoch, is_best=True)
            elif epoch % 10 == 0:
                self._save_checkpoint(epoch, is_best=False)

        # Save final checkpoint
        self._save_checkpoint(self.epochs, is_best=False, filename="transformer_final.pt")

        total_time = time.time() - start_time
        print(f"\nTraining complete in {total_time:.1f}s")
        print(f"Best validation loss: {self.best_val_loss:.4f}")

        return {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
            "best_val_loss": self.best_val_loss,
            "total_time": total_time,
        }

    def _train_epoch(self, epoch: int) -> float:
        """Run one training epoch."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch in self.train_loader:
            input_ids = batch["input_ids"].to(self.device)
            targets = batch["targets"].to(self.device)

            # Forward pass
            logits, loss = self.model(input_ids, targets)

            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            if self.grad_clip > 0:
                nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip)

            self.optimizer.step()
            self.scheduler.step()

            total_loss += loss.item()
            num_batches += 1

        return total_loss / max(num_batches, 1)

    @torch.no_grad()
    def _validate(self) -> float:
        """Run validation."""
        self.model.eval()
        total_loss = 0.0
        num_batches = 0

        for batch in self.val_loader:
            input_ids = batch["input_ids"].to(self.device)
            targets = batch["targets"].to(self.device)

            _, loss = self.model(input_ids, targets)
            total_loss += loss.item()
            num_batches += 1

        return total_loss / max(num_batches, 1)

    def _save_checkpoint(
        self,
        epoch: int,
        is_best: bool = False,
        filename: str | None = None,
    ):
        """Save model checkpoint."""
        if filename is None:
            filename = "transformer_best.pt" if is_best else f"transformer_epoch_{epoch}.pt"

        path = self.checkpoint_dir / filename
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "config": self.model.config,
                "train_losses": self.train_losses,
                "val_losses": self.val_losses,
                "best_val_loss": self.best_val_loss,
            },
            path,
        )
        if is_best:
            print(f"  → Saved best checkpoint: {path}")


# ==========================================
# Entry Point
# ==========================================

def train_model(
    data_path: str = "./data/training_data/health_qa.json",
    checkpoint_dir: str = "./data/checkpoints",
    epochs: int = 50,
    batch_size: int = 16,
    lr: float = 3e-4,
    device: str = "auto",
) -> dict:
    """
    Train the custom decoder-only transformer on health Q&A data.

    Args:
        data_path: Path to the training data JSON file.
        checkpoint_dir: Directory to save checkpoints.
        epochs: Number of training epochs.
        batch_size: Training batch size.
        lr: Learning rate.
        device: Device to train on.

    Returns:
        Training history dict.
    """
    # Initialize tokenizer
    tokenizer = TokenizerWrapper("gpt2")

    # Initialize model
    config = TransformerConfig(
        vocab_size=tokenizer.vocab_size,
        max_seq_len=256,
        d_model=384,
        n_heads=6,
        n_layers=6,
        d_ff=1536,
        dropout=0.1,
    )
    model = DecoderOnlyTransformer(config)

    # Load dataset — 90/10 train/val split
    full_dataset = HealthQADataset(data_path, tokenizer, max_length=config.max_seq_len)

    val_size = max(1, len(full_dataset) // 10)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size]
    )

    print(f"Train samples: {train_size}, Val samples: {val_size}")

    # Create trainer and train
    trainer = Trainer(
        model=model,
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        lr=lr,
        batch_size=batch_size,
        epochs=epochs,
        checkpoint_dir=checkpoint_dir,
        device=device,
    )

    return trainer.train()


if __name__ == "__main__":
    train_model()
