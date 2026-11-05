<h1 align="center">Qwen3.8-Flash-Next on 2x RTX 3090</h1>

<p align="center">
  <b>150 tok/s on code. 262K context. 0 refusals.</b><br>
  unsloth Dynamic v3.1 UD-IQ4_XS · Strata 0.2.10 · DFlash2 drafter · my own refusal vector
</p>

<p align="center">
  <img alt="GPUs" src="https://img.shields.io/badge/GPUs-2x%20RTX%203090-2a78d6">
  <img alt="VRAM" src="https://img.shields.io/badge/VRAM-48%20GB-2a78d6">
  <img alt="context" src="https://img.shields.io/badge/context-262K-1c5cab">
  <img alt="engine" src="https://img.shields.io/badge/engine-Strata%200.2.10-1c5cab">
  <img alt="refusals" src="https://img.shields.io/badge/refusals-0%20of%20146-0d366b">
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/speed-dark.svg">
    <img alt="Decode speed on 2x RTX 3090: code 147-152, file edits 150-163, English prose 123-131, Russian 112-116 tok/s from 2K to 128K context" src="assets/speed-light.svg" width="860">
  </picture>
</p>

The model does not fit in 48 GB of VRAM. The weights are 65 GB plus a 29 GB n-gram table, and Strata keeps the most used
experts on the GPUs and computes the rest on the CPU. With the DFlash2 block drafter on top, two 3090s decode code at 150 tok/s
and speed barely moves between 2K and 128K of context.

This repo is the full recipe: pinned versions with checksums, the exact server config, every flag that mattered, the raw
benchmark traces, the refusal vectors, and a patch that keeps a long conversation alive across a server restart.
No weights here, everything downloads from the original repos.

