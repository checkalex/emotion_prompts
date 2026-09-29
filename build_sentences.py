"""Build sentences.html (round 2) with a "best output" selector and live per-model / per-emotion scores.

Reads the WAVs from ~/Desktop/Prompts_test/emotion_sentences, encodes them to MP3 under audios/sentences/
(skipping files already encoded) and writes sentences.html. Run with: python3 build_sentences.py
"""
import html
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

R = os.path.dirname(os.path.abspath(__file__))
P = os.path.expanduser('~/Desktop/Prompts_test')
SENT = json.load(open(f'{P}/sentences.json'))
EMOS = list(SENT)
LIB = {v['id']: v['label'] for v in json.load(open(os.path.expanduser('~/Desktop/odub_tts_api/voice_library.json')))}
LANGS = [('en', 'English'), ('es', 'Spanish'), ('fr', 'French')]
COLS = [('CosyVoice3 end-to-end', 'cosyvoice_end-to-end'),
        ('Chatterbox (neutral)', 'chatterbox_output'),
        ('Chatterbox → Step-Audio-EditX', 'step-audio-editx_edition')]

jobs = []


def mp3(src, rel):
    """Queue src -> R/rel encoding; return rel."""
    assert os.path.isfile(src), src
    jobs.append((src, os.path.join(R, rel)))
    return rel


def audio(rel):
    return f'<audio controls preload="none" src="{rel}"></audio>'


def cell(lang, v, e, d):
    rel = mp3(f'{P}/emotion_sentences/{d}/{lang}/{v}_{e}.wav', f'audios/sentences/{d}/{lang}/{v}_{e}.mp3')
    key = f'{lang}|{v}|{e}|{d}'
    return (f'<td>{audio(rel)}<label class="pick"><input type="checkbox" data-key="{key}" '
            f'data-lang="{lang}" data-emo="{e}" data-model="{d}"> best</label></td>')


sections = []
for lang, lang_name in LANGS:
    voices = sorted(os.path.splitext(f)[0] for f in os.listdir(f'{P}/inputs/library/{lang}'))
    sent_rows = ''.join(f'<tr><td><b>{e}</b></td><td>{html.escape(SENT[e][lang])}</td></tr>' for e in EMOS)
    blocks = []
    for v in voices:
        ref = mp3(f'{P}/inputs/library/{lang}/{v}.wav', f'audios/sentences/reference/{lang}/{v}.mp3')
        rows = ''.join(f'<tr data-row="{lang}|{v}|{e}"><td><b>{e}</b></td>' + ''.join(cell(lang, v, e, d) for _, d in COLS) + '</tr>'
                       for e in EMOS)
        head = ''.join(f'<th>{n}</th>' for n, _ in COLS)
        blocks.append(f'''
        <details data-voice="{lang}|{v}">
          <summary><b>{html.escape(LIB.get(v, v))}</b> <span class="muted">({v})</span> <span class="done muted"></span></summary>
          <p>Reference voice: {audio(ref)}</p>
          <div class="scroll"><table class="grid"><tr><th>Emotion</th>{head}</tr>{rows}</table></div>
        </details>''')
    sections.append(f'''
      <h2 id="{lang}">{lang_name}</h2>
      <div class="scroll"><table class="sent"><tr><th>Emotion</th><th>Sentence</th></tr>{sent_rows}</table></div>
      {''.join(blocks)}
''')

nav = ' · '.join(f'<a href="#{l}">{n}</a>' for l, n in LANGS) + ' · <a href="#results">Results</a>'
CONFIG = json.dumps({'emotions': EMOS, 'models': [[d, n] for n, d in COLS], 'langs': LANGS}, ensure_ascii=False)

