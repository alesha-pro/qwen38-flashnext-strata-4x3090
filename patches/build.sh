#!/usr/bin/env bash
# Strata v0.2.10 (engine 0.1.56) + PR #2590 (session files on a layer split), sm_86, CUDA 12.6.
# Source = the v0.2.10 release source tarball (engines/strata/0.2.10/dist) with pr2590-on-0.2.0-beta.diff applied
# (9 of 10 hunks; the parking refactor hunk is not needed: 0.2.10 parks through ParkSource). See README.md.
set -uo pipefail
D=/mnt/nvme/engines/strata/0.2.10-sessions
BT=/mnt/nvme/engines/strata/0.2.0-beta-sessions/buildtools
export CUDA_VISIBLE_DEVICES=
export PATH=$BT/bin:$PATH
cmake -S $D/source -B $D/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc -DCUDAToolkit_ROOT=/usr/local/cuda-12.6 -DSTRATA_BUILD_TESTS=OFF -DSTRATA_BUILD_CONVERSATION_TESTS=ON -DSTRATA_GGML_DIR=$D/llama.cpp-3cf0325 -DIQ_FIXTURE_PYTHON=/mnt/nvme/engines/flashnext-schnelle-20260929/venv/bin/python > $D/configure.log 2>&1 || { echo configure-failed > $D/build.exit; exit 1; }
nice -n 10 cmake --build $D/build --target strata conversation_file_test conversation_snapshot_test --parallel 24 > $D/build.log 2>&1
echo $? > $D/build.exit
