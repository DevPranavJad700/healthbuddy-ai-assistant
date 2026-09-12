"""
Decoder-Only Transformer Model — Built from scratch using PyTorch.

Architecture:
- Token + Learnable Positional Embeddings
- N x Transformer Blocks (Pre-Norm: LayerNorm → Attention → Residual)
- Causal (masked) Multi-Head Self-Attention
- Feed-Forward Network with GELU activation
- Final LayerNorm → Linear LM Head

This is a GPT-style autoregressive language model designed for
next-token prediction on health-domain text.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass


@dataclass
class TransformerConfig:
    """Configuration for the decoder-only transformer."""
    vocab_size: int = 50257       # GPT-2 tokenizer vocab size
    max_seq_len: int = 256        # Maximum sequence length
    d_model: int = 384            # Embedding dimension
    n_heads: int = 6              # Number of attention heads
    n_layers: int = 6             # Number of transformer blocks
    d_ff: int = 1536              # Feed-forward inner dimension (4x d_model)
    dropout: float = 0.1          # Dropout rate
    bias: bool = False            # Use bias in linear layers

    @property
    def head_dim(self) -> int:
        assert self.d_model % self.n_heads == 0, "d_model must be divisible by n_heads"
        return self.d_model // self.n_heads


class CausalSelfAttention(nn.Module):
    """
    Multi-Head Causal Self-Attention.

    Uses a causal mask to prevent attending to future tokens,
    enabling autoregressive generation.
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.n_heads = config.n_heads
        self.head_dim = config.head_dim
        self.d_model = config.d_model

        # Combined QKV projection for efficiency
        self.qkv_proj = nn.Linear(config.d_model, 3 * config.d_model, bias=config.bias)
        # Output projection
        self.out_proj = nn.Linear(config.d_model, config.d_model, bias=config.bias)

        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

        # Causal mask: lower triangular matrix
        self.register_buffer(
            "causal_mask",
            torch.tril(torch.ones(config.max_seq_len, config.max_seq_len))
            .view(1, 1, config.max_seq_len, config.max_seq_len)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape

        # Project to Q, K, V
        qkv = self.qkv_proj(x)
        q, k, v = qkv.chunk(3, dim=-1)

        # Reshape for multi-head: (B, T, C) → (B, n_heads, T, head_dim)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention with causal mask
        scale = math.sqrt(self.head_dim)
        attn_weights = (q @ k.transpose(-2, -1)) / scale

        # Apply causal mask (set future positions to -inf)
        attn_weights = attn_weights.masked_fill(
            self.causal_mask[:, :, :T, :T] == 0,
            float("-inf")
        )

        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)

        # Weighted sum of values
        out = attn_weights @ v  # (B, n_heads, T, head_dim)

        # Concatenate heads: (B, n_heads, T, head_dim) → (B, T, C)
        out = out.transpose(1, 2).contiguous().view(B, T, C)

        # Output projection
        out = self.resid_dropout(self.out_proj(out))
        return out


class FeedForward(nn.Module):
    """
    Position-wise Feed-Forward Network.
    FFN(x) = GELU(x @ W1 + b1) @ W2 + b2
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(config.d_model, config.d_ff, bias=config.bias),
            nn.GELU(),
            nn.Linear(config.d_ff, config.d_model, bias=config.bias),
            nn.Dropout(config.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    """
    Single Transformer Block with Pre-Norm architecture.

    Pre-Norm (used in GPT-2/3, LLaMA, etc.):
        x = x + Attention(LayerNorm(x))
        x = x + FFN(LayerNorm(x))
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model)
        self.attn = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model)
        self.ffn = FeedForward(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-norm + residual connections
        x = x + self.attn(self.ln1(x))
        x = x + self.ffn(self.ln2(x))
        return x


class DecoderOnlyTransformer(nn.Module):
    """
    Decoder-Only Transformer for Causal Language Modeling.

    This model follows the GPT architecture:
    1. Token embeddings + Positional embeddings
    2. Stack of N transformer blocks
    3. Final layer norm
    4. Linear projection to vocabulary (LM head)

    The LM head shares weights with the token embedding layer
    (weight tying) for parameter efficiency.
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config

        # Embeddings
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position_embedding = nn.Embedding(config.max_seq_len, config.d_model)
        self.embedding_dropout = nn.Dropout(config.dropout)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.n_layers)
        ])

        # Final layer norm
        self.ln_f = nn.LayerNorm(config.d_model)

        # LM Head (projects back to vocab size)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Weight tying: share weights between token embedding and LM head
        self.lm_head.weight = self.token_embedding.weight

        # Initialize weights
        self.apply(self._init_weights)

        # Report parameter count
        n_params = sum(p.numel() for p in self.parameters())
        print(f"DecoderOnlyTransformer initialized with {n_params / 1e6:.2f}M parameters")

    def _init_weights(self, module: nn.Module):
        """Xavier/Kaiming initialization for stable training."""
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        """
        Forward pass.

        Args:
            input_ids: (B, T) token indices
            targets: (B, T) target token indices for computing loss

        Returns:
            logits: (B, T, vocab_size) — raw prediction scores
            loss: scalar loss if targets provided, else None
        """
        B, T = input_ids.shape
        assert T <= self.config.max_seq_len, (
            f"Sequence length {T} exceeds max_seq_len {self.config.max_seq_len}"
        )

        # Create position indices
        positions = torch.arange(0, T, dtype=torch.long, device=input_ids.device)

        # Embeddings
        tok_emb = self.token_embedding(input_ids)       # (B, T, d_model)
        pos_emb = self.position_embedding(positions)     # (T, d_model)
        x = self.embedding_dropout(tok_emb + pos_emb)

        # Through transformer blocks
        for block in self.blocks:
            x = block(x)

        # Final layer norm
        x = self.ln_f(x)

        # LM head → logits
        logits = self.lm_head(x)  # (B, T, vocab_size)

        # Compute loss if targets provided
        loss = None
        if targets is not None:
            # Reshape for cross-entropy: (B*T, vocab_size) vs (B*T,)
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-1,  # Ignore padding tokens
            )

        return logits, loss

    @torch.no_grad()
    def count_parameters(self) -> dict:
        """Return parameter count breakdown."""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        return {
            "total": total,
            "trainable": trainable,
            "total_millions": f"{total / 1e6:.2f}M",
        }