SCRIPT = r'''
<script>
(function () {
  const CFG = __CONFIG__;
  const STORE = 'emotion_prompts_round2_v1';
  const boxes = Array.from(document.querySelectorAll('input[data-key]'));
  const rows = Array.from(document.querySelectorAll('tr[data-row]'));
  const nameInput = document.getElementById('reviewer');

  function load() {
    try { return JSON.parse(localStorage.getItem(STORE) || '{}'); } catch (e) { return {}; }
  }
  function save() {
    const state = { reviewer: nameInput.value, picks: boxes.filter(b => b.checked).map(b => b.dataset.key) };
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
  }
  const saved = load();
  const picked = new Set(saved.picks || []);
  boxes.forEach(b => { b.checked = picked.has(b.dataset.key); });
  nameInput.value = saved.reviewer || '';

  function scores() {
    // count[lang][emotion][model] = number of lines where that model was picked
    const count = {}, rated = {};
    for (const [l] of CFG.langs.concat([['all']])) {
      count[l] = {}; rated[l] = {};
      for (const e of CFG.emotions) { count[l][e] = {}; rated[l][e] = 0; for (const [m] of CFG.models) count[l][e][m] = 0; }
    }
    for (const r of rows) {
      const [lang, , emo] = r.dataset.row.split('|');
      const on = Array.from(r.querySelectorAll('input:checked'));
      r.classList.toggle('rated', on.length > 0);
      if (!on.length) continue;
      rated[lang][emo]++; rated.all[emo]++;
      for (const b of on) { count[lang][emo][b.dataset.model]++; count.all[emo][b.dataset.model]++; }
    }
    return { count, rated };
  }

  function table(l, s) {
    let h = '<div class="scroll"><table class="grid"><tr><th>Emotion</th><th>Lines rated</th>' +
      CFG.models.map(([, n]) => `<th>${n}</th>`).join('') + '</tr>';
    const tot = {}; let totRated = 0;
    CFG.models.forEach(([m]) => tot[m] = 0);
    for (const e of CFG.emotions) {
      const n = s.rated[l][e]; totRated += n;
      const vals = CFG.models.map(([m]) => s.count[l][e][m]);
      const best = Math.max(...vals);
      h += `<tr><td><b>${e}</b></td><td>${n}</td>` + CFG.models.map(([m], i) => {
        tot[m] += vals[i];
        const pct = n ? Math.round(100 * vals[i] / n) + '%' : '–';
        return `<td class="${best > 0 && vals[i] === best ? 'win' : ''}">${vals[i]} <span class="muted">(${pct})</span></td>`;
      }).join('') + '</tr>';
    }
    const bestTot = Math.max(...Object.values(tot));
    h += `<tr class="total"><td><b>Total</b></td><td>${totRated}</td>` + CFG.models.map(([m]) => {
      const pct = totRated ? Math.round(100 * tot[m] / totRated) + '%' : '–';
      return `<td class="${bestTot > 0 && tot[m] === bestTot ? 'win' : ''}"><b>${tot[m]}</b> <span class="muted">(${pct})</span></td>`;
    }).join('') + '</tr></table></div>';
    return h;
  }

  function render() {
    const s = scores();
    let h = '<h4>All languages</h4>' + table('all', s);
    for (const [l, name] of CFG.langs) h += `<h4>${name}</h4>` + table(l, s);
    document.getElementById('score-tables').innerHTML = h;
    const done = rows.filter(r => r.classList.contains('rated')).length;
    document.getElementById('progress').textContent = `${done} / ${rows.length} lines rated`;
    document.querySelectorAll('details[data-voice]').forEach(d => {
      const rs = d.querySelectorAll('tr[data-row]');
      const n = Array.from(rs).filter(r => r.classList.contains('rated')).length;
      d.querySelector('.done').textContent = `— ${n}/${rs.length} rated`;
    });
    return s;
  }

  function exportData() {
    const s = render();
    return {
      page: 'emotion_prompts/sentences.html',
      reviewer: nameInput.value.trim(),
      exported_at: new Date().toISOString(),
      lines_rated: rows.filter(r => r.classList.contains('rated')).length,
      lines_total: rows.length,
      scores: s.count, lines_rated_per_emotion: s.rated,
      picks: boxes.filter(b => b.checked).map(b => b.dataset.key)
    };
  }

  document.addEventListener('change', e => { if (e.target.matches('input[data-key]')) { save(); render(); } });
  nameInput.addEventListener('input', save);
  document.getElementById('copy').addEventListener('click', async () => {
    const txt = JSON.stringify(exportData(), null, 1);
    const out = document.getElementById('export-out');
    out.value = txt; out.hidden = false; out.select();
    let ok = false;
    try { await navigator.clipboard.writeText(txt); ok = true; } catch (e) {}
    document.getElementById('copy-msg').textContent = ok ? 'Copied to clipboard.' : 'Select the text below and copy it.';
  });
  document.getElementById('download').addEventListener('click', () => {
    const d = exportData();
    const blob = new Blob([JSON.stringify(d, null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `emotion_ranking_${(d.reviewer || 'anonymous').replace(/\W+/g, '_')}.json`;
    document.body.appendChild(a); a.click(); a.remove();
  });
  document.getElementById('reset').addEventListener('click', () => {
    if (!confirm('Clear all your selections on this page?')) return;
    boxes.forEach(b => b.checked = false); save(); render();
  });
  // pause other players when one starts
  document.addEventListener('play', e => {
    document.querySelectorAll('audio').forEach(a => { if (a !== e.target) a.pause(); });
  }, true);
  render();
})();
</script>
'''.replace('__CONFIG__', CONFIG)

