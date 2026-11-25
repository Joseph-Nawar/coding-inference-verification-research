# P0 command record

25 November 2026. The commands below reproduce the principal metadata and provenance checks. Raw sources, the metadata-only audit script and its output, the ordered split commitment, package resolution logs, and fetched artifacts are under `.research-private/p0/`. The script intentionally refuses to overwrite its existing commitment. Use a new isolated evidence directory to replay it.

```sh
uname -sm
sw_vers
sysctl hw.model hw.memsize hw.logicalcpu vm.swapusage
system_profiler SPHardwareDataType
df -k .
memory_pressure -Q
git rev-parse --show-toplevel
git init -b main
uv python list --only-installed
docker context show
docker version
docker desktop status
docker desktop start --timeout 60
docker info --format '{{.Architecture}} {{.MemTotal}} {{.NCPU}} {{json .SecurityOptions}}'
docker system df
docker buildx imagetools inspect --raw python:3.12.13-slim-bookworm
docker buildx imagetools inspect --raw python@sha256:3f9c7f75b916e8279e24136d7a57769aba9e193715be52570417698c52d6eed0
```

```sh
p=.research-private/p0
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
hf models info mlx-community/Qwen2.5-Coder-3B-Instruct-4bit --expand sha,cardData,siblings --format json
hf models info Qwen/Qwen2.5-Coder-3B-Instruct --expand sha,cardData --format json
hf download mlx-community/Qwen2.5-Coder-3B-Instruct-4bit README.md config.json tokenizer_config.json --revision 3dd939c621c08e5753d5b89f35a2642cd83b98ca --local-dir "$p/model-metadata"
curl -fsSL https://huggingface.co/api/models/mlx-community/Qwen2.5-Coder-3B-Instruct-4bit/tree/3dd939c621c08e5753d5b89f35a2642cd83b98ca -o "$p/mlx-tree.json"
git ls-remote https://github.com/evalplus/evalplus.git 'refs/tags/v0.3*'
curl -fsSL https://codeload.github.com/evalplus/evalplus/tar.gz/e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2 -o "$p/evalplus.tar.gz"
curl -fsSL https://pypi.org/pypi/evalplus/0.3.1/json -o "$p/evalplus-pypi.json"
unzip -p "$p/evalplus-0.3.1-py3-none-any.whl" evalplus/eval/__init__.py > "$p/eval-wheel.py"
cmp "$p/eval-wheel.py" "$p/upstream/evalplus/eval/__init__.py"
curl -fsSL https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus.jsonl.gz -o "$p/HumanEvalPlus.jsonl.gz"
curl -fsSL https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus.jsonl.gz -o "$p/MbppPlus.jsonl.gz"
gzip -t "$p/HumanEvalPlus.jsonl.gz" "$p/MbppPlus.jsonl.gz"
python3 "$p/audit_split.py" > "$p/split-audit.json"
```

The first Docker client probe failed with a missing Desktop socket. The daemon started successfully and the repeat client/VM probes succeeded. Package-resolution attempts and results are recorded in the status file and private logs. Scorer source and wheel equality, gzip integrity and split/schema inspection were P0 checks. See the [P1 status](P1_SMOKE.md) for the runtime checks gated by P0.

```sh
p=.research-private/p0
UV_CACHE_DIR="$PWD/$p/uv-cache" uv pip compile "$p/inference.in" --default-index https://pypi.org/simple --python-version 3.12.15 --python-platform aarch64-apple-darwin --generate-hashes --no-build --output-file "$p/inference.lock"
MACOSX_DEPLOYMENT_TARGET=26.4 UV_CACHE_DIR="$PWD/$p/uv-cache-host" uv pip compile "$p/inference.in" --default-index https://pypi.org/simple --python "$USER_LOCAL_PYTHON_312" --generate-hashes --no-build --output-file "$p/inference.lock"
UV_CACHE_DIR="$PWD/$p/uv-cache" uv pip compile "$p/evaluation.in" --default-index https://pypi.org/simple --python-version 3.12.13 --python-platform aarch64-unknown-linux-gnu --generate-hashes --output-file "$p/evaluation.lock"
UV_CACHE_DIR="$PWD/$p/uv-cache" uv pip compile "$p/evaluation.in" --default-index https://pypi.org/simple --python-version 3.12.13 --python-platform aarch64-unknown-linux-gnu --generate-hashes --no-build --offline --output-file "$p/evaluation.lock"
```

The inputs contain `mlx-lm==0.32.2` and `evalplus==0.3.1` respectively. `USER_LOCAL_PYTHON_312` denotes the installed arm64 CPython 3.12.15 executable. The first command failed, the second resolved successfully, the third was interrupted, and the fourth failed with a wheel-only constraint. The third command is recorded for provenance. Replaying it requires a separately reviewed way to handle source distributions.

The first final YAML check used `Psych.safe_load_file`, which is unavailable in the system Ruby. The replacement `Psych.safe_load(File.read(...))` verified the disabled P1 entry and confirmation gate plus the 24-call cap. This was an artifact-validation command error.
