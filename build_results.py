"""Build results.html from every reviewer export in results/*.json (the JSON produced by sentences.html).

Scores are recomputed from the raw picks: each reviewer x voice x emotion line with at least one tick counts as
one rated line, and every ticked model on that line gets one point (ties give a point to each).
Run with: python3 build_results.py
"""
import glob
import html
import json
import os
from collections import defaultdict

R = os.path.dirname(os.path.abspath(__file__))
EMOS = ['Angry', 'Happy', 'Sad', 'Embarrassed', 'Shocked', 'Excited', 'Exhausted']
LANGS = [('en', 'English'), ('es', 'Spanish'), ('fr', 'French')]
MODELS = [('cosyvoice_end-to-end', 'CosyVoice3 end-to-end'),
          ('chatterbox_output', 'Chatterbox (neutral)'),
          ('step-audio-editx_edition', 'Chatterbox → Step-Audio-EditX'),
          ('cosyvoice_native-instruct', 'CosyVoice3, native instruction (es/fr only)'),
          ('chatterbox_finetuned', 'Chatterbox finetuned (neutral) (es/fr only)'),
          ]
# Columns shown per language, matching the listening page (EditX removed for es/fr; es/fr-only columns not shown for en).
ES_FR_ONLY = {'cosyvoice_native-instruct', 'chatterbox_finetuned'}
HIDDEN = {'en': ES_FR_ONLY, 'es': {'step-audio-editx_edition'}, 'fr': {'step-audio-editx_edition'}, 'all': set()}

exports = []
for path in sorted(glob.glob(f'{R}/results/*.json')):
    d = json.load(open(path))
    d['_name'] = d.get('reviewer') or os.path.splitext(os.path.basename(path))[0]
    exports.append(d)

count = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # count[lang][emo][model]
rated = defaultdict(lambda: defaultdict(int))                       # rated[lang][emo]
for d in exports:
    lines = defaultdict(set)
    for key in d['picks']:
        lang, voice, emo, model = key.split('|')
        lines[(lang, voice, emo)].add(model)
    for (lang, voice, emo), models in lines.items():
        for l in (lang, 'all'):
            rated[l][emo] += 1
            for m in models:
                count[l][emo][m] += 1


def table(l):
    models = [x for x in MODELS if x[0] not in HIDDEN[l]]
    head = ''.join(f'<th>{n}</th>' for _, n in models)
    rows, tot, tot_rated = [], defaultdict(int), 0
    for e in EMOS:
        n = rated[l][e]
        tot_rated += n
        vals = [count[l][e][m] for m, _ in models]
        best = max(vals)
        cells = []
        for (m, _), v in zip(models, vals):
            tot[m] += v
            pct = f'{round(100 * v / n)}%' if n else '–'
            cells.append(f'<td class="{"win" if best and v == best else ""}">{v} <span class="muted">({pct})</span></td>')
        rows.append(f'<tr><td><b>{e}</b></td><td>{n}</td>{"".join(cells)}</tr>')
    best = max(tot[m] for m, _ in models)
    cells = ''.join(
        f'<td class="{"win" if best and tot[m] == best else ""}"><b>{tot[m]}</b> '
        f'<span class="muted">({round(100 * tot[m] / tot_rated) if tot_rated else "–"}{"%" if tot_rated else ""})</span></td>'
        for m, _ in models)
    rows.append(f'<tr class="total"><td><b>Total</b></td><td>{tot_rated}</td>{cells}</tr>')
    return f'<div class="scroll"><table class="grid"><tr><th>Emotion</th><th>Lines rated</th>{head}</tr>{"".join(rows)}</table></div>'


reviewers = ''.join(
    f'<li><b>{html.escape(d["_name"])}</b>: {len({p.rsplit("|", 1)[0] for p in d["picks"]})} lines rated'
    f' <span class="muted">(exported {d.get("exported_at", "")[:10]})</span>'
    + (f'<blockquote><p>{html.escape(d["comments"])}</p></blockquote>' if d.get('comments') else '') + '</li>'
    for d in exports)