page = f'''<!DOCTYPE html>
<html lang="en-us">
  <head>
    <meta charset="UTF-8">
    <title>Emotional Sentences Benchmark</title>
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
      .main-content audio {{ width: 220px; display: block; }}
      .main-content p audio {{ display: inline-block; vertical-align: middle; }}
      .main-content dl dd {{ margin-left: 0; }}
      .main-content details {{ border: 1px solid #e9ebec; border-radius: 4px; padding: 0.5rem 1rem; margin-bottom: 0.75rem; }}
      .main-content summary {{ cursor: pointer; }}
      .muted {{ color: #819198; font-size: 0.9em; }}
      .pick {{ display: inline-flex; align-items: center; gap: 0.35rem; margin-top: 0.3rem; cursor: pointer; font-size: 0.9em; }}
      .pick input {{ width: 1.1rem; height: 1.1rem; cursor: pointer; }}
      td:has(.pick input:checked) {{ background: #e6f4ea; }}
      tr.rated td:first-child {{ color: #1e7e34; }}
      td.win {{ background: #e6f4ea; font-weight: bold; }}
      tr.total td {{ border-top: 2px solid #c9d1d5; }}
      #results {{ scroll-margin-top: 1rem; }}
      .results-box {{ border: 2px solid #159957; border-radius: 6px; padding: 1rem 1.5rem; margin-top: 2rem; }}
      .results-box button {{ font: inherit; padding: 0.4rem 0.9rem; margin: 0 0.5rem 0.5rem 0; cursor: pointer;
        border: 1px solid #159957; border-radius: 4px; background: #159957; color: #fff; }}
      .results-box button.secondary {{ background: #fff; color: #159957; }}
      .results-box input[type=text] {{ font: inherit; padding: 0.3rem 0.5rem; width: 16rem; max-width: 100%; }}
      #export-out {{ width: 100%; height: 12rem; font-family: monospace; font-size: 0.8rem; }}
    </style>
  </head>
  <body>
    <section id="page-header" class="page-header">
        <div id="bg-header"></div>
        <canvas id="demo-canvas"></canvas>
        <div class="main-title">
          <h1 class="project-name"><span><a href="index.html">Emotional Speech Benchmark</a></span></h1>
          <h2 class="project-tagline">Round 2: a sentence written for each emotion, 30 library voices in 3 languages</h2>
        </div>
    </section>

    <section class="main-content">
      <p><a href="index.html">← Round 1 (same sentence for every emotion)</a></p>
      <h2>What changed from round 1</h2>
      <p>Each emotion now has its own sentence whose content matches the emotion, and we test the two approaches
        we liked in round 1 on the 10 English, 10 Spanish and 10 French voices of the odub voice library.
        Open a voice to listen to its results.</p>
      <dl>
        <dt>CosyVoice3 end-to-end</dt>
        <dd>Fun-CosyVoice3-0.5B cloning the reference voice, with the emotion given as a text instruction (e.g. "Speak in a very angry, furious tone").</dd>
        <dt>Chatterbox (neutral)</dt>
        <dd>Chatterbox multilingual 0.1.7 with default settings, no emotion control. It is the input to the next column.</dd>
        <dt>Chatterbox → Step-Audio-EditX</dt>
        <dd>The Chatterbox clip edited by Step-Audio-EditX with an emotion label (two edit passes).
          <b>Shocked</b> uses <i>surprised</i> and <b>Exhausted</b> uses <i>depressed</i>, since EditX has no exact label for them.
          EditX is mainly trained on Chinese and English, so Spanish and French edits may be weaker.</dd>
      </dl>
      <h2>How to rate</h2>
      <p>For every line (voice × emotion), tick <b>best</b> under the output that conveys the emotion best while still
        sounding like the reference voice. If several outputs are equally good, tick all of them.
        Your choices are saved in this browser, so you can stop and come back later.
        When you're done, go to <a href="#results">Results</a> at the end of the page, enter your name and send us the export.</p>
      <p><b>Jump to:</b> {nav}</p>
{''.join(sections)}
      <div class="results-box" id="results">
        <h2>Results</h2>
        <p id="progress" class="muted"></p>
        <p>One point per ticked box. The percentage is out of the lines you rated for that emotion
          (it can add up to more than 100% because ties count for every model ticked). The best model of each row is highlighted.</p>
        <div id="score-tables"></div>
        <h3>Send your results</h3>
        <p><label>Your name: <input type="text" id="reviewer" placeholder="e.g. Alex"></label></p>
        <p>
          <button id="copy">Copy results</button>
          <button id="download" class="secondary">Download results (.json)</button>
          <button id="reset" class="secondary">Clear my selections</button>
          <span id="copy-msg" class="muted"></span>
        </p>
        <textarea id="export-out" readonly hidden></textarea>
      </div>
    </section>

    <script src="js/animheader.js"></script>
{SCRIPT}
  </body>
</html>
'''


def enc(job):
    src, dst = job
    if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-ac', '1', '-b:a', '128k', dst], check=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(enc, jobs))
open(f'{R}/sentences.html', 'w').write(page)
print(len(jobs), 'audio files referenced')
