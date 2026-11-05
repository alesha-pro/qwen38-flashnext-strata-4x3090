#!/usr/bin/env python3
"""Draw the README charts from the raw runs in bench/results (stdlib only).

    python3 assets/make_charts.py

Writes assets/speed-{light,dark}.svg (final build, 2 cards, decode by task and context) and
assets/cards-{light,dark}.svg (the same config on 1 / 2 / 3 / 4 cards, 16K context).
Values are the mean of repeats 1 and 2 (repeat 0 is the first request after load and is left out).
Colors: one blue ramp, ordinal, checked for light and dark surfaces.
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / 'bench' / 'results'
FINAL = RES / '20261105T003504Z-3b9c9622' / 'arms' / 'final-iq4xs-df2c05-cyr-mixr1' / 'result.json'
CARDS = {n: RES / '20261105T082238Z-e0c77fe0' / 'arms' / f'svc-g{n}' / 'result.json' for n in (1, 2, 3, 4)}

THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', grid='#e6e5e1',
                  ramp=['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']),
    'dark': dict(surface='#1a1a19', ink='#f0efec', ink2='#c3c2b7', grid='#33332f',
                 ramp=['#184f95', '#2a78d6', '#6da7ec', '#b7d3f6']),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
TASKS = [('code', 'Code'), ('edit', 'File edits'), ('essay', 'English prose'), ('ru', 'Russian')]


def mean_decode(rows, task, depth):
    xs = [r['decode_tok_s'] for r in rows if r['task'] == task and r['depth'] == depth and r['repeat'] > 0]
    return statistics.mean(xs) if xs else None


def bar(x, y0, w, h, r=4):
    """A bar anchored to the baseline y0 with 4px rounded data-end (top) corners."""
    r = min(r, w / 2, h)
    top = y0 - h
    return (f'M{x:.1f},{y0:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} '
            f'H{x + w - r:.1f} Q{x + w:.1f},{top:.1f} {x + w:.1f},{top + r:.1f} V{y0:.1f} Z')


def chart(theme, title, subtitle, groups, series, values, ymax, label_fn, footnote, desc):
    t = THEMES[theme]
    W, H = 920, 460
    left, right, top, bottom = 64, 24, 128, 70
    pw, ph = W - left - right, H - top - bottom
    y0 = top + ph
    n_s = len(series)
    bw, gap = 26, 2
    gw = n_s * bw + (n_s - 1) * gap
    slot = pw / len(groups)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-labelledby="t d" font-family="{FONT}">',
           f'<title id="t">{title}</title><desc id="d">{desc}</desc>',
           f'<rect width="{W}" height="{H}" rx="14" fill="{t["surface"]}"/>',
           f'<text x="{left - 40}" y="44" font-size="22" font-weight="650" fill="{t["ink"]}">{title}</text>',
           f'<text x="{left - 40}" y="70" font-size="14" fill="{t["ink2"]}">{subtitle}</text>']
    lx = left - 40
    for i, s in enumerate(series):                      # legend: swatch + text in ink, identity never by color alone
        out.append(f'<rect x="{lx}" y="88" width="14" height="14" rx="3" fill="{t["ramp"][i]}"/>')
        out.append(f'<text x="{lx + 20}" y="100" font-size="13" fill="{t["ink2"]}">{s}</text>')
        lx += 20 + 8 * len(s) + 26
    for v in range(0, ymax + 1, 50):                    # recessive grid
        y = y0 - ph * v / ymax
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(f'<text x="{left - 10}" y="{y + 4:.1f}" font-size="12" text-anchor="end" fill="{t["ink2"]}">{v}</text>')
    out.append(f'<text x="{left - 46}" y="{top + 12}" font-size="12" fill="{t["ink2"]}">tok/s</text>')
    for gi, (gkey, glabel) in enumerate(groups):
        gx = left + slot * gi + (slot - gw) / 2
        vals = values[gkey]
        for si, v in enumerate(vals):
            if v is None:
                continue
            h = ph * v / ymax
            x = gx + si * (bw + gap)
            out.append(f'<path d="{bar(x, y0, bw, h)}" fill="{t["ramp"][si]}"><title>{glabel}, {series[si]}: '
                       f'{v:.0f} tok/s</title></path>')
        peak = max(v for v in vals if v is not None)
        out.append(f'<text x="{gx + gw / 2:.1f}" y="{y0 - ph * peak / ymax - 10:.1f}" font-size="14" font-weight="600" '
                   f'text-anchor="middle" fill="{t["ink"]}">{label_fn(vals)}</text>')
        out.append(f'<text x="{gx + gw / 2:.1f}" y="{y0 + 24}" font-size="14" text-anchor="middle" fill="{t["ink"]}">{glabel}</text>')
    out.append(f'<line x1="{left}" x2="{W - right}" y1="{y0}" y2="{y0}" stroke="{t["ink2"]}" stroke-width="1"/>')
    out.append(f'<text x="{left - 40}" y="{H - 18}" font-size="12" fill="{t["ink2"]}">{footnote}</text>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def rng(vals):
    v = [round(x) for x in vals if x is not None]
    return f'{min(v)}-{max(v)}' if min(v) != max(v) else f'{v[0]}'


def main():
    final = json.loads(FINAL.read_text())['rows']
    depths = [2048, 16384, 65536, 131072]
    sp = {k: [mean_decode(final, k, d) for d in depths] for k, _ in TASKS}
    cards = {n: json.loads(p.read_text())['rows'] for n, p in CARDS.items()}
    tasks3 = [t for t in TASKS if t[0] != 'edit']
    cv = {k: [mean_decode(cards[n], k, 16384) for n in (1, 2, 3, 4)] for k, _ in tasks3}
    for theme in THEMES:
        (ROOT / 'assets' / f'speed-{theme}.svg').write_text(chart(
            theme, 'Decode speed on 2x RTX 3090',
            'Qwen3.8-Flash-Next UD-IQ4_XS, Strata 0.2.10, DFlash2 drafter, refusal vector on, 262K context window',
            TASKS, ['2K context', '16K', '64K', '128K'], sp, 175, rng,
            'Single request, greedy, 512 new tokens, no thinking, 300 W per card. Mean of repeats 1 and 2. Run 20261105T003504Z.',
            'Grouped bars: decode tokens per second for code, file edits, English prose and Russian at 2K, 16K, 64K and 128K '
            'context on two RTX 3090. Code 147 to 152, file edits 150 to 163, prose 123 to 131, Russian 112 to 116.'))
        (ROOT / 'assets' / f'cards-{theme}.svg').write_text(chart(
            theme, 'Same config on 1, 2, 3 and 4 cards',
            'Decode at 16K context. Layer split across cards; the expert cache grows with VRAM',
            tasks3, ['1 card', '2 cards', '3 cards', '4 cards'], cv, 175,
            lambda v: f'2nd card +{(v[1] / v[0] - 1) * 100:.0f}%',
            'Single request, greedy, 512 new tokens, no thinking, 300 W per card. Mean of repeats 1 and 2. Run 20261105T082238Z.',
            'Grouped bars: decode tokens per second at 16K context on 1, 2, 3 and 4 RTX 3090 for code, English prose and Russian.'))
    print(json.dumps({'speed': {k: [round(x, 1) for x in v] for k, v in sp.items()},
                      'cards': {k: [round(x, 1) for x in v] for k, v in cv.items()}}))


if __name__ == '__main__':
    main()
