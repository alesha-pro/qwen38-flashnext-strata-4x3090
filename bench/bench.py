"""Speed of Strata configs on Qwen3.8-Flash-Next (unsloth UD-Q4_K_XL): serve.server + a run config per arm.

    python bench.py --plan plan.json [--only A,B]      # RIG_RUN_DIR from rig-task; results in RIG_RUN_DIR/arms/<arm>/

plan.json: {"base_config": "<run config json>", "control": "<strata control dir>", "python": "<python>",
            "tokenizer": "<tokenizer dir>", "port": 18442, "gpus": "0,1,2,3",
            "arms": [{"name": "...", "set_args": {"--flag": "value"}, "drop_args": ["--mtp"], "extra_args": [...],
                      "env": {...}, "cfg": {...}}],
            "depths": [2048, 16384, 65536], "repeat": 2, "max_new": 512, "tasks": ["essay", "code"]}

Per arm one fresh server (the engine loads once). Chat requests, thinking off, greedy, a unique header per
request so no prefix is reused. Speeds are the engine's own clock (`timings`). Derived from llm-services/bench/
strata_version_ab.py (20.10.2026).
"""
import argparse, json, os, random, signal, subprocess, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path('/mnt/nvme/projects/llm-services/bench/corpus.txt')
TASKS = {
    'essay': ('Write a detailed technical essay of at least 2000 words explaining database indexes, B-trees, hash '
              'tables, transactions and replication with worked examples. Begin immediately.'),
    'code': ('Write a complete, well-commented Python module implementing an LRU cache with TTL expiry, a thread-safe '
             'wrapper, a decorator for memoizing functions, and a full pytest test suite for all of it. Output only code.'),
    'ru': ('Напиши подробное техническое эссе на русском языке (не меньше 1500 слов) о том, как устроены индексы баз данных, '
           'B-деревья, хеш-таблицы, транзакции и репликация, с разобранными примерами. Начинай сразу.'),
}


EDIT_SRC = Path('/mnt/nvme/engines/strata/0.2.10/control/serve/server.py')
EDIT_TASK = ('Above is the start of a Python file. Rewrite the LAST 60 lines of it exactly as they are, but rename every '
             'local variable called `args` to `argv` and add a one-line comment above each `def`. Output only the code.')


def prompt_text(tok, depth, seed, task):
    rng = random.Random(seed)
    if task == 'edit':                      # agent-style edit: the context is real code, the answer mostly copies it
        lines = EDIT_SRC.read_text().split('\n'); start = rng.randrange(0, 2000); out, n = [], 0
        for ln in lines[start:]:
            k = len(tok.encode(ln + '\n'))
            if n + k > depth - 120:
                break
            out.append(ln); n += k
        return f'# file {seed}-{rng.randrange(10**8)}\n' + '\n'.join(out) + '\n\n' + EDIT_TASK
    paras = [x for x in CORPUS.read_text().split('\n\n') if len(x) > 100]
    head = f'Independent document {seed}-{rng.randrange(10**8)}. Read the reference text.\n'
    chunks, n = [], 0
    target = depth - 90
    while n < target:
        s = rng.choice(paras) + '\n\n'; k = len(tok.encode(s))
        if n + k > target:
            s = s[:max(0, int(len(s) * (target - n) / k))]; k = target - n
        chunks.append(s); n += k
    return head + ''.join(chunks) + '\n' + TASKS[task]


def post(port, body, timeout=3600):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def gpu_state(gpus):
    r = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used,power.limit', '--format=csv,noheader,nounits'],
                       capture_output=True, text=True).stdout
    out = {}
    for line in r.strip().splitlines():
        i, m, p = [x.strip() for x in line.split(',')]
        if i in gpus.split(','):
            out[i] = (int(m), float(p))
    return out


def build_cfg(plan, arm, d):
    cfg = json.loads(Path(arm.get('base_config', plan['base_config'])).read_text())
    for flag in arm.get('drop_args', []):
        if flag in cfg['args']:
            i = cfg['args'].index(flag)
            n = 1 if i + 1 >= len(cfg['args']) or cfg['args'][i + 1].startswith('--') else 2
            if flag in ('--control-vector-layer-range',):
                n = 3
            del cfg['args'][i:i + n]
    for flag, value in arm.get('set_args', {}).items():
        if flag in cfg['args']:
            i = cfg['args'].index(flag); del cfg['args'][i:i + 2]
        cfg['args'] += [flag, value]
    cfg['args'] += arm.get('extra_args', [])
    cfg.update(arm.get('cfg', {}))
    cfg['log'] = str(d / 'engine.log'); cfg['host'] = '127.0.0.1'
    return cfg


