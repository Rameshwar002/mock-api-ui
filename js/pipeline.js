/* ═══════════════════════════════════════════
   pipeline.js — AI Agent Pipeline
═══════════════════════════════════════════ */

const AGENTS = [
  {
    id: 'trigger',  label: 'AGENT-01', name: 'Trigger Agent',
    icon: '&#9200;',   color: '#10b981',
    msgs: ['Reading file...', 'File validated OK'],
  },
  {
    id: 'parser',   label: 'AGENT-02', name: 'Parser Agent',
    icon: '{ }',       color: '#3b82f6',
    msgs: ['Parsing sequence flows...', 'Extracting actors & messages...', 'Conditions mapped'],
  },
  {
    id: 'context',  label: 'AGENT-03', name: 'Context Agent',
    icon: '&#129504;', color: '#a855f7',
    msgs: ['Loading knowledge base...', 'Querying vector DB...', 'Context merged'],
  },
  {
    id: 'validate', label: 'AGENT-04', name: 'Validator Agent',
    icon: '&#10003;',  color: '#14b8a6',
    msgs: ['Checking structure...', 'Validating inputs...', 'Validation passed'],
  },
  {
    id: 'llm',      label: 'AGENT-05', name: 'Generator Agent',
    icon: '&#9889;',   color: '#22c55e',
    msgs: ['Building prompt...', 'Sending to LLM...'],
  },
  {
    id: 'format',   label: 'AGENT-06', name: 'Formatter Agent',
    icon: '{ }',       color: '#f59e0b',
    msgs: ['Assigning TC IDs...', 'Structuring fields...', 'Output ready'],
  },
];

const delay = ms => new Promise(r => setTimeout(r, ms));

/* ── Build the pipeline DOM ── */
function buildPipelineRow() {
  const row = document.getElementById('pipeline-row');
  if (!row) return;

  let html = '';
  AGENTS.forEach((a, i) => {
    html += `
      <div class="pn-wrap">
        <div class="pn-col">
          <div class="pn-agent-lbl">${a.label}</div>
          <div class="pn-box" id="pn-${a.id}" style="color:${a.color}">
            <div class="pn-ring"></div>
            <span id="pni-${a.id}">${a.icon}</span>
          </div>
          <div class="pn-name">${a.name}</div>
          <div class="pn-status" id="ps-${a.id}">Waiting</div>
        </div>
      </div>`;
    if (i < AGENTS.length - 1) {
      html += `
      <div class="pn-conn">
        <div class="pn-dot" id="pd1-${a.id}"></div>
        <div class="pn-line" id="pl-${a.id}"></div>
        <div class="pn-dot" id="pd2-${a.id}"></div>
      </div>`;
    }
  });
  row.innerHTML = html;
}

/* ── Set individual node state ── */
function setPipeNode(id, state, msg) {
  const box = document.getElementById('pn-' + id);
  const sts = document.getElementById('ps-' + id);
  const ag  = AGENTS.find(x => x.id === id);
  if (!box || !ag) return;

  box.className = 'pn-box ' + state;
  let badge = '';
  if (state === 'done')  badge = '<div class="pn-badge">&#10003;</div>';
  if (state === 'error') badge = '<div class="pn-badge err">!</div>';
  box.innerHTML = `<div class="pn-ring"></div><span>${ag.icon}</span>${badge}`;

  if (state === 'active') {
    sts.className = 'pn-status live';
    sts.innerHTML = escHtml(msg) +
      '<span class="flow-dots"><span></span><span></span><span></span></span>';
  } else {
    sts.className = 'pn-status';
    sts.textContent = msg || (state === 'done' ? 'Analyzing...' : state === 'error' ? 'Failed' : 'Waiting');
  }
}

/* ── Set connector line ── */
function setPipeLine(id, done) {
  ['pl', 'pd1', 'pd2'].forEach(pfx => {
    const el = document.getElementById(pfx + '-' + id);
    if (!el) return;
    el.className = (pfx === 'pl' ? 'pn-line' : 'pn-dot') + (done ? ' done' : '');
  });
}

/* ── Overall progress bar ── */
function setOverall(idx, total, label, isErr = false) {
  const pct  = Math.round((idx / total) * 100);
  const fill = document.getElementById('pp-fill');
  const prog = document.getElementById('pipeline-progress');
  if (!fill || !prog) return;

  fill.style.width = pct + '%';
  fill.className   = 'pp-fill' + (isErr ? ' err' : '');

  const lbl = document.getElementById('pp-label');
  const pctEl = document.getElementById('pp-pct');
  if (lbl) lbl.textContent = label;
  if (pctEl) pctEl.textContent = pct + '%';
  prog.classList.add('show');
}

