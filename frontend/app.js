async function feed(scenario) {
  // generate 800 rows client-side? No — ask backend to simulate via ingest of synthetic batch.
  // Simplest demo: call a helper endpoint pattern — here we POST random batch built in python via /ingest.
  // For starter: frontend just triggers refresh; real feeding done by Role 1 script.
  // TODO(Role1+3): add POST /simulate/{scenario} to auto-generate + ingest.
  await draw();
}
async function draw() {
  const r = await fetch('/scores?limit=50').then(x => x.json());
  const data = r.scores;
  const svg = d3.select('#chart'); svg.selectAll('*').remove();
  const m = {t:10,r:10,b:30,l:40}, W = 900-m.l-m.r, H = 300-m.t-m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
  const x = d3.scaleLinear().domain([0, Math.max(data.length,1)]).range([0,W]);
  const y = d3.scaleLinear().domain([0, Math.max(0.6, ...data.map(d=>d.psi))]).range([H,0]);
  g.append('g').attr('transform',`translate(0,${H})`).call(d3.axisBottom(x));
  g.append('g').call(d3.axisLeft(y));
  const line = d3.line().x((d,i)=>x(i)).y(d=>y(d.psi));
  g.append('path').datum(data).attr('fill','none').attr('stroke','#1c69d4').attr('stroke-width',2).attr('d',line);
  // thresholds
  [0.1,0.25].forEach(t=>g.append('line').attr('x1',0).attr('x2',W).attr('y1',y(t)).attr('y2',y(t)).attr('stroke',t>0.2?'red':'orange').attr('stroke-dasharray','4 4'));
  const last = data[data.length-1];
  if (last && (last.severity==='severe'||last.severity==='moderate')) {
    document.getElementById('banner').classList.remove('hidden');
    document.getElementById('feat').textContent = 'Feature: ' + last.top;
  } else document.getElementById('banner').classList.add('hidden');
}
draw(); setInterval(draw, 2000);
