// app.js — HealthSkill Graph
// Lógica del frontend: tabs, upload, análisis, renderizado de resultados y grafo SVG.
// Si algo falla en el browser, abre DevTools > Console y busca el error ahí.

// ── COLORES POR CATEGORÍA ──────────────────────────────────────────────────
// Tienen que coincidir con los de Python (CAT_COLORS en main.py)
const CAT_COLORS = {
  "Foundation":     "#3b82f6",
  "Clinical Skills":"#10b981",
  "Surgery":        "#ec4899",
  "Research":       "#f59e0b",
  "Digital Health": "#8b5cf6",
  "Management":     "#ef4444",
};

// ── MANEJO DE PESTAÑAS ─────────────────────────────────────────────────────
function switchTab(tabName, clickedBtn) {
  // Desactivamos todo
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  // Activamos el seleccionado
  document.getElementById('tab-' + tabName).classList.add('active');
  if (clickedBtn) clickedBtn.classList.add('active');
}

function switchTabByName(name) {
  // Versión sin pasar el botón — útil para llamadas programáticas
  const btn = document.querySelector(`.tab-btn[onclick*="${name}"]`);
  switchTab(name, btn);
}

// ── MANEJO DE ARCHIVOS: CV ─────────────────────────────────────────────────
const cvInput    = document.getElementById('cv-input');
const cvDrop     = document.getElementById('cv-drop');
const cvFilename = document.getElementById('cv-filename');

// Cuando el usuario elige un archivo normal
cvInput.addEventListener('change', () => {
  if (cvInput.files[0]) {
    cvFilename.textContent = cvInput.files[0].name;
    document.getElementById('preview-btn').disabled = false;
    document.getElementById('analyze-cv-btn').disabled = false;
    document.getElementById('analyze-jd-btn').disabled = false;
  }
});

// Drag & drop para el CV
cvDrop.addEventListener('dragover', e => { e.preventDefault(); cvDrop.classList.add('over'); });
cvDrop.addEventListener('dragleave', () => cvDrop.classList.remove('over'));
cvDrop.addEventListener('drop', e => {
  e.preventDefault();
  cvDrop.classList.remove('over');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  if (!isValidFile(f.name)) { showError('cv-error', 'Solo PDF o DOCX'); return; }
  setFileToInput(cvInput, f);
  cvFilename.textContent = f.name;
  document.getElementById('preview-btn').disabled = false;
  document.getElementById('analyze-cv-btn').disabled = false;
  document.getElementById('analyze-jd-btn').disabled = false;
});

// ── MANEJO DE ARCHIVOS: JD ─────────────────────────────────────────────────
const jdInput    = document.getElementById('jd-input');
const jdDrop     = document.getElementById('jd-drop');
const jdFilename = document.getElementById('jd-filename');

jdInput.addEventListener('change', () => {
  if (jdInput.files[0]) jdFilename.textContent = jdInput.files[0].name;
});

jdDrop.addEventListener('dragover', e => { e.preventDefault(); jdDrop.classList.add('over'); });
jdDrop.addEventListener('dragleave', () => jdDrop.classList.remove('over'));
jdDrop.addEventListener('drop', e => {
  e.preventDefault();
  jdDrop.classList.remove('over');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  if (!isValidFile(f.name)) { showError('jd-error', 'Solo PDF o DOCX'); return; }
  setFileToInput(jdInput, f);
  jdFilename.textContent = f.name;
});

// ── HELPERS DE ARCHIVOS ────────────────────────────────────────────────────
function isValidFile(name) {
  return /\.(pdf|doc|docx)$/i.test(name);
}

function setFileToInput(input, file) {
  // Inyectar archivo al input de forma programática (para drag&drop)
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
}

// ── PREVIEW DEL CV ─────────────────────────────────────────────────────────
async function previewCV() {
  if (!cvInput.files[0]) return;
  hideError('cv-error');

  // Mostramos el loader del preview
  document.getElementById('preview-loader').classList.remove('hidden');
  document.getElementById('cv-preview-card').classList.add('hidden');

  const fd = new FormData();
  fd.append('cv', cvInput.files[0]);

  try {
    const res  = await fetch('/preview-cv', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.error) { showError('cv-error', data.error); return; }

    // Mostramos metadata del archivo
    document.getElementById('cv-meta').innerHTML = `
      <span class="meta-pill">📄 ${data.filename}</span>
      <span class="meta-pill">📝 ${data.word_count} palabras</span>
    `;

    const content = document.getElementById('cv-preview-content');

    // Si es PDF y tenemos base64, mostramos el embed del PDF
    if (data.pdf_base64) {
      content.innerHTML = `<iframe class="pdf-embed"
        src="data:application/pdf;base64,${data.pdf_base64}"
        type="application/pdf"></iframe>`;
    } else {
      // Si es DOCX, mostramos el texto extraído
      content.innerHTML = `<div class="cv-preview-box">${escapeHTML(data.text)}</div>`;
    }

    document.getElementById('cv-preview-card').classList.remove('hidden');

  } catch (e) {
    showError('cv-error', 'Error al leer el archivo. Intenta de nuevo.');
  } finally {
    document.getElementById('preview-loader').classList.add('hidden');
  }
}

