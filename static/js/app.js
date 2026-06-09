// ── DOM ──────────────────────────────────────────────────────────────────
const cvInput   = document.getElementById('cv-input');
const jdInput   = document.getElementById('jd-input');
const cvDrop    = document.getElementById('cv-drop');
const jdDrop    = document.getElementById('jd-drop');
const cvName    = document.getElementById('cv-name');
const jdName    = document.getElementById('jd-name');
const jdText    = document.getElementById('jd-text');
const analyzeBtn= document.getElementById('analyze-btn');
const errorBox  = document.getElementById('error-box');
const loader    = document.getElementById('loader');
const loaderMsg = document.getElementById('loader-msg');
const inputSec  = document.getElementById('input-section');
const resultsSec= document.getElementById('results');
const resetBtn  = document.getElementById('reset-btn');

const CAT_COLORS = {
  "Foundation":     "#60a5fa",
  "Clinical Skills":"#4ade80",
  "Surgery":        "#f472b6",
  "Research":       "#fb923c",
  "Digital Health": "#a78bfa",
  "Management":     "#facc15",
};

// ── File handling ─────────────────────────────────────────────────────────
function attachFile(input, nameEl, dropEl, isJD) {
  input.addEventListener('change', () => {
    if (input.files[0]) { nameEl.textContent = input.files[0].name; checkReady(); }
  });
  dropEl.addEventListener('dragover', e => { e.preventDefault(); dropEl.classList.add('over'); });
  dropEl.addEventListener('dragleave', () => dropEl.classList.remove('over'));
  dropEl.addEventListener('drop', e => {
    e.preventDefault(); dropEl.classList.remove('over');
    const f = e.dataTransfer.files[0]; if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['pdf','doc','docx'].includes(ext)) { showError('Only PDF or DOCX files are supported.'); return; }
    const dt = new DataTransfer(); dt.items.add(f); input.files = dt.files;
    nameEl.textContent = f.name; checkReady();
  });
}

attachFile(cvInput, cvName, cvDrop, false);
attachFile(jdInput, jdName, jdDrop, true);
jdText.addEventListener('input', checkReady);

function checkReady() {
  analyzeBtn.disabled = !cvInput.files[0];
}

// ── Submit ────────────────────────────────────────────────────────────────
const MSGS = [
  'Extracting clinical competencies…',
  'Mapping to ESCO / O*NET taxonomy…',
  'Building knowledge graph…',
  'Computing learning pathways…',
  'Generating development plan…'
];

analyzeBtn.addEventListener('click', async () => {
  if (!cvInput.files[0]) return;
  hideError();
  const fd = new FormData();
  fd.append('cv', cvInput.files[0]);
  if (jdInput.files[0]) fd.append('jd', jdInput.files[0]);
  if (jdText.value.trim()) fd.append('jd_text', jdText.value.trim());

  inputSec.classList.add('hidden');
  loader.classList.remove('hidden');

  let mi = 0;
  const iv = setInterval(() => { mi = (mi+1)%MSGS.length; loaderMsg.textContent = MSGS[mi]; }, 2500);

  try {
    const res  = await fetch('/analyze', { method:'POST', body:fd });
    const data = await res.json();
    clearInterval(iv);
    if (!res.ok || data.error) { showError(data.error||'Server error'); loader.classList.add('hidden'); inputSec.classList.remove('hidden'); return; }
    render(data);
  } catch(e) {
    clearInterval(iv);
    showError('Network error. Please try again.');
    loader.classList.add('hidden'); inputSec.classList.remove('hidden');
  }
});

// ── Reset ─────────────────────────────────────────────────────────────────
resetBtn.addEventListener('click', () => {
  resultsSec.classList.add('hidden');
  inputSec.classList.remove('hidden');
  cvInput.value=''; jdInput.value=''; jdText.value='';
  cvName.textContent=''; jdName.textContent='';
  analyzeBtn.disabled=true; hideError();
});

