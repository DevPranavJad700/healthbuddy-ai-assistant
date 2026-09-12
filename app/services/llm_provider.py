"""
LLM Provider — Factory for selecting and initializing LLM backends.

Supports:
1. HuggingFace Transformers (default) — local models
2. Custom PyTorch Transformer — trained from scratch
3. Ollama — local server
"""

import torch
from typing import Any
import httpx
from pydantic import ConfigDict
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

from app.core.config import settings
from app.core.logging_config import logger


class CustomTransformerLLM(LLM):
    """
    LangChain-compatible wrapper around the custom PyTorch transformer.
    Allows the custom model to be used in LangChain LCEL chains.
    """

    model: Any = None
    tokenizer: Any = None
    device: Any = None
    max_new_tokens: int = 256

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "custom_transformer"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> str:
        from app.transformer.generate import generate

        # Encode prompt
        input_ids = self.tokenizer.encode(prompt)
        input_tensor = torch.tensor([input_ids], dtype=torch.long).to(self.device)

        # Generate
        output_ids = generate(
            model=self.model,
            input_ids=input_tensor,
            max_new_tokens=self.max_new_tokens,
            temperature=kwargs.get("temperature", 0.7),
            top_k=kwargs.get("top_k", 50),
            top_p=kwargs.get("top_p", 0.9),
            eos_token_id=self.tokenizer.eos_token_id,
        )

        # Decode only the generated part
        generated_ids = output_ids[0, len(input_ids):].tolist()
        response = self.tokenizer.decode(generated_ids)

        # Apply stop sequences
        if stop:
            for s in stop:
                if s in response:
                    response = response[:response.index(s)]

        return response.strip()


class FallbackLLM(LLM):
    """Simple deterministic fallback LLM for local/dev environments."""

    @property
    def _llm_type(self) -> str:
        return "fallback"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> str:
        response = (
            "I can help with general health information. "
            "For urgent concerns, please contact a qualified healthcare professional."
        )
        return response


def _get_device() -> torch.device:
    """Determine the best available device."""
    if settings.device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        else:
            return torch.device("cpu")
    return torch.device(settings.device)


def get_huggingface_llm():
    """
    Initialize a HuggingFace Transformers pipeline as LangChain LLM.
    """
    from langchain_huggingface import HuggingFacePipeline
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig, pipeline

    device = _get_device()
    logger.info(f"Loading HuggingFace model: {settings.llm_model} on {device}")

    tokenizer = AutoTokenizer.from_pretrained(settings.llm_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        settings.llm_model,
        device_map="auto" if device.type == "cuda" else None,
        low_cpu_mem_usage=True,
    )

    # Avoid generation-config conflicts by overriding generation params explicitly.
    generation_cfg = GenerationConfig.from_model_config(model.config)
    generation_cfg.max_new_tokens = settings.max_new_tokens
    generation_cfg.do_sample = True
    generation_cfg.temperature = 0.7
    generation_cfg.top_p = 0.9
    generation_cfg.repetition_penalty = 1.1
    model.generation_config = generation_cfg

    if device.type != "cuda":
        model = model.to(device)

    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        return_full_text=False,
    )

    llm = HuggingFacePipeline(pipeline=pipe)
    logger.info(f"HuggingFace model loaded successfully: {settings.llm_model}")
    return llm


def get_custom_transformer_llm():
    """
    Load the custom PyTorch transformer and wrap it for LangChain.
    """
    from app.transformer.model import DecoderOnlyTransformer, TransformerConfig
    from app.transformer.tokenizer_utils import TokenizerWrapper

    device = _get_device()
    logger.info("Loading custom transformer model...")

    tokenizer = TokenizerWrapper("gpt2")
    config = TransformerConfig(vocab_size=tokenizer.vocab_size)
    model = DecoderOnlyTransformer(config)

    # Load checkpoint if available
    checkpoint_path = settings.custom_model_abs_path
    if checkpoint_path.exists():
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded custom transformer from {checkpoint_path}")
    else:
        logger.warning(
            f"No checkpoint found at {checkpoint_path}. "
            "Using randomly initialized model. Train it first!"
        )

    model = model.to(device)
    model.eval()

    llm = CustomTransformerLLM(
        model=model,
        tokenizer=tokenizer,
        device=device,
        max_new_tokens=settings.max_new_tokens,
    )
    return llm


def get_ollama_llm():
    """
    Initialize Ollama-based LLM (requires Ollama server running locally).
    """
    from langchain_community.llms import Ollama

    logger.info(f"Connecting to Ollama model: {settings.llm_model}")
    llm = Ollama(model=settings.llm_model)
    return llm

def get_openai_llm():
    """
    Initialize OpenAI Chat API.
    """
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is missing, using fallback local LLM")
        return FallbackLLM()
    
    logger.info(f"Connecting to OpenAI API Model: {settings.llm_model}")
    llm = ChatOpenAI(
        model=settings.llm_model if settings.llm_model != "gpt2" else "gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.7,
        max_tokens=None
    )
    return llm

def get_groq_llm():
    """
    Initialize Groq Fast Inference API (Llama3).
    """
    from langchain_groq import ChatGroq

    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY is missing, using fallback local LLM")
        return FallbackLLM()

    logger.info(f"Connecting to Groq API Model: {settings.llm_model}")
    llm = ChatGroq(
        model_name=settings.llm_model if settings.llm_model not in ("gpt2", "llama3-8b-8192") else "llama-3.1-8b-instant",
        api_key=settings.groq_api_key,
        temperature=0.7
    )
    return llm


def get_llm():
    """
    Factory function — returns the configured LLM provider.
    """
    provider = settings.llm_provider.lower()

    if provider == "huggingface":
        return get_huggingface_llm()
    elif provider == "custom":
        return get_custom_transformer_llm()
    elif provider == "ollama":
        return get_ollama_llm()
    elif provider == "openai":
        return get_openai_llm()
    elif provider == "groq":
        return get_groq_llm()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            "Supported: huggingface, custom, ollama, openai, groq"
        )


def check_provider_connectivity(timeout_seconds: int = 8) -> tuple[bool, str]:
    """Perform lightweight provider reachability checks at startup."""
    provider = settings.llm_provider.lower()
    timeout = max(2, min(30, timeout_seconds))

    try:
        if provider == "groq":
            if not settings.groq_api_key:
                return False, "GROQ_API_KEY missing"
            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                timeout=timeout,
            )
            if r.status_code == 200:
                return True, "Groq connectivity OK"
            return False, f"Groq connectivity failed: HTTP {r.status_code}"

        if provider == "openai":
            if not settings.openai_api_key:
                return False, "OPENAI_API_KEY missing"
            r = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=timeout,
            )
            if r.status_code == 200:
                return True, "OpenAI connectivity OK"
            return False, f"OpenAI connectivity failed: HTTP {r.status_code}"

        if provider == "ollama":
            r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=timeout)
            if r.status_code == 200:
                return True, "Ollama connectivity OK"
            return False, f"Ollama connectivity failed: HTTP {r.status_code}"

        if provider in {"huggingface", "custom"}:
            return True, f"{provider} connectivity check skipped (local model path)"

        return False, f"Unsupported provider for connectivity check: {provider}"
    except Exception as exc:
        return False, f"{provider} connectivity check error: {exc}"