// ── ANÁLISIS PRINCIPAL ─────────────────────────────────────────────────────
// Este es el flujo principal: manda CV + JD al servidor, recibe resultados,
// los distribuye en la pestaña de resultados.
const LOADER_MSGS = [
  'Extrayendo texto del CV...',
  'Identificando competencias clínicas (Locator)...',
  'Construyendo grafo de conocimiento (Connector)...',
  'Calculando rutas de aprendizaje (Pathfinder)...',
  'Generando plan de desarrollo con Claude...',
];

async function analyzeFull() {
  if (!cvInput.files[0]) {
    alert('Por favor sube un CV primero en la pestaña Candidato.');
    switchTabByName('candidate');
    return;
  }

  hideError('cv-error');
  hideError('jd-error');

  // Cambiamos a la pestaña de resultados y mostramos loader
  switchTabByName('results');
  document.getElementById('results-empty').classList.add('hidden');
  document.getElementById('results-content').classList.add('hidden');
  document.getElementById('loader').classList.remove('hidden');

  // Animamos los mensajes del loader
  let mi = 0;
  const loaderMsg = document.getElementById('loader-msg');
  const msgInterval = setInterval(() => {
    mi = (mi + 1) % LOADER_MSGS.length;
    loaderMsg.textContent = LOADER_MSGS[mi];
  }, 3000);

  const fd = new FormData();
  fd.append('cv', cvInput.files[0]);
  if (jdInput.files[0]) fd.append('jd', jdInput.files[0]);
  const jdTxt = document.getElementById('jd-text').value.trim();
  if (jdTxt) fd.append('jd_text', jdTxt);

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    clearInterval(msgInterval);

    if (!res.ok || data.error) {
      document.getElementById('loader').classList.add('hidden');
      document.getElementById('results-empty').classList.remove('hidden');
      alert('Error: ' + (data.error || 'Algo salió mal. Revisa los logs de Render.'));
      return;
    }

    renderResults(data);

  } catch (e) {
    clearInterval(msgInterval);
    document.getElementById('loader').classList.add('hidden');
    document.getElementById('results-empty').classList.remove('hidden');
    alert('Error de red. Verifica que el servidor esté corriendo.');
  }
}

