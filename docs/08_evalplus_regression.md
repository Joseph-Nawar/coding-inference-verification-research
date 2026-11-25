# Reproduce the synthetic EvalPlus regression

The fixture compares the upstream `untrusted_check` source from three immutable revisions. It contains independently authored code strings and synthetic inputs. It does not load benchmark datasets or call model backends. Run it only with the documented restricted Linux ARM64 Docker Desktop profile. This image contains official checker code and serves only this synthetic diagnostic.

## Inputs

| EvalPlus source revision | GitHub archive SHA-256 |
| --- | --- |
| `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2` | `9586c229e27fded15a67eb9c306a4b7b26aec920d16abadd9e6f4bb34ea83551` |
| `6eb1e199c2e370518e7bf3e8eee6322c2b23c89c` | `453d576a6e1c19b781e34c75113cc77e798e423c9b7f251f83b1d00d6b3121be` |
| `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e` | `a0bba19b3a3d1054d064939866befbfafe6c1ab43ded24f16ff2e26703aa1d47` |

Fetch each archive from `https://codeload.github.com/evalplus/evalplus/tar.gz/<revision>`. Fetch the CPython 3.12 manylinux2014 AArch64 NumPy 2.2.6 and ABI3 manylinux2014 AArch64 psutil 7.0.0 wheels from their PyPI release files. Verify every source archive against the table before extraction. The Dockerfile verifies both wheels using the hash lock with no dependency downloads. [EvalPlus source](https://github.com/evalplus/evalplus) · [NumPy release](https://pypi.org/project/numpy/2.2.6/#files) · [psutil release](https://pypi.org/project/psutil/7.0.0/#files) · [Fixture lock](../configs/evalplus-regression-arm64.txt)

Use an ignored build directory. For each extracted source archive, copy the files below to `$build/sources/<revision>/`, keeping their relative paths. Retain each upstream license with its files in the local build context.

```text
LICENSE
evalplus/__init__.py
evalplus/config.py
evalplus/eval/__init__.py
evalplus/eval/utils.py
evalplus/eval/_special_oracle.py
```

## Build and run

```sh
build=.research-private/fixture-build
evidence=.research-private/fixture-evidence
mkdir -p "$build"
# Place the two verified wheels, source slices and licenses as described above.
cp configs/evalplus-regression-arm64.txt "$build/requirements.txt"
cp tests/evalplus_regression.py "$build/"
docker --context desktop-linux pull --platform linux/arm64 \
  docker.io/library/python@sha256:3f9c7f75b916e8279e24136d7a57769aba9e193715be52570417698c52d6eed0
docker --context desktop-linux build --platform linux/arm64 --network none \
  --pull=false --iidfile "$build/image.id" -f sandbox/Dockerfile.evalplus-regression "$build"
python3 tests/run_evalplus_regression.py "$(cat "$build/image.id")" "$evidence"
```

Use a new evidence directory for each run. The launcher inspects each newly created container before starting it and force-removes it by ID in cleanup. It retains combined bounded output, inspect JSON and engine exit state. Inside the container the fixture verifies the network interface state, a read-only root, writable tmpfs, Docker socket absence, user, capabilities, seccomp and no-new-privileges. The 30-second host attach timeout is separate from the per-case timings under test. The output-size bound is 64 KiB per invocation. The host never imports the upstream evaluator or executes fixture code strings.

The expected results include two known failures for valid roots under v0.3.1, a successful valid-root check under each fixed revision, and a timeout decision that differs only under the later default. These are expected checker verdicts. A passing regression invocation means the observed verdict and detail vector matched the registered fixture expectation. [Evaluator decision](../reports/EVALPLUS_DECISION_V1.md)