def port_busy(port):
    import socket
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def run_arm(plan, arm, run_dir, tok):
    if port_busy(plan['port']):           # an older server still answers there: every request would go to it
        raise RuntimeError(f"port {plan['port']} is busy before the arm starts")
    d = run_dir / 'arms' / arm['name']; d.mkdir(parents=True, exist_ok=True)
    cfg = build_cfg(plan, arm, d)
    (d / 'config.json').write_text(json.dumps(cfg, indent=1) + '\n')
    gpus = arm.get('gpus', plan['gpus'])
    env = dict(os.environ, PYTHONUNBUFFERED='1', **plan.get('env', {}), **arm.get('env', {}))
    argv = [plan['python'], '-u', '-m', 'serve.server', '--engine', 'strata', '--config', str(d / 'config.json'),
            '--port', str(plan['port']), '--gpu', gpus]
    meta = dict(arm=arm, argv=argv, cwd=plan['control'], engine_argv=[cfg['exe'], *cfg['args']],
                env={k: v for k, v in env.items() if k.startswith('STRATA_')},
                power_limit_w={k: v[1] for k, v in gpu_state(gpus).items()},
                started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (d / 'launch.json').write_text(json.dumps(meta, indent=1) + '\n')
    log = open(d / 'server.log', 'w')
    p = subprocess.Popen(argv, cwd=plan['control'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    peak = {'stop': False, 'vram': {}}

    def sampler():
        while not peak['stop']:
            for k, (m, _) in gpu_state(gpus).items():
                peak['vram'][k] = max(peak['vram'].get(k, 0), m)
            time.sleep(2)
    try:
        t0 = time.time(); ready = None
        while time.time() - t0 < plan.get('ready_timeout', 1800):
            if p.poll() is not None:
                raise RuntimeError(f"{arm['name']}: server exited {p.returncode}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{plan['port']}/health", timeout=5) as r:
                    if r.status == 200 and json.loads(r.read() or b'{}').get('loaded') is True:
                        ready = time.time() - t0; break
            except Exception:
                pass
            time.sleep(2)
        if ready is None:
            raise RuntimeError(f"{arm['name']}: not ready")
        print(json.dumps(dict(arm=arm['name'], stage='ready', seconds=round(ready, 1))), flush=True)
        threading.Thread(target=sampler, daemon=True).start()
        # warm-up: one short request, not recorded (first graph captures, lazy allocations)
        post(plan['port'], dict(model='bench', messages=[dict(role='user', content='Say hi.')], max_tokens=16,
                                temperature=0.0, chat_template_kwargs=dict(enable_thinking=False)))
        rows = []
        for task in arm.get('tasks', plan.get('tasks', ['essay'])):
            for dep in arm.get('depths', plan['depths']):
                for rep in range(plan['repeat']):
                    seed = dep * 10 + rep + (100 if task == 'code' else 0)
                    body = dict(model='bench', messages=[dict(role='user', content=prompt_text(tok, dep, seed, task))],
                                max_tokens=plan['max_new'], stream=False, temperature=0.0,
                                chat_template_kwargs=dict(enable_thinking=False))
                    t1 = time.time(); r = post(plan['port'], body); wall = time.time() - t1
                    t = r.get('timings') or {}
                    row = dict(arm=arm['name'], task=task, depth=dep, repeat=rep,
                               prompt_n=t.get('prompt_n'), cache_n=t.get('cache_n'), prefill_tok_s=t.get('prompt_per_second'),
                               decode_tok_s=t.get('predicted_per_second'), predicted_n=t.get('predicted_n'),
                               draft_n=t.get('draft_n'), draft_acc=t.get('draft_n_accepted'), timings=t, wall_s=round(wall, 2),
                               finish=r['choices'][0].get('finish_reason'), usage=r.get('usage'),
                               head=(r['choices'][0]['message'].get('content') or '')[:160])
                    rows.append(row)
                    print(json.dumps({k: v for k, v in row.items() if k not in ('timings', 'head')}), flush=True)
        res = dict(meta, ready_s=round(ready, 1), vram_peak_mib=peak['vram'], rows=rows)
        (d / 'result.json').write_text(json.dumps(res, indent=1) + '\n')
        return res
    finally:
        peak['stop'] = True
        for sig, wait in ((signal.SIGINT, 30), (signal.SIGTERM, 20), (signal.SIGKILL, 30)):
            try:
                os.killpg(p.pid, sig); p.wait(timeout=wait); break
            except Exception:
                continue
        time.sleep(5)


def load_tok(plan):
    sys.path.insert(0, plan['control'] + '/tools')
    import strata_tokenizer as ST
    tp = Path(plan['tokenizer'])
    vocab = json.loads((tp / 'vocab.json').read_text()); toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    return ST.Tokenizer(toks, (tp / 'merges.txt').read_text().split('\n'), json.loads((tp / 'token_type.json').read_text()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--plan', required=True); ap.add_argument('--only', default='')
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    run_dir = Path(os.environ.get('RIG_RUN_DIR') or plan['run_dir'])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'plan.json').write_text(json.dumps(plan, indent=1) + '\n')
    tok = load_tok(plan)
    for arm in plan['arms']:
        if a.only and arm['name'] not in a.only.split(','):
            continue
        if (run_dir / 'arms' / arm['name'] / 'result.json').exists():
            continue
        try:
            run_arm(plan, arm, run_dir, tok)
        except KeyboardInterrupt:
            print(json.dumps(dict(stage='interrupted')), flush=True); raise
        except Exception as e:
            print(json.dumps(dict(arm=arm['name'], error=str(e))), flush=True)
            if 'port' in str(e):
                break
    print(json.dumps(dict(stage='all-done')), flush=True)


if __name__ == '__main__':
    main()