// ── RENDERIZAR RESULTADOS ──────────────────────────────────────────────────
function renderResults(d) {
  document.getElementById('loader').classList.add('hidden');
  document.getElementById('results-content').classList.remove('hidden');

  // Marcamos la pestaña con badge de "Nuevo"
  document.getElementById('results-badge').classList.remove('hidden');

  // ── STATS RÁPIDAS ──────────────────────────────────────────────
  const statsRow = document.getElementById('stats-row');
  statsRow.innerHTML = `
    <div class="stat-card">
      <div class="stat-num" style="color:var(--green)">${d.cv_skills.length}</div>
      <div class="stat-lbl">Habilidades detectadas</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--orange)">${d.gaps.length}</div>
      <div class="stat-lbl">Brechas identificadas</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--purple)">${Object.keys(d.paths).length}</div>
      <div class="stat-lbl">Rutas calculadas</div>
    </div>
  `;

  // ── MATCH BANNER ───────────────────────────────────────────────
  if (d.has_jd && d.match_pct !== null) {
    document.getElementById('match-banner').classList.remove('hidden');
    document.getElementById('match-pct-val').textContent = d.match_pct + '%';
    // Animamos la barra con un pequeño delay para que se vea el efecto
    setTimeout(() => {
      document.getElementById('match-bar').style.width = d.match_pct + '%';
    }, 100);

    // Chips de skills: verde=tiene, naranja=falta, azul=extra
    const chips = document.getElementById('match-chips');
    chips.innerHTML = '';
    (d.matched || []).slice(0, 5).forEach(s =>
      chips.insertAdjacentHTML('beforeend', `<span class="match-chip chip-ok">✓ ${s.name}</span>`));
    (d.missing || []).slice(0, 5).forEach(s =>
      chips.insertAdjacentHTML('beforeend', `<span class="match-chip chip-miss">○ ${s.name}</span>`));
    (d.bonus  || []).slice(0, 3).forEach(s =>
      chips.insertAdjacentHTML('beforeend', `<span class="match-chip chip-plus">+ ${s.name}</span>`));
  }

  // ── RESÚMENES ──────────────────────────────────────────────────
  document.getElementById('res-cv-summary').textContent = d.cv_summary || '—';
  if (d.has_jd && d.jd_summary) {
    document.getElementById('jd-summary-card').style.display = '';
    document.getElementById('res-jd-summary').textContent = d.jd_summary;
  }

  // ── LISTA DE HABILIDADES DEL CV ────────────────────────────────
  const cvSkillsList = document.getElementById('res-cv-skills');
  document.getElementById('cv-skills-count').textContent = d.cv_skills.length;
  cvSkillsList.innerHTML = '';
  (d.cv_skills || []).forEach(s => {
    const color = CAT_COLORS[s.cat] || '#888';
    cvSkillsList.insertAdjacentHTML('beforeend', `
      <li class="skill-item">
        <span class="skill-dot" style="background:${color}"></span>
        <span class="skill-name">${s.name}</span>
        <span class="skill-cat">${s.cat || ''}</span>
        <span class="skill-level">Lv ${s.level}</span>
        <span class="skill-conf">${s.confidence || '?'}%</span>
      </li>`);
  });

  // Habilidades mencionadas pero no en taxonomía
  if (d.unmapped && d.unmapped.length) {
    document.getElementById('unmapped-box').classList.remove('hidden');
    document.getElementById('unmapped-text').textContent = d.unmapped.join(', ');
  }

  // ── BRECHAS / COMPETENCIAS A DESARROLLAR ──────────────────────
  const gapsList = document.getElementById('res-gaps');
  document.getElementById('gap-count').textContent = d.gaps.length;
  if (d.has_jd) {
    document.getElementById('gap-title').innerHTML =
      `<span class="dot" style="background:var(--orange)"></span>Skills Requeridas que Faltan <span class="badge badge-orange" id="gap-count">${d.gaps.length}</span>`;
  }
  gapsList.innerHTML = '';
  (d.gaps || []).forEach(s => {
    gapsList.insertAdjacentHTML('beforeend', `
      <li class="skill-item">
        <span class="skill-dot" style="background:var(--orange)"></span>
        <span class="skill-name">${s.name}</span>
        <span class="skill-cat">${s.cat || ''}</span>
        <span class="skill-level">Lv ${s.level}</span>
      </li>`);
  });

  // ── GRAFO SVG ──────────────────────────────────────────────────
  renderGraph(d.graph);

  // ── RUTAS DE APRENDIZAJE ───────────────────────────────────────
  const pathsEl = document.getElementById('res-paths');
  pathsEl.innerHTML = '';
  const pathEntries = Object.entries(d.paths || {});

  if (!pathEntries.length) {
    pathsEl.innerHTML = `<p style="font-size:0.82rem; color:var(--gray-400);">No se encontraron rutas directas en la taxonomía actual.</p>`;
  } else {
    pathEntries.forEach(([, p]) => {
      // Construimos la cadena de pasos visualmente
      const stepsHTML = p.steps.map((step, i) =>
        `<span class="path-step ${i === 0 ? 'start' : ''}">${step.name}</span>` +
        (i < p.steps.length - 1 ? '<span class="path-arrow">→</span>' : '')
      ).join('');

      pathsEl.insertAdjacentHTML('beforeend', `
        <div class="path-item">
          <div class="path-title">→ ${p.to} (${p.length - 1} pasos)</div>
          <div class="path-steps">${stepsHTML}</div>
        </div>`);
    });
  }

  // ── PLAN DE APRENDIZAJE ────────────────────────────────────────
  // El plan viene con formato markdown básico — lo dejamos como texto
  document.getElementById('res-plan').textContent = d.learning_plan || '—';
}

