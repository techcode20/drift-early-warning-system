const SEVC = {none:'#22c55e', mild:'#eab308', moderate:'#f97316', severe:'#e2001a', 'no-decision':'#6b7280'};
const msg = (t) => { document.getElementById('msg').textContent = t || ''; };

async function feed(scenario) {
  const btns = document.querySelectorAll('[data-feed]');
  btns.forEach(b => b.disabled = true);
  msg(`Feeding ${scenario} batch…`);
  try {
    const r = await fetch(`/simulate/${scenario}`, {method: 'POST'});
    const j = await r.json();
    if (j.error) msg('Error: ' + j.error);
    else msg(`Batch ${j.batch_id}: PSI ${j.psi_global} (${j.severity}), action: ${j.action}`);
  } catch (e) { msg('Request failed: ' + e); }
  btns.forEach(b => b.disabled = false);
  await draw();
}

async function resetDemo() {
  msg('Resetting…');
  await fetch('/reset', {method: 'POST'});
  msg('Fresh demo. Feed Normal a few times first.');
  await draw();
}

function drawLine(data) {
  const svg = d3.select('#chart'); svg.selectAll('*').remove();
  const m = {t:14, r:14, b:32, l:46}, W = 900 - m.l - m.r, H = 320 - m.t - m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
  const x = d3.scaleLinear().domain([0, Math.max(data.length - 1, 1)]).range([0, W]);
  const yMax = Math.max(0.6, ...data.map(d => d.psi || 0));
  const y = d3.scaleLinear().domain([0, yMax]).range([H, 0]);
  g.append('g').attr('transform', `translate(0,${H})`)
    .call(d3.axisBottom(x).ticks(Math.min(data.length, 10)).tickFormat(i => '#' + (data[i] ? data[i].batch_id : '')));
  g.append('g').call(d3.axisLeft(y).ticks(6));
  // threshold lines + labels
  [[0.1, 'mild 0.1', '#eab308'], [0.25, 'severe 0.25', '#e2001a']].forEach(([t, label, c]) => {
    if (t > yMax) return;
    g.append('line').attr('x1', 0).attr('x2', W).attr('y1', y(t)).attr('y2', y(t))
      .attr('stroke', c).attr('stroke-dasharray', '5 4').attr('opacity', .8);
    g.append('text').attr('x', W - 4).attr('y', y(t) - 4).attr('text-anchor', 'end')
      .attr('fill', c).attr('font-size', 11).text(label);
  });
  // segments colored by severity of the *next* point
  for (let i = 0; i + 1 < data.length; i++) {
    g.append('line')
      .attr('x1', x(i)).attr('y1', y(data[i].psi || 0))
      .attr('x2', x(i + 1)).attr('y2', y(data[i + 1].psi || 0))
      .attr('stroke', SEVC[data[i + 1].severity] || '#1c69d4').attr('stroke-width', 2.5);
  }
  // dots with tooltip
  g.selectAll('circle').data(data).join('circle')
    .attr('cx', (d, i) => x(i)).attr('cy', d => y(d.psi || 0)).attr('r', 4)
    .attr('class', d => 'dot-' + d.severity)
    .append('title').text(d => `#${d.batch_id} ${d.scenario} · PSI ${d.psi} · ${d.severity} · top: ${d.top || '–'}`);
}

function drawBars(features, batchId) {
  const box = document.getElementById('bars'); box.innerHTML = '';
  const rows = features.filter(f => f.batch_id === batchId)
    .sort((a, b) => b.psi - a.psi);
  if (!rows.length) { box.innerHTML = '<p style="color:var(--muted)">No per-feature data yet.</p>'; return; }
  const mx = Math.max(...rows.map(r => r.psi), 0.01);
  rows.forEach(r => {
    const div = document.createElement('div'); div.className = 'brow';
    const col = r.psi >= 0.25 ? 'var(--sev)' : r.psi >= 0.1 ? 'var(--mild)' : 'var(--ok)';
    div.innerHTML = `<span>${r.feature}</span>
      <div class="btrack"><div class="bfill" style="width:${(r.psi / mx * 100).toFixed(1)}%;background:${col}"></div></div>
      <span>${r.psi.toFixed(3)}</span>`;
    box.appendChild(div);
  });
}

async function draw() {
  let payload;
  try {
    payload = await fetch('/scores?limit=50').then(x => x.json());
  } catch (e) { msg('Cannot reach backend. Is uvicorn running?'); return; }
  const data = payload.scores || [];
  document.getElementById('baseInfo').textContent = `baseline: ${(payload.baseline_rows || 0).toLocaleString()} rows`;
  document.getElementById('empty').classList.toggle('hidden', data.length > 0);
  const last = data[data.length - 1];
  document.getElementById('cPsi').textContent = last ? last.psi.toFixed(3) : '–';
  document.getElementById('cSev').textContent = last ? last.severity + (last.confirmed ? ' ✓' : '') : '–';
  document.getElementById('cSev').className = 'v ' + (last ? 'sev-' + last.severity : '');
  document.getElementById('cTop').textContent = last && last.top ? last.top : '–';
  document.getElementById('cN').textContent = data.length;
  const bad = last && (last.severity === 'severe' || last.severity === 'moderate');
  document.getElementById('banner').classList.toggle('hidden', !bad);
  if (bad) document.getElementById('feat').textContent = 'Feature: ' + last.top + ` (batch #${last.batch_id})`;
  if (data.length) {
    drawLine(data);
    drawBars(payload.features || [], last.batch_id);
    document.querySelector('#hist tbody').innerHTML = [...data].reverse().map(d =>
      `<tr><td>${d.batch_id}</td><td>${d.scenario}</td><td>${Number(d.psi).toFixed(3)}</td>` +
      `<td class="sev-${d.severity}">${d.severity}</td><td>${d.confirmed ? '✓ confirmed' : '–'}</td><td>${d.top || '–'}</td></tr>`).join('');
  } else {
    d3.select('#chart').selectAll('*').remove();
    document.getElementById('bars').innerHTML = '';
    document.querySelector('#hist tbody').innerHTML = '';
  }
}

document.querySelectorAll('[data-feed]').forEach(b =>
  b.addEventListener('click', () => feed(b.dataset.feed)));
document.getElementById('resetBtn').addEventListener('click', resetDemo);
document.getElementById('demoBtn').addEventListener('click', async () => {
  const plan = ['normal','normal','normal','normal','gradual','gradual','gradual','gradual','spike','spike'];
  msg('Auto-demo running: 10 batches…');
  for (const s of plan) {
    await fetch(`/simulate/${s}`, {method: 'POST'});
    await draw();
    await new Promise(r => setTimeout(r, 500));
  }
  msg('Auto-demo done: flat → climb → spike. Check the red banner.');
});
document.getElementById('exportBtn').addEventListener('click', async () => {
  const r = await fetch('/scores?limit=500').then(x => x.json());
  const rows = [['batch_id','ts','scenario','psi','severity','confirmed','top_feature']]
    .concat(r.scores.map(d => [d.batch_id, d.ts, d.scenario, d.psi, d.severity, d.confirmed, d.top || '']));
  const blob = new Blob([rows.map(x => x.join(',')).join('\n')], {type: 'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'drift_history.csv'; a.click();
  URL.revokeObjectURL(a.href);
});
draw(); setInterval(draw, 3000);
