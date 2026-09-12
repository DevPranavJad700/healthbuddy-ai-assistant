"""BLEU evaluation for HealthBuddy.

Modes:
- precomputed: uses model_response from input file
- live_api: calls /api/v1/chat to generate model outputs
"""

import argparse
import json
import time
import uuid
from pathlib import Path

import nltk
import requests
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu


def load_test_data(path: str) -> list[dict]:
    """Load test Q&A pairs."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_bleu(reference: str, hypothesis: str) -> dict:
    """
    Calculate BLEU scores (1-4) for a single reference-hypothesis pair.

    Args:
        reference: Ground truth answer.
        hypothesis: Model-generated answer.

    Returns:
        Dictionary with BLEU-1 through BLEU-4 scores.
    """
    ref_tokens = nltk.word_tokenize(reference.lower())
    hyp_tokens = nltk.word_tokenize(hypothesis.lower())

    smoothie = SmoothingFunction().method1

    scores = {}
    for n in range(1, 5):
        weights = tuple([1.0 / n] * n + [0.0] * (4 - n))
        scores[f"bleu_{n}"] = sentence_bleu(
            [ref_tokens], hyp_tokens, weights=weights, smoothing_function=smoothie
        )

    return scores


def evaluate_model(
    test_data: list[dict],
    model_fn=None,
) -> dict:
    """
    Evaluate model responses against reference answers.

    Args:
        test_data: List of {"question": ..., "answer": ..., "model_response": ...} dicts.
        model_fn: Optional function that takes a question and returns a response.
                  If provided, generates responses. Otherwise uses pre-computed responses.

    Returns:
        Evaluation results with per-sample and aggregate scores.
    """
    results = []
    totals = {"bleu_1": 0, "bleu_2": 0, "bleu_3": 0, "bleu_4": 0}

    for item in test_data:
        reference = item["answer"]

        if model_fn:
            hypothesis = model_fn(item["question"])
        elif "model_response" in item:
            hypothesis = item["model_response"]
        else:
            continue

        scores = calculate_bleu(reference, hypothesis)

        result_row = {
            "question": item["question"],
            "reference": reference[:100] + "..." if len(reference) > 100 else reference,
            "hypothesis": hypothesis[:100] + "..." if len(hypothesis) > 100 else hypothesis,
            **scores,
        }
        if "meta" in item:
            result_row["meta"] = item["meta"]
        results.append(result_row)

        for k in totals:
            totals[k] += scores[k]

    n = len(results)
    avg_scores = {k: v / max(n, 1) for k, v in totals.items()}

    return {
        "num_samples": n,
        "average_scores": avg_scores,
        "per_sample": results,
    }


def print_results(results: dict):
    """Pretty print evaluation results."""
    print("\n" + "=" * 60)


def make_live_api_model_fn(
    base_url: str,
    use_rag: bool,
    disable_cache: bool,
    timeout_seconds: int,
):
    """Return a model_fn(question)->response that calls live API."""

    base = base_url.rstrip("/")

    def _model_fn(question: str) -> str:
        session_id = f"eval_{uuid.uuid4().hex[:10]}"
        payload = {
            "message": question,
            "use_rag": use_rag,
            "disable_cache": disable_cache,
            "session_id": session_id,
        }
        started = time.perf_counter()
        r = requests.post(f"{base}/api/v1/chat", json=payload, timeout=timeout_seconds)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from /api/v1/chat")
        data = r.json()
        text = (data.get("response") or "").strip()
        if not text:
            raise RuntimeError("Empty response from live API")
        data["_eval_latency_ms"] = round(elapsed_ms, 2)
        return text

    return _model_fn
    print("HealthBuddy AI — BLEU Score Evaluation")
    print("=" * 60)
    print(f"\nSamples evaluated: {results['num_samples']}")

    print("\n--- Average Scores ---")
    for metric, score in results["average_scores"].items():
        bar = "█" * int(score * 40) + "░" * (40 - int(score * 40))
        print(f"  {metric.upper()}: {score:.4f} |{bar}|")

    print("\n--- Per-Sample Results (Top 5) ---")
    for i, sample in enumerate(results["per_sample"][:5], 1):
        print(f"\n  [{i}] Q: {sample['question'][:60]}...")
        print(f"      BLEU-4: {sample['bleu_4']:.4f}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Evaluate HealthBuddy model with BLEU scores")
    parser.add_argument(
        "--test-data",
        default="./evaluation/test_queries.json",
        help="Path to test queries JSON file",
    )
    parser.add_argument(
        "--output",
        default="./evaluation/results.json",
        help="Path to save evaluation results",
    )
    parser.add_argument(
        "--mode",
        choices=["precomputed", "live_api"],
        default="live_api",
        help="Evaluation mode. live_api calls /api/v1/chat; precomputed reads model_response from file.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for live_api mode",
    )
    parser.add_argument(
        "--use-rag",
        action="store_true",
        default=True,
        help="Use RAG for live_api mode (default: true)",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG for live_api mode",
    )
    parser.add_argument(
        "--disable-cache",
        action="store_true",
        help="Disable response cache in live_api mode for truer latency/accuracy measurement.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Request timeout for each live API call",
    )
    args = parser.parse_args()

    # Download required NLTK data
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)

    # Load test data
    test_data = load_test_data(args.test_data)
    print(f"Loaded {len(test_data)} test samples")

    model_fn = None
    if args.mode == "precomputed":
        missing = [i for i, row in enumerate(test_data) if "model_response" not in row]
        if missing:
            raise SystemExit(
                f"precomputed mode requires model_response in all rows; missing at indices: {missing[:5]}"
            )
    else:
        model_fn = make_live_api_model_fn(
            base_url=args.base_url,
            use_rag=not args.no_rag,
            disable_cache=args.disable_cache,
            timeout_seconds=max(10, args.timeout_seconds),
        )

    results = evaluate_model(test_data, model_fn=model_fn)
    if results["num_samples"] == 0:
        raise SystemExit("No samples were evaluated")
    print_results(results)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