**Contents**
[Numbers](#numbers) ·
[1 to 4 cards](#1-to-4-cards) ·
[Stack](#stack) ·
[Run it](#run-it) ·
[Flags that matter](#flags-that-matter) ·
[What did not help](#what-did-not-help) ·
[Refusal vector](#refusal-vector) ·
[Sessions across restarts](#sessions-across-restarts) ·
[Raw data](#raw-data) ·
[Credits](#credits)

## Numbers

2x RTX 3090 at 300 W, layer split, 262K context window, int8 KV, refusal vector on. One request at a time, greedy,
512 new tokens, no thinking, a fresh prompt every time (no prefix reuse). Decode in tok/s, mean of repeats 1 and 2
(repeat 0 is the first request after load, while the expert cache is still adapting).

| Task | 2K | 16K | 64K | 128K |
|---|---:|---:|---:|---:|
| Code (write a module) | 152 | 151 | 152 | 147 |
| File edits (copy code with renames) | 159 | 163 | 161 | 150 |
| English prose | 131 | 126 | 124 | 123 |
| Russian prose | 114 | 115 | 116 | 112 |
| **Prefill, tok/s** | 680 | 2,550 | 3,440 | 3,540 |

Run [`20261105T003504Z-3b9c9622`](bench/results/20261105T003504Z-3b9c9622). Per-request ranges across all four depths:
code 146-153, file edits 149-168, prose 121-132, Russian 111-119.

## 1 to 4 cards

The same config on 1, 2, 3 and 4 cards. The second card is the big step. Cards 3 and 4 add prefill on long prompts
and little decode, because a layer split runs the cards one after another.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/cards-dark.svg">
    <img alt="Decode at 16K on 1, 2, 3 and 4 cards: the second card adds 31 to 38 percent" src="assets/cards-light.svg" width="860">
  </picture>
</p>

| Cards | Code 16K | Prose 16K | Russian 16K | Code 64K | Prefill 64K |
|---|---:|---:|---:|---:|---:|
| 1 | 110 | 91 | 87 | 106 | 1,940 |
| 2 | 144 | 126 | 118 | 145 | 3,410 |
| 3 | 153 | 128 | 116 | 148 | 3,860 |
| 4 | 149 | 124 | 112 | 141 | 4,080 |

Run [`20261105T082238Z-e0c77fe0`](bench/results/20261105T082238Z-e0c77fe0). The 2-card row is a few percent under the
table above: different day, same config, normal run-to-run spread.

## Stack

| Part | Version | Where |
|---|---|---|
| Model | unsloth `UD-IQ4_XS`, Dynamic v3.1 | [`unsloth/Qwen3.8-Flash-Next-GGUF`](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF) @ `d96201194f103c906994f283f504209dc8d2a10c` |
| Vision projector | `mmproj-BF16.gguf` | same repo and revision |
| Drafter | DFlash2 | [`incoai/Qwen3.8-Flash-Next-DFlash2`](https://huggingface.co/incoai/Qwen3.8-Flash-Next-DFlash2) @ `a22a1744e85c17364dcc54a6a420af7135d4c7f6` |
| Engine | Strata 0.2.10 (Control and engine 0.1.56) | [`Niko1221/Strata`](https://github.com/Niko1221/Strata) release v0.2.10, `linux-x86_64-cuda-cuda13` |
| Refusal vector | `mix-r1` | [`vectors/`](vectors) |
| Session patch (optional) | PR #2590 ported to 0.2.10 | [`patches/`](patches) |

<details>
<summary>SHA256 of every file</summary>

```
93ff23a08e5cd7501f24fa16f5b415d5807d0175e04edd3ed6a7a41b601a4eef  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00004.gguf
13d5dc8b93d039e4cfade5a9af7037f10c97f7ec4e53f75bd2e9ae34aae54aeb  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00004.gguf
f6b9b5934908a2043732269dd740155d0f921d0763a1dcdd3452246311651f87  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00004.gguf
5de8b5dbf89409acc39468decafd4a4a95b13c29d88a14b0356107897829ec36  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00004-of-00004.gguf  (n-gram table, same file as in UD-Q4_K_XL)
2e788f8c511d8093c7b43cb87b2fd7e14228340318057f8fb20c86df2efe2355  mmproj-BF16.gguf
d6723f2a359eaf33ec0c95f22ae8edda896774020c552296a85e1913b4d3186f  incoai DFlash2 model.safetensors
2409575986f9ea24d455343eb469c0e6940def5edab1d1be503bb8eb4cc3b1b9  incoai DFlash2 config.json
4a42b98220ea7880664002c8edda1563aecbae754b762a2e2f31b2b91ee93ecd  qwen3.8-flash-next-dflash2.q4_0-selq4.pack  (built below, matches the pack Strata pins)
cda40d62d0eb8f37ed6e272142641a1d2f0de4a32f9e14d0416e7a71534849f1  qwen3.8-flash-next-dflash2.q4_0.pack
25d7fd1670a2e0ec885868d1718d410a3baab03bceeacf0a156cf93ffe4e1ef4  draft_vocab_cyrillic.bin  (ships with Strata in control/data)
b1e1d3a7a9e4bf862dcd5923ce661fb59bbd07907e594df5cf86a62ac235cb91  draft_vocab.bin
df6a6dfd806289caa42becd2acc14081815bedac9ec8f5efa3821a7d10582ee5  strata-engine-0.1.56-linux-x86_64-cuda-cuda13.tar.gz
9fde2c69d8509b22984a8402505cb49300f70df82f4d6033ab73e32592e799e5  strata-control-0.1.56-linux-x86_64.tar.gz
82902362c1e9207a2da158ea678ba9d78f9821070d912f15d98efe41ef5fdc86  vectors/qwen38-flashnext-refusal-mix-r1.gguf
```
</details>

### The box

| | |
|---|---|
| GPUs | 4x RTX 3090 24 GB, this setup uses 2 of them. 300 W each, PCIe 3.0 x16, driver 610.43.02 |
| CPU | AMD EPYC 7642 (48 cores) |
| RAM | 4x 64 GB DDR4-2133 in channels A-D. **NPS2 in BIOS**: STREAM Triad went from ~20 to ~41 GB/s on this layout |
| Disks | weights on a SATA SSD, the 29 GB n-gram table on an NVMe |

Misses in the expert cache run on the CPU and read RAM, so memory bandwidth shows up directly in decode speed.

## Run it

**1. Strata 0.2.10.** Take the release tarballs from [Niko1221/Strata](https://github.com/Niko1221/Strata/releases) and
check them against the release `SHA256SUMS.txt`. Control comes with its own Python.

**2. Weights and drafter.**

```bash
hf download unsloth/Qwen3.8-Flash-Next-GGUF --revision d96201194f103c906994f283f504209dc8d2a10c \
  --include "UD-IQ4_XS/*" --include mmproj-BF16.gguf --local-dir models/qwen38-flashnext
hf download incoai/Qwen3.8-Flash-Next-DFlash2 --revision a22a1744e85c17364dcc54a6a420af7135d4c7f6 \
  --local-dir models/dflash2-src
```

Shard 4 (the n-gram table) can live on another disk behind a symlink. I keep it on NVMe and run with `--ple-io direct`.

**3. Packs.** From the Strata `control/` folder:

```bash
M=models/qwen38-flashnext
python tools/iq_pack.py --gguf $M/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00004.gguf \
  --out $M/packs/ud-iq4_xs --compat-bf16
mkdir -p $M/dflash2
python tools/dflash2_pack.py models/dflash2-src/model.safetensors models/dflash2-src/config.json \
  $M/dflash2/qwen3.8-flash-next-dflash2.q4_0-selq4.pack --q4_0 --q4_0-selector
cp data/draft_vocab.bin data/draft_vocab_cyrillic.bin $M/dflash2/
```

Strata looks for the drafter in `dflash2/` next to `packs/`. Unsloth v3.1 moved the n-gram table into its own shard, and
`iq_pack.py` handles that layout as is.

**4. Config.** [`configs/service.json`](configs/service.json) is the exact file my service runs, with my paths. Change the
paths, keep the rest. Two lines decide whether DFlash2 starts at all:

```json
"model_name": "qwen3.8-flash-next-unsloth-ud-iq4_xs",
"drafting": "dflash2",
```

**5. Start.**

```bash
cd strata/control
python/bin/python3 -m serve.server --engine strata --config /path/to/service.json \
  --port 18000 --gpu 0,1 --no-api-key
```

It loads in 26-44 s from page cache. Then it is a normal OpenAI API on `/v1` with images. The server log line
`drafting: DFlash2 alone (--draft dflash2, --draft-conf 0.5)` means the drafter is on. My systemd unit is in [`deploy/`](deploy).

## Flags that matter

| Flag | Why |
|---|---|
| `"model_name": "qwen3.8-flash-next-unsloth-*"` | `serve.server` turns DFlash2 on only for names matching this pattern. Any other name and it silently runs MTP. If your clients know an old name, put it in `"aliases"` |
| `--draft-conf 0.5` (in `user_args`) | Strata's default is 0.35, and at 0.35 DFlash2 only ties MTP here. At 0.5 it is 8-15% faster than MTP (prose 109 vs 95, code 121 vs 110 on UD-Q4_K_XL). 0.65 is worse than 0.5 |
| `--mtp-draft-vocab .../draft_vocab_cyrillic.bin` | The default draft vocabulary has almost no Cyrillic. Russian draft acceptance goes from 32% to 54% and Russian decode from 78-81 to 94-101 tok/s. English and code do not lose anything |
| `--vram-reserve-later-mib 1394` | On a layer split the drafter (688 MiB) lands on the last card and the split plan does not count it, so that card ends up with 74-108 MiB free. The engine prints this exact number as advice |
| `--vram-reserve-mib 768` | Room for the vision encoder on the first card |
| `--ple-io direct` | Reads the n-gram table from disk instead of holding 27 GiB in RAM. Decode is the same, prefill is about 3% lower |
| `STRATA_HC_Q8=1`, `STRATA_ROUTE_TAIL_SKIP=0` | What Strata's own setup writes for unsloth UD files |
| `--kv int8`, `--max-context 262144` | Full context, KV at 8 bit. I did not go lower on KV |
| `user_args` | `"drafting": "dflash2"` rebuilds the drafter arguments at start. Your own drafter flags only survive in `user_args` |

## What did not help

Measured on 2 cards, all within noise or worse:

- `--spec 7` instead of 6, `STRATA_ROUTE_TAIL_SKIP=7`, `--adapt-async 1`, `STRATA_SPLIT_OVERLAP=1`, `--pipeline-windows 2`.
- `--kv-resident 32768` (KV streaming) keeps decode the same and drops prefill by 6-10%.
- A 128K window instead of 262K: +3-5% decode from extra expert slots. I kept 262K.

Other quants on the same bench (2 cards, 16K, DFlash2 at 0.5), with KL to Q8_0 from Strata's `docs/QUANTS.md`:

| Quant | Prose | Code | File edits | KL to Q8_0 |
|---|---:|---:|---:|---:|
| ISTA-DASLab IQ3_S | 138-147 | 164-166 | 192-204 | 0.144 |
| **unsloth UD-IQ4_XS** | 126-130 | 146-149 | 141-167 | 0.101 |
| unsloth UD-Q4_K_XL | 102-110 | 117-119 | 97-108 | 0.056 |

Speed follows how many experts fit in VRAM and how big they are. IQ3_S is faster and less accurate, Q4_K_XL is more
accurate and slower. IQ4_XS is the middle and it is what I run.

## Refusal vector

[`vectors/`](vectors) has two control vectors for Strata's built-in projection mode. The shipped one is `mix-r1`:
my own refusal direction mixed per layer with the refusal direction published by huihui-ai, then renormalized.
How I extract my direction stays with me, the vectors are free to use.

```text
--control-vector-scaled vectors/qwen38-flashnext-refusal-mix-r1.gguf:1.0
--control-vector-layer-range 1 47 --cvec-mode project --cvec-dir per-layer
```

Results on UD-IQ4_XS, 2 cards. Refusals counted on AdvBench validation (64), JailbreakBench (82) and 64 harmless prompts
(false refusals). KL and top-1 agreement are teacher-forced against the same model without the vector, 6x1024 tokens of
prose and 6x1024 of code.

| Vector | AdvBench | JailbreakBench | Harmless | KL prose / code | Top-1 prose / code | Perplexity |
|---|---:|---:|---:|---|---|---|
| none | 64 / 64 | 78 / 82 | 0 / 64 | | | |
| **mix-r1** | **0** | **0** | **0** | **0.029 / 0.011** | **95.4 / 97.4%** | **+0.5 / +0.2%** |
| own-NX | 0 | 1 | 1 | 0.039 / 0.018 | 94.6 / 96.9% | +1.6 / +0.8% |
| huihui r alone | 1 | 1 | 0 | 0.028 / 0.011 | 95.5 / 97.6% | +0.5 / +0.2% |

With thinking on (xhigh, up to 2048 tokens): mix-r1 refused 0 of 32 and 0 of 32, the stock model refused 16 of 16.
Russian, code, tool calls and long answers read normal, no loops, and DFlash2 acceptance does not change with the vector on.
One request can turn it off with `"experimental_speed_projection": false`.

## Sessions across restarts

Strata 0.2.10 refuses to save a session on a layer split (`session files do not support --layer-split`). PR #2590 added
that and was never merged. [`patches/`](patches) has it ported to the 0.2.10 source, plus one fix so a one-card save works
with DFlash2. My service runs this build.

| | Release binary | 0.2.10 + patch |
|---|---:|---:|
| Code 16K / 64K | 148-150 / 141-144 | 144-151 / 145-152 |
| Prose 16K / 64K | 122-129 / 118-119 | 125-128 / 121 |
| Russian 16K / 64K | 116-118 / 115-117 | 112-115 / 109-116 |
| Prefill 64K | 3,420 | 3,420 |

Same speed. A 55K-token conversation on 2 cards saves in 0.5 s (1.0 GB file) and restores in 0.7 s. After the restore
the next turn reads 33 new tokens instead of 55K and gives the same answer as without the restart. A file saved on
2 cards and loaded on 3 gets a clean 400 and the server keeps going. Details in [`patches/README.md`](patches/README.md).

## Raw data

- [`bench/results/`](bench/results) has every run used here. Each arm keeps `config.json`, `launch.json` (full engine argv),
  `result.json` (every request with the engine's own timings), `engine.log` and `server.log`.
- [`bench/speed-benchmarks.jsonl`](bench/speed-benchmarks.jsonl) is the same 351 measurements as flat rows.
- [`bench/bench.py`](bench/bench.py) is the harness, [`bench/plans/`](bench/plans) the exact plans, and
  [`bench/session_test.py`](bench/session_test.py) the save, restart, restore check.
- [`assets/make_charts.py`](assets/make_charts.py) redraws both charts from `bench/results`.

| Run | What |
|---|---|
| `20261105T003504Z-3b9c9622` | final build, 2K to 128K, 4 tasks |
| `20261105T082238Z-e0c77fe0` | 1 / 2 / 3 / 4 cards, plus `--kv-resident` |
| `20261105T091335Z-7e919ade` | release binary vs patched build, session tests |
| `20261105T092013Z-94c00b29` | session tests after the one-card fix |
| `20261104T222523Z-5a37f904` | UD-IQ4_XS, DFlash2 vs MTP |
| `20261104T212010Z-e4fd4fcb` | tuning arms, ISTA IQ3_S |
| `20261104T205722Z-50cfb756` | `--draft-conf` 0.35 / 0.5 / 0.65 |
| `20261104T202130Z-68274720` | UD-Q4_K_XL on 2 cards, MTP, DFlash2, n-gram table in RAM vs NVMe |
| `20261104T194319Z-e4c128ce` | UD-Q4_K_XL on 4 cards, taken with 7 RAM sticks in NPS1, not comparable to the rest |

## Credits

- [unsloth](https://huggingface.co/unsloth) for the Dynamic v3.1 GGUFs.
- [incoai](https://huggingface.co/incoai) for the DFlash2 drafter.
- [Niko1221 and the Strata contributors](https://github.com/Niko1221/Strata) for the engine, and the author of PR #2590.
- [huihui-ai](https://huggingface.co/huihui-ai) for the refusal direction mixed into `mix-r1`.
- Qwen for Qwen3.8-Flash-Next.

## License

Scripts, configs and docs: MIT. The patch follows Strata (MIT). The vectors are computed from Qwen3.8-Flash-Next and
follow its license (`qwen-community-1.0`, see the model card).

<p align="center"><sub>Measured on my own rig by <a href="https://x.com/superalesha">@superalesha</a>. Numbers come from the runs in this repo, nothing typed by hand.</sub></p>