tables = '<h3>All languages</h3>' + table('all') + ''.join(
    f'<h3>{name}</h3>' + (table(l) if sum(rated[l].values()) else '<p class="muted">Not rated yet.</p>')
    for l, name in LANGS)

page = f'''<!DOCTYPE html>
<html lang="en-us">
  <head>
    <meta charset="UTF-8">
    <title>Emotion Benchmark Results</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="stylesheets/normalize.css" media="screen">
    <link href='https://fonts.googleapis.com/css?family=Open+Sans:400,700' rel='stylesheet' type='text/css'>
    <link rel="stylesheet" type="text/css" href="stylesheets/stylesheet.css" media="screen">
    <link rel="stylesheet" type="text/css" href="stylesheets/github-light.css" media="screen">
    <style>
      @media screen and (min-width: 64em) {{ .main-content {{ max-width: 90rem; }} }}
      .main-content .scroll {{ overflow-x: auto; margin-bottom: 1.5rem; }}
      .main-content .scroll table {{ display: table; width: auto; }}
      .main-content table th {{ text-align: left; vertical-align: bottom; }}
      .muted {{ color: #819198; font-size: 0.9em; }}
      td.win {{ background: #e6f4ea; font-weight: bold; }}
      tr.total td {{ border-top: 2px solid #c9d1d5; }}
    </style>
  </head>
  <body>
    <section id="page-header" class="page-header">
        <div id="bg-header"></div>
        <canvas id="demo-canvas"></canvas>
        <div class="main-title">
          <h1 class="project-name"><span><a href="index.html">Emotional Speech Benchmark</a></span></h1>
          <h2 class="project-tagline">Round 2 results</h2>
        </div>
    </section>

    <section class="main-content">
      <p><a href="sentences.html">← Round 2 listening page</a> · <a href="index.html">Round 1</a></p>
      <h2>Summary</h2>
      <ul>
        <li><b>English:</b> CosyVoice3 end-to-end wins clearly: best on 14 of 17 rated lines (82%), and best or tied on every emotion rated.
          Step-Audio-EditX is competitive only on <i>Shocked</i>.</li>
        <li><b>French:</b> only Chatterbox (neutral) was picked. CosyVoice3 adds an English accent, and Step-Audio-EditX
          struggles with the French speech (worse than CosyVoice3). Chatterbox has no emotion control, so French still needs a
          working emotion option.</li>
        <li><b>Spanish:</b> not rated yet.</li>
        <li><b>New:</b> a <i>CosyVoice3, native instruction</i> column was added for Spanish and French on the listening page
          (emotion instruction written in the voice's language) to test whether it removes the English accent. Not rated yet.
          Automatic check (Whisper language detection, a rough proxy for accent): with the English instruction, 10 of 70 French
          CosyVoice3 clips were detected as less than 90% French (lowest 48%); with the French instruction, none were
          (average 99.3%, same level as Chatterbox). Spanish was already fine with either instruction.</li>
        <li><b>New:</b> Spanish and French also have a column with odub's production finetuned Chatterbox models. Not rated yet.</li>
        <li><b>Removed:</b> Step-Audio-EditX outputs for Spanish and French. EditX doesn't support those languages yet (its audio
          tokenizer is Chinese/English only), so they sounded English-accented and distorted. It stays in the English comparison.</li>
        <li>Sample size is small ({sum(rated["all"].values())} lines out of 210), so treat these numbers as a first signal.</li>
      </ul>
      <h2>Scores</h2>
      <p>One point per ticked box. The percentage is out of the lines rated for that emotion (it can add up to more than 100%
        because ties count for every model ticked). The best model of each row is highlighted.</p>
      {tables}
      <h2>Reviewers</h2>
      <ul>{reviewers}</ul>
    </section>

    <script src="js/animheader.js"></script>
  </body>
</html>
'''
open(f'{R}/results.html', 'w').write(page)
print(f'{len(exports)} export(s), {sum(rated["all"].values())} lines rated')
