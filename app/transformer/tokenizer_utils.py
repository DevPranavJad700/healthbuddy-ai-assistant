"""
Tokenizer utilities — wraps HuggingFace GPT-2 tokenizer
for use with the custom transformer model.
"""

from transformers import AutoTokenizer


class TokenizerWrapper:
    """
    Wrapper around HuggingFace tokenizer for the custom transformer.
    Uses GPT-2's BPE tokenizer as the base vocabulary.
    """

    def __init__(self, tokenizer_name: str = "gpt2"):
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        # GPT-2 tokenizer doesn't have a pad token by default
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

    @property
    def vocab_size(self) -> int:
        return len(self.tokenizer)

    @property
    def eos_token_id(self) -> int:
        return self.tokenizer.eos_token_id

    @property
    def pad_token_id(self) -> int:
        return self.tokenizer.pad_token_id

    @property
    def bos_token_id(self) -> int:
        return self.tokenizer.bos_token_id or self.tokenizer.eos_token_id

    def encode(self, text: str, max_length: int | None = None) -> list[int]:
        """Encode text to token IDs."""
        kwargs = {"add_special_tokens": False}
        if max_length:
            kwargs["max_length"] = max_length
            kwargs["truncation"] = True
        return self.tokenizer.encode(text, **kwargs)

    def decode(self, token_ids: list[int], skip_special: bool = True) -> str:
        """Decode token IDs back to text."""
        return self.tokenizer.decode(token_ids, skip_special_tokens=skip_special)

    def batch_encode(
        self,
        texts: list[str],
        max_length: int = 256,
        padding: bool = True,
    ) -> dict:
        """Batch encode with padding."""
        return self.tokenizer(
            texts,
            max_length=max_length,
            padding="max_length" if padding else False,
            truncation=True,
            return_tensors="pt",
        )

    def format_health_qa(self, question: str, answer: str) -> str:
        """Format a health Q&A pair for training."""
        return f"<|health|>Question: {question}\nAnswer: {answer}<|end|>"