// ── Render results ────────────────────────────────────────────────────────
function render(d) {
  loader.classList.add('hidden');

  // Match banner
  if (d.has_jd && d.match_pct !== null) {
    document.getElementById('match-banner').classList.remove('hidden');
    document.getElementById('match-pct-val').textContent = d.match_pct + '%';
    setTimeout(() => { document.getElementById('match-bar').style.width = d.match_pct + '%'; }, 50);
    const chips = document.getElementById('match-chips');
    chips.innerHTML = '';
    (d.matched||[]).slice(0,4).forEach(s => chips.insertAdjacentHTML('beforeend',`<span class="chip chip-match">&#10003; ${s.name}</span>`));
    (d.missing||[]).slice(0,4).forEach(s => chips.insertAdjacentHTML('beforeend',`<span class="chip chip-miss">&#x25CB; ${s.name}</span>`));
    (d.bonus||[]).slice(0,2).forEach(s  => chips.insertAdjacentHTML('beforeend',`<span class="chip chip-bonus">+ ${s.name}</span>`));
  }

  // Summaries
  document.getElementById('res-cv-summary').textContent = d.cv_summary || '—';
  if (d.has_jd && d.jd_summary) {
    document.getElementById('jd-summary-card').style.display='';
    document.getElementById('res-jd-summary').textContent = d.jd_summary;
  }

  // CV skills
  const cvList = document.getElementById('res-cv-skills');
  document.getElementById('cv-count').textContent = d.cv_skills.length;
  cvList.innerHTML = '';
  d.cv_skills.forEach(s => {
    const col = CAT_COLORS[s.cat] || '#888';
    cvList.insertAdjacentHTML('beforeend',
      `<li><span class="sk-dot" style="background:${col}"></span>${s.name}
       <span class="sk-cat">${s.cat||''}</span>
       <span class="sk-level">Lv ${s.level} &middot; ${s.confidence||'?'}%</span></li>`);
  });

  // Gaps
  const gapList  = document.getElementById('res-gaps');
  const gapTitle = document.getElementById('gap-title');
  document.getElementById('gap-count').textContent = d.gaps.length;
  if (d.has_jd) gapTitle.innerHTML = 'Skills to Develop <span class="count-badge gap-count" id="gap-count">'+d.gaps.length+'</span>';
  gapList.innerHTML = '';
  d.gaps.forEach(s => {
    gapList.insertAdjacentHTML('beforeend',
      `<li><span class="sk-dot" style="background:var(--gap)"></span>${s.name}
       <span class="sk-cat">${s.cat||''}</span>
       <span class="sk-level">Lv ${s.level}</span></li>`);
  });

  // Graph
  renderGraph(d.graph);

  // Paths
  const pathsEl = document.getElementById('res-paths');
  pathsEl.innerHTML = '';
  const pathEntries = Object.entries(d.paths||{});
  if (!pathEntries.length) {
    pathsEl.innerHTML = '<p style="font-family:var(--mono);font-size:.8rem;color:var(--muted)">No direct paths computed in current taxonomy.</p>';
  } else {
    pathEntries.forEach(([,p]) => {
      const stepsHtml = p.steps.map((st,i) =>
        `<span class="path-step${i===0?' start':''}">${st.name}</span>${i<p.steps.length-1?'<span class="path-arrow">&#8594;</span>':''}`
      ).join('');
      pathsEl.insertAdjacentHTML('beforeend',
        `<div class="path-item"><div class="path-to">&#8594; ${p.to}</div><div class="path-steps">${stepsHtml}</div></div>`);
    });
  }

  // Plan
  document.getElementById('res-plan').textContent = d.learning_plan || '—';

  resultsSec.classList.remove('hidden');
  resultsSec.scrollIntoView({ behavior:'smooth' });
}

