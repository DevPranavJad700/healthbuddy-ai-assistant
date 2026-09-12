"""
Text generation utilities for the custom decoder-only transformer.

Supports:
- Greedy decoding
- Temperature scaling
- Top-k sampling
- Top-p (nucleus) sampling
- Repetition penalty
"""

import torch
import torch.nn.functional as F
from app.transformer.model import DecoderOnlyTransformer


@torch.no_grad()
def generate(
    model: DecoderOnlyTransformer,
    input_ids: torch.Tensor,
    max_new_tokens: int = 128,
    temperature: float = 0.8,
    top_k: int = 50,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
    eos_token_id: int | None = None,
) -> torch.Tensor:
    """
    Autoregressive text generation with sampling strategies.

    Args:
        model: The decoder-only transformer model.
        input_ids: (1, T) initial token IDs (prompt).
        max_new_tokens: Maximum number of tokens to generate.
        temperature: Sampling temperature (higher = more random).
        top_k: Keep only top-k tokens for sampling.
        top_p: Nucleus sampling threshold.
        repetition_penalty: Penalty for repeating tokens.
        eos_token_id: Stop generation when this token is produced.

    Returns:
        (1, T + generated) tensor of token IDs.
    """
    model.eval()
    device = input_ids.device
    generated = input_ids.clone()

    for _ in range(max_new_tokens):
        # Crop to max_seq_len if needed
        context = generated[:, -model.config.max_seq_len:]

        # Forward pass
        logits, _ = model(context)

        # Get logits for the last position only
        next_logits = logits[:, -1, :]  # (1, vocab_size)

        # Apply repetition penalty
        if repetition_penalty != 1.0:
            next_logits = _apply_repetition_penalty(
                next_logits, generated, repetition_penalty
            )

        # Apply temperature
        if temperature != 1.0:
            next_logits = next_logits / temperature

        # Apply top-k filtering
        if top_k > 0:
            next_logits = _top_k_filter(next_logits, top_k)

        # Apply top-p (nucleus) filtering
        if top_p < 1.0:
            next_logits = _top_p_filter(next_logits, top_p)

        # Sample from the distribution
        probs = F.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)  # (1, 1)

        # Append to generated sequence
        generated = torch.cat([generated, next_token], dim=1)

        # Stop if EOS token generated
        if eos_token_id is not None and next_token.item() == eos_token_id:
            break

    return generated


def _apply_repetition_penalty(
    logits: torch.Tensor,
    generated: torch.Tensor,
    penalty: float,
) -> torch.Tensor:
    """Penalize tokens that have already been generated."""
    for token_id in set(generated[0].tolist()):
        if logits[0, token_id] > 0:
            logits[0, token_id] /= penalty
        else:
            logits[0, token_id] *= penalty
    return logits


def _top_k_filter(logits: torch.Tensor, k: int) -> torch.Tensor:
    """Keep only the top-k logits, set the rest to -inf."""
    values, _ = torch.topk(logits, k)
    min_value = values[:, -1].unsqueeze(-1)
    return torch.where(logits < min_value, torch.full_like(logits, float("-inf")), logits)


def _top_p_filter(logits: torch.Tensor, p: float) -> torch.Tensor:
    """Nucleus sampling: keep top tokens whose cumulative probability >= p."""
    sorted_logits, sorted_indices = torch.sort(logits, descending=True)
    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

    # Remove tokens with cumulative probability above the threshold
    sorted_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= p
    sorted_logits[sorted_mask] = float("-inf")

    # Scatter back to original positions
    logits = logits.scatter(1, sorted_indices, sorted_logits)
    return logits
