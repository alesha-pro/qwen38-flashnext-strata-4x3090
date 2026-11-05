"""Session files on a layer split (Strata 0.2.10 + PR #2590): save, restart, restore, continue - and compare with the live run.

    python session_test.py --exe ENGINE --gpus 2,3 [--restore-gpus 0,2,3] --out RUN_DIR

Steps: server A loads; turn 1 (a ~16K document + a question, greedy) -> save slot 0 -> turn 2 live (greedy).  Server A stops.
Server B (same config, --restore-gpus or the same cards) loads; restore -> turn 2 again.  Prints the save/restore answers,
turn 2's prompt/cache counts on both servers, and whether the turn-2 answers are the same.  Benign text only.
"""
import argparse, json, os, random, signal, socket, subprocess, time, urllib.request, urllib.error
from pathlib import Path

CONTROL = '/mnt/nvme/engines/strata/0.2.10/control'
PY = CONTROL + '/python/bin/python3'
BASE = '/mnt/nvme/projects/qwen38-flashnext-unsloth-strata/configs/service-20261105.json'
CORPUS = Path('/mnt/nvme/projects/llm-services/bench/corpus.txt')
PORT = 18442


def call(path, body=None, timeout=900):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', json.dumps(body).encode() if body is not None else None,
                                 {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def start(exe, gpus, out, tag, slot_dir):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', PORT)) == 0:
            raise SystemExit(f'port {PORT} busy')
    cfg = json.loads(Path(BASE).read_text())
    cfg.update(exe=exe, host='127.0.0.1', port=PORT, log=str(out / f'{tag}.engine.log'), slot_save_path=str(slot_dir))
    cfg.pop('aliases', None)
    cp = out / f'{tag}.config.json'; cp.write_text(json.dumps(cfg, indent=1))
    log = open(out / f'{tag}.server.log', 'w')
    p = subprocess.Popen([PY, '-u', '-m', 'serve.server', '--engine', 'strata', '--config', str(cp), '--port', str(PORT),
                          '--gpu', gpus], cwd=CONTROL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 900:
        if p.poll() is not None:
            raise SystemExit(f'{tag}: server exited {p.returncode}')
        try:
            if call('/health', timeout=5)[1].get('loaded') is True:
                print(json.dumps({'server': tag, 'gpus': gpus, 'ready_s': round(time.time() - t0, 1)}), flush=True)
                return p
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit(f'{tag}: not ready')


def stop(p):
    for sig, wait in ((signal.SIGTERM, 40), (signal.SIGKILL, 20)):
        try:
            os.killpg(p.pid, sig); p.wait(timeout=wait); break
        except Exception:
            continue
    time.sleep(4)


def chat(messages, max_tokens=160):
    t0 = time.time()
    code, r = call('/v1/chat/completions', dict(model='x', messages=messages, max_tokens=max_tokens, temperature=0.0,
                                                chat_template_kwargs={'enable_thinking': False}))
    assert code == 200, r
    t = r.get('timings') or {}
    return r['choices'][0]['message']['content'], dict(prompt_n=t.get('prompt_n'), cache_n=t.get('cache_n'),
                                                       prefill_tok_s=t.get('prompt_per_second'),
                                                       decode_tok_s=t.get('predicted_per_second'), wall_s=round(time.time() - t0, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True); ap.add_argument('--gpus', default='2,3'); ap.add_argument('--restore-gpus')
    ap.add_argument('--out', required=True); ap.add_argument('--tokens', type=int, default=60000)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    slot_dir = Path(os.environ.get('RIG_SCRATCH_DIR') or out) / 'sessions'; slot_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    paras = [x for x in CORPUS.read_text().split('\n\n') if len(x) > 100]
    doc, n = [], 0
    while n < a.tokens * 4:          # ~4 characters per token
        s = rng.choice(paras); doc.append(s); n += len(s)
    u1 = 'Reference text follows.\n\n' + '\n\n'.join(doc) + '\n\nIn two sentences: what topics does the reference text cover?'
    u2 = 'Now list three concrete technical terms that appear in the reference text, one per line, nothing else.'
    res = {}
    A = start(a.exe, a.gpus, out, 'A', slot_dir)
    try:
        ans1, t1 = chat([{'role': 'user', 'content': u1}])
        res['turn1'] = t1
        name = f'split-test-{int(time.time())}.sess'
        t0 = time.time(); code, r = call(f'/slots/0?action=save', {'filename': name}, timeout=600)
        res['save'] = dict(code=code, seconds=round(time.time() - t0, 1), body=r)
        print(json.dumps({'save': res['save']}), flush=True)
        msgs2 = [{'role': 'user', 'content': u1}, {'role': 'assistant', 'content': ans1}, {'role': 'user', 'content': u2}]
        ans2_live, t2_live = chat(msgs2)
        res['turn2_live'] = t2_live
    finally:
        stop(A)
    B = start(a.exe, a.restore_gpus or a.gpus, out, 'B', slot_dir)
    try:
        t0 = time.time(); code, r = call(f'/slots/0?action=restore', {'filename': name}, timeout=600)
        res['restore'] = dict(code=code, seconds=round(time.time() - t0, 1), body=r)
        print(json.dumps({'restore': res['restore']}), flush=True)
        ans2_rest, t2_rest = chat(msgs2)
        res['turn2_after_restore'] = t2_rest
        res['turn2_same_answer'] = ans2_rest == ans2_live
        res['answers'] = dict(turn1=ans1, turn2_live=ans2_live, turn2_after_restore=ans2_rest)
        res['session_file_bytes'] = (slot_dir / name).stat().st_size if (slot_dir / name).exists() else None
    finally:
        stop(B)
    (out / f'session-test-{a.gpus.replace(",", "")}-to-{(a.restore_gpus or a.gpus).replace(",", "")}.json').write_text(
        json.dumps(res, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'answers'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