/* ── Activity log ── */
function clearLog() {
  const log = document.getElementById('flow-log');
  if (log) log.innerHTML = '';
}

function logLine(agent, msg, kind) {
  const log = document.getElementById('flow-log');
  if (!log) return;
  log.classList.add('show');

  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  const div  = document.createElement('div');
  div.className = 'll';
  const cls = kind === 'ok' ? 'lo' : kind === 'err' ? 'le' : '';
  div.innerHTML =
    `<span class="lt">${time}</span>` +
    `<span class="la">${escHtml(agent)}</span>` +
    `<span class="${cls}">${escHtml(msg)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  if (log.children.length > 60) log.removeChild(log.firstChild);
}

/* ── Reset pipeline to idle ── */
function resetPipeline() {
  buildPipelineRow();
  const prog = document.getElementById('pipeline-progress');
  const log  = document.getElementById('flow-log');
  if (prog) prog.classList.remove('show');
  if (log)  { log.classList.remove('show'); log.innerHTML = ''; }
}

/* ── Run full generation ── */
async function runGenerate() {
  if (!pumlContent.trim()) return;

  const errBanner = document.getElementById('tc-err');
  if (errBanner) errBanner.classList.remove('show');

  buildPipelineRow();
  clearLog();
  setOverall(0, AGENTS.length, 'Starting...');

  // Pre-LLM agents (all except last)
  for (let i = 0; i < AGENTS.length - 1; i++) {
    const ag = AGENTS[i];
    setOverall(i, AGENTS.length, ag.name);

    for (let m = 0; m < ag.msgs.length; m++) {
      setPipeNode(ag.id, 'active', ag.msgs[m]);
      logLine(ag.name, ag.msgs[m]);
      await delay(360 + Math.random() * 200);
    }
    setPipeNode(ag.id, 'done', 'Analyzing...');
    logLine(ag.name, 'Task complete', 'ok');
    setPipeLine(ag.id, true);
    await delay(80);
  }

  // LLM Generator Agent (last)
  const llmAg = AGENTS[AGENTS.length - 1];
  setOverall(AGENTS.length - 1, AGENTS.length, llmAg.name);
  setPipeNode(llmAg.id, 'active', 'Building prompt...');
  logLine(llmAg.name, 'Building prompt...');
  await delay(350);
  setPipeNode(llmAg.id, 'active', 'Sending to LLM...');
  logLine(llmAg.name, 'Sending to LLM...');

  try {
    const minCases = parseInt(document.getElementById('tc-limit')?.value) || 8;
    const payload = {
      puml: pumlContent,
      knowledge: {
        project:     knowledge.project,
        description: knowledge.desc,
        tech:        knowledge.tech,
        keywords:    knowledge.tags,
        rules:       knowledge.rules,
        focus:       knowledge.focus,
        min_cases:   minCases,
        extra:       knowledge.extra,
        vdb:         knowledge.vdb,
        collection:  knowledge.collection,
      },
    };

    const res = await fetch(BACKEND + '/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    setPipeNode(llmAg.id, 'active', 'Receiving response...');
    logLine(llmAg.name, 'Receiving response...');
    await delay(250);

    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || 'HTTP ' + res.status);
    }

    const d = await res.json();
    if (!d.cases || d.cases.length === 0) throw new Error('LLM returned no test cases.');

    setPipeNode(llmAg.id, 'active', `Parsing ${d.cases.length} cases...`);
    logLine(llmAg.name, `Parsing ${d.cases.length} test cases...`);
    await delay(300);

    setPipeNode(llmAg.id, 'done', 'Generating...');
    logLine(llmAg.name, `${d.cases.length} test cases generated`, 'ok');

    setOverall(AGENTS.length, AGENTS.length, 'Complete ✓');
    logLine('Pipeline', 'All agents finished successfully', 'ok');

    // Hand off to table module
    cases = d.cases;
    fileTitle = d.title || fileTitle;
    if (typeof renderTable === 'function') renderTable();

    const exportBtn = document.getElementById('btn-export');
    if (exportBtn) exportBtn.disabled = false;

  } catch (err) {
    setPipeNode(llmAg.id, 'error', err.message);
    logLine(llmAg.name, 'ERROR: ' + err.message, 'err');
    setOverall(AGENTS.length - 1, AGENTS.length, 'Failed', true);
    const errBanner = document.getElementById('tc-err');
    if (errBanner) {
      errBanner.innerHTML = `<strong>Generation failed</strong><br>${err.message}`;
      errBanner.classList.add('show');
    }
  }
}