// ── SVG Graph ─────────────────────────────────────────────────────────────
function renderGraph(g) {
  const svg = document.getElementById('graph-svg');
  svg.innerHTML = '';
  if (!g||!g.nodes.length) { svg.innerHTML='<text x="20" y="30" fill="#64748b" font-size="12" font-family="JetBrains Mono">No graph data.</text>'; return; }

  const wrap = document.getElementById('graph-wrap');
  const W = wrap.clientWidth || 900;
  const H = wrap.clientHeight || 400;

  // Layout: group by level
  const levels = {};
  g.nodes.forEach(n => { if (!levels[n.level]) levels[n.level]=[];  levels[n.level].push(n); });
  const lkeys = Object.keys(levels).sort((a,b)=>+a-+b);
  const nodeMap = {};

  g.nodes.forEach(n => {
    const li  = lkeys.indexOf(String(n.level));
    const grp = levels[n.level];
    const gi  = grp.indexOf(n);
    n.x = ((li+0.5)/lkeys.length)*(W-80)+40;
    n.y = ((gi+0.5)/grp.length)*(H-60)+30;
    nodeMap[n.id] = n;
  });

  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);

  // Defs
  const defs = document.createElementNS('http://www.w3.org/2000/svg','defs');
  lkeys.forEach(lk => {
    const first = levels[lk][0];
    const col = first ? (CAT_COLORS[first.cat]||'#888') : '#888';
    const hex = col.replace('#','');
    defs.innerHTML += `<marker id="arr-${hex}" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <polygon points="0 0,8 3,0 6" fill="${col}" opacity="0.5"/></marker>`;
  });
  // generic arrow
  defs.innerHTML += `<marker id="arr-gen" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0 0,8 3,0 6" fill="#334155"/></marker>`;
  svg.appendChild(defs);

  // Edges
  g.edges.forEach(e => {
    const s = nodeMap[e.from], t = nodeMap[e.to];
    if (!s||!t) return;
    const dx=t.x-s.x, dy=t.y-s.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
    const r=10;
    const x1=s.x+dx/dist*r, y1=s.y+dy/dist*r;
    const x2=t.x-dx/dist*(r+8), y2=t.y-dy/dist*(r+8);
    const line = document.createElementNS('http://www.w3.org/2000/svg','line');
    line.setAttribute('x1',x1);line.setAttribute('y1',y1);
    line.setAttribute('x2',x2);line.setAttribute('y2',y2);
    line.setAttribute('stroke','#1e2a35');line.setAttribute('stroke-width','1.5');
    line.setAttribute('marker-end','url(#arr-gen)');
    svg.appendChild(line);
  });

  // Nodes
  g.nodes.forEach(n => {
    const col = n.color || CAT_COLORS[n.cat] || '#888';
    const grp = document.createElementNS('http://www.w3.org/2000/svg','g');
    grp.setAttribute('transform',`translate(${n.x},${n.y})`);
    grp.style.cursor='pointer';

    const ring = document.createElementNS('http://www.w3.org/2000/svg','circle');
    ring.setAttribute('r',13);
    ring.setAttribute('fill','none');
    ring.setAttribute('stroke', n.owned?col:(n.required?'#fb923c':'#1e2a35'));
    ring.setAttribute('stroke-width', n.owned||n.required?2:1);
    grp.appendChild(ring);

    const circle = document.createElementNS('http://www.w3.org/2000/svg','circle');
    circle.setAttribute('r',10);
    circle.setAttribute('fill',col);
    circle.setAttribute('fill-opacity', n.owned?'0.9':'0.25');
    grp.appendChild(circle);

    const title = document.createElementNS('http://www.w3.org/2000/svg','title');
    title.textContent=`${n.label} | Level ${n.level} | ${n.cat}`;
    grp.appendChild(title);

    const label = document.createElementNS('http://www.w3.org/2000/svg','text');
    label.setAttribute('x',16);label.setAttribute('y',4);
    label.setAttribute('font-size','9');
    label.setAttribute('font-family','JetBrains Mono,monospace');
    label.setAttribute('fill', n.owned?'#e2e8f0':'#64748b');
    label.setAttribute('font-weight', n.owned?'500':'400');
    const short = n.label.length>24 ? n.label.slice(0,22)+'…' : n.label;
    label.textContent = short;
    grp.appendChild(label);

    svg.appendChild(grp);
  });

  // Legend
  const leg = document.getElementById('graph-legend');
  leg.innerHTML = Object.entries(CAT_COLORS).map(([cat,col])=>
    `<span class="leg-item"><span class="leg-dot" style="background:${col}"></span>${cat}</span>`
  ).join('');
  leg.insertAdjacentHTML('beforeend',`
    <span class="leg-item"><span class="leg-dot" style="background:#4ade80;opacity:.9"></span>Owned</span>
    <span class="leg-item"><span style="width:8px;height:8px;border-radius:50%;border:2px solid #fb923c;display:inline-block"></span>&nbsp;Required</span>`);
}

// ── Utils ─────────────────────────────────────────────────────────────────
function showError(msg){errorBox.textContent=msg;errorBox.classList.remove('hidden')}
function hideError(){errorBox.classList.add('hidden')}