// ── RENDERIZADOR DEL GRAFO SVG ─────────────────────────────────────────────
// Layout por niveles (como un árbol), nodos con colores por categoría.
// Nodos verdes = skills que tiene el candidato
// Borde naranja = skills requeridas por el puesto
function renderGraph(g) {
  const svg = document.getElementById('graph-svg');
  svg.innerHTML = '';

  if (!g || !g.nodes.length) {
    svg.innerHTML = '<text x="20" y="40" fill="#94a3b8" font-size="13" font-family="Inter">Sin datos de grafo.</text>';
    return;
  }

  const wrap = document.getElementById('graph-svg').closest('.graph-wrap');
  const W = wrap.clientWidth  || 900;
  const H = wrap.clientHeight || 420;

  // Agrupar nodos por nivel para el layout
  const byLevel = {};
  g.nodes.forEach(n => {
    if (!byLevel[n.level]) byLevel[n.level] = [];
    byLevel[n.level].push(n);
  });
  const levels = Object.keys(byLevel).sort((a, b) => +a - +b);
  const nodeMap = {};

  // Posicionamos cada nodo en una grilla basada en su nivel
  g.nodes.forEach(n => {
    const li  = levels.indexOf(String(n.level));
    const grp = byLevel[n.level];
    const gi  = grp.indexOf(n);
    n.x = ((li + 0.5) / levels.length) * (W - 100) + 50;
    n.y = ((gi + 0.5) / grp.length) * (H - 80) + 40;
    nodeMap[n.id] = n;
  });

  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  // Definimos la punta de flecha
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  defs.innerHTML = `<marker id="arrowhead" markerWidth="8" markerHeight="6"
    refX="8" refY="3" orient="auto">
    <polygon points="0 0,8 3,0 6" fill="#cbd5e1"/>
  </marker>`;
  svg.appendChild(defs);

  // Dibujamos las aristas primero (para que queden debajo de los nodos)
  g.edges.forEach(e => {
    const s = nodeMap[e.from], t = nodeMap[e.to];
    if (!s || !t) return;

    const dx = t.x - s.x, dy = t.y - s.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const r = 14;
    const x1 = s.x + dx / dist * r, y1 = s.y + dy / dist * r;
    const x2 = t.x - dx / dist * (r + 10), y2 = t.y - dy / dist * (r + 10);

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('stroke', '#e2e8f0');
    line.setAttribute('stroke-width', '1.5');
    line.setAttribute('marker-end', 'url(#arrowhead)');
    svg.appendChild(line);
  });

  // Dibujamos los nodos
  g.nodes.forEach(n => {
    const color = n.color || CAT_COLORS[n.cat] || '#94a3b8';
    const grp = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    grp.setAttribute('transform', `translate(${n.x},${n.y})`);
    grp.style.cursor = 'pointer';

    // Anillo exterior — naranja si lo requiere el puesto, verde si lo tiene el candidato
    if (n.required || n.owned) {
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      ring.setAttribute('r', 17);
      ring.setAttribute('fill', 'none');
      ring.setAttribute('stroke', n.owned ? '#10b981' : '#f59e0b');
      ring.setAttribute('stroke-width', '2');
      grp.appendChild(ring);
    }

    // Círculo principal del nodo
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('r', 13);
    circle.setAttribute('fill', color);
    circle.setAttribute('fill-opacity', n.owned ? '1' : '0.3');
    circle.setAttribute('stroke', color);
    circle.setAttribute('stroke-width', '1.5');
    grp.appendChild(circle);

    // Tooltip con nombre y nivel al hacer hover
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${n.label} | Nivel ${n.level} | ${n.cat}`;
    grp.appendChild(title);

    // Etiqueta de texto al lado del nodo
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', 18);
    label.setAttribute('y', 4);
    label.setAttribute('font-size', '9.5');
    label.setAttribute('font-family', 'Inter, sans-serif');
    label.setAttribute('fill', n.owned ? '#1e293b' : '#64748b');
    label.setAttribute('font-weight', n.owned ? '600' : '400');
    const shortName = n.label.length > 22 ? n.label.slice(0, 20) + '…' : n.label;
    label.textContent = shortName;
    grp.appendChild(label);

    svg.appendChild(grp);
  });

  // Leyenda del grafo
  const legend = document.getElementById('graph-legend');
  legend.innerHTML = Object.entries(CAT_COLORS).map(([cat, color]) =>
    `<span class="leg-item"><span class="leg-dot" style="background:${color}"></span>${cat}</span>`
  ).join('') + `
    <span class="leg-item"><span class="leg-dot" style="background:#10b981"></span>Candidato tiene</span>
    <span class="leg-item" style="display:flex;align-items:center;gap:4px;">
      <span style="width:10px;height:10px;border-radius:50%;border:2px solid #f59e0b;display:inline-block"></span>Puesto requiere
    </span>`;
}

// ── RESET ──────────────────────────────────────────────────────────────────
function resetAll() {
  // Limpiamos todo y volvemos al estado inicial
  cvInput.value = ''; jdInput.value = '';
  document.getElementById('jd-text').value = '';
  cvFilename.textContent = ''; jdFilename.textContent = '';
  document.getElementById('preview-btn').disabled = true;
  document.getElementById('analyze-cv-btn').disabled = true;
  document.getElementById('analyze-jd-btn').disabled = true;
  document.getElementById('cv-preview-card').classList.add('hidden');
  document.getElementById('results-content').classList.add('hidden');
  document.getElementById('results-empty').classList.remove('hidden');
  document.getElementById('results-badge').classList.add('hidden');
  document.getElementById('match-banner').classList.add('hidden');
  document.getElementById('match-bar').style.width = '0';
  switchTabByName('candidate');
}

// ── UTILS ──────────────────────────────────────────────────────────────────
function showError(elementId, msg) {
  const el = document.getElementById(elementId);
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}
function hideError(elementId) {
  const el = document.getElementById(elementId);
  if (el) el.classList.add('hidden');
}
function escapeHTML(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}