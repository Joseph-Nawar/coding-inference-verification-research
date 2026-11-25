"""Offline, prompt-only MLX subprocess. No evaluator or benchmark imports."""

import json
import os
from pathlib import Path
import resource
import sys
import time


def main():
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise SystemExit("offline inference is required")
    model_path = Path(sys.argv[1]).resolve(strict=True)
    if not (model_path / "model.safetensors").is_file():
        raise SystemExit("verified local weights are required")

    def reply(value):
        print(json.dumps(value, allow_nan=False), flush=True)

    start = time.monotonic()
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer, config = load(str(model_path), tokenizer_config={"trust_remote_code": False},
                                    return_config=True, trust_remote_code=False)
    if config["model_type"] != "qwen2" or config["quantization"]["bits"] != 4:
        raise SystemExit("unexpected checkpoint configuration")
    reply({"status": "ready", "load_seconds": time.monotonic() - start,
           "device": str(mx.default_device()), "peak_mlx_bytes": mx.get_peak_memory()})

    while raw := sys.stdin.buffer.readline(65_537):
        if not raw.endswith(b"\n") or len(raw) > 65_536:
            raise SystemExit("prompt frame exceeds limit")
        request = json.loads(raw)
        if type(request) is not dict or set(request) != {"prompt", "seed"}:
            raise SystemExit("inference accepts only a prompt and seed")
        messages = [
            {"role": "system", "content": "Solve the Python function task. Return complete Python code only."},
            {"role": "user", "content": request["prompt"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        tokens = tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) + 768 > 8192:
            raise ValueError("context limit exceeded")
        started = time.monotonic()
        mx.reset_peak_memory()
        mx.random.seed(request["seed"])
        token_ids = []
        text_parts = []
        try:
            for response in stream_generate(model, tokenizer, tokens, max_tokens=768,
                                            sampler=make_sampler(temp=0.7, top_p=0.95)):
                token_ids.append(response.token)
                text_parts.append(response.text)
        except Exception as exc:
            reply({"status": "infrastructure_error", "text": "".join(text_parts),
                   "token_ids": token_ids, "input_tokens": len(tokens),
                   "observed_partial_tokens": len(token_ids), "exception": type(exc).__name__})
            return
        if len(token_ids) != response.generation_tokens:
            raise RuntimeError("generation token accounting disagreed")
        reply({
            "status": "ok", "text": "".join(text_parts), "token_ids": token_ids,
            "input_tokens": len(tokens), "output_tokens": response.generation_tokens,
            "prefill_tokens_per_second": response.prompt_tps, "decode_tokens_per_second": response.generation_tps,
            "finish_reason": response.finish_reason, "wall_seconds": time.monotonic() - started,
            "peak_mlx_bytes": mx.get_peak_memory(), "host_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        })


if __name__ == "__main__":
    main()
