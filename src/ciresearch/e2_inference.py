"""Offline MLX selector worker. It has no evaluator or label-data imports."""
import json
import os
from pathlib import Path
import resource
import sys
import time

from ciresearch.e2_prompts import E2_SYSTEM_PROMPT

MAX_PROMPT_BYTES = 1_000_000
MAX_REQUEST_BYTES = 6_500_000
MAX_RESPONSE_BYTES = 256_000
MAX_CONTEXT_TOKENS = 8192
OUTPUT_RESERVE = 128
MAX_OUTPUT_TOKENS = 128
PINNED_RUNTIME = {
    "mlx": "0.32.5", "mlx-metal": "0.32.5", "mlx-lm": "0.32.2",
    "transformers": "5.24.1", "tokenizers": "0.23.3",
}


class WorkerRequestError(ValueError):
    pass


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkerRequestError("duplicate request key")
        result[key] = value
    return result


def validate_request(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES or not raw.endswith(b"\n"):
        raise WorkerRequestError("invalid selector request frame")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _value: (_ for _ in ()).throw(
                               WorkerRequestError("invalid JSON constant")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise WorkerRequestError("selector request is malformed JSON") from error
    if type(value) is not dict or set(value) != {"prompt", "seed", "input_tokens"}:
        raise WorkerRequestError("selector worker accepts only prompt, seed, and token count")
    prompt = value["prompt"]
    if type(prompt) is not str or not prompt.strip() or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise WorkerRequestError("selector prompt is empty or over the byte cap")
    seed, input_tokens = value["seed"], value["input_tokens"]
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise WorkerRequestError("selector seed is outside the registered range")
    if type(input_tokens) is not int or not 1 <= input_tokens <= 8064:
        raise WorkerRequestError("registered prompt token count is invalid")
    return value


def render_prompt_tokens(tokenizer, prompt: str) -> tuple[str, list]:
    messages = [
        {"role": "system", "content": E2_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    chat = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    tokens = tokenizer.encode(chat, add_special_tokens=False)
    if len(tokens) + OUTPUT_RESERVE > MAX_CONTEXT_TOKENS:
        raise WorkerRequestError("selector prompt exceeds the registered context allowance")
    return chat, tokens


def _reply(value):
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii") + b"\n"
    if len(data) > MAX_RESPONSE_BYTES:
        raise SystemExit("selector worker response exceeded its cap")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main():
    if (os.environ.get("HF_HUB_OFFLINE") != "1"
            or os.environ.get("TRANSFORMERS_OFFLINE") != "1"
            or os.environ.get("HF_HUB_DISABLE_IMPLICIT_TOKEN") != "1"):
        raise SystemExit("offline inference environment is required")
    if len(sys.argv) != 2:
        raise SystemExit("a single verified local model directory is required")
    model_path = Path(sys.argv[1]).resolve(strict=True)
    if not (model_path / "model.safetensors").is_file():
        raise SystemExit("verified local model weights are required")

    from importlib.metadata import version
    for package, expected in PINNED_RUNTIME.items():
        try:
            actual = version(package)
        except Exception as error:
            raise SystemExit(f"required offline runtime package is unavailable: {package}") from error
        if actual != expected:
            raise SystemExit(f"offline runtime package pin mismatch: {package}")

    start = time.monotonic()
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer, config = load(str(model_path), tokenizer_config={"trust_remote_code": False},
                                    return_config=True, trust_remote_code=False)
    if config["model_type"] != "qwen2" or config["quantization"]["bits"] != 4:
        raise SystemExit("unexpected pinned selector checkpoint configuration")
    _reply({"status": "ready", "load_seconds": time.monotonic() - start,
            "device": str(mx.default_device()), "model_type": config["model_type"],
            "quantization_bits": config["quantization"]["bits"],
            "peak_mlx_bytes": mx.get_peak_memory()})

    while True:
        raw = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            return
        request = validate_request(raw)
        _chat, tokens = render_prompt_tokens(tokenizer, request["prompt"])
        if len(tokens) != request["input_tokens"]:
            raise SystemExit("selector prompt token count differs from frozen registration")
        started = time.monotonic()
        mx.reset_peak_memory()
        mx.random.seed(request["seed"])
        token_ids, parts = [], []
        try:
            for response in stream_generate(
                    model, tokenizer, tokens, max_tokens=MAX_OUTPUT_TOKENS,
                    sampler=make_sampler(temp=0.7, top_p=0.95)):
                token_ids.append(response.token)
                parts.append(response.text)
        except Exception as error:
            _reply({"status": "infrastructure_error", "text": "".join(parts),
                    "token_ids": token_ids, "observed_partial_tokens": len(token_ids),
                    "input_tokens": len(tokens), "exception": type(error).__name__,
                    "wall_seconds": time.monotonic() - started,
                    "peak_mlx_bytes": mx.get_peak_memory(),
                    "host_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
            return
        if len(token_ids) != response.generation_tokens or len(token_ids) > MAX_OUTPUT_TOKENS:
            raise SystemExit("selector output token accounting exceeded its limit")
        _reply({
            "status": "ok", "text": "".join(parts), "token_ids": token_ids,
            "input_tokens": len(tokens), "output_tokens": response.generation_tokens,
            "finish_reason": response.finish_reason,
            "prefill_tokens_per_second": response.prompt_tps,
            "decode_tokens_per_second": response.generation_tps,
            "wall_seconds": time.monotonic() - started,
            "peak_mlx_bytes": mx.get_peak_memory(),
            "host_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        })


if __name__ == "__main__":
    main()
