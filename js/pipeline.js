/* ═══════════════════════════════════════════
   pipeline.js — AI Agent Pipeline
   Each agent does REAL work, not mock delays.
═══════════════════════════════════════════ */

const AGENTS = [
  { id:'trigger',  label:'AGENT-01', name:'Trigger Agent',   icon:'&#9200;',   color:'#10b981' },
  { id:'parser',   label:'AGENT-02', name:'Parser Agent',    icon:'{ }',       color:'#3b82f6' },
  { id:'context',  label:'AGENT-03', name:'Context Agent',   icon:'&#129504;', color:'#a855f7' },
  { id:'validate', label:'AGENT-04', name:'Validator Agent', icon:'&#10003;',  color:'#14b8a6' },
  { id:'llm',      label:'AGENT-05', name:'Generator Agent', icon:'&#9889;',   color:'#22c55e' },
  { id:'format',   label:'AGENT-06', name:'Formatter Agent', icon:'{ }',       color:'#f59e0b' },
];

const delay = ms => new Promise(r => setTimeout(r, ms));

/* ══════════════════════════════════════════
   BUILD PIPELINE DOM
══════════════════════════════════════════ */
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

/* ══════════════════════════════════════════
   UI HELPERS
══════════════════════════════════════════ */
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
    sts.textContent = msg || (state === 'done' ? 'Done' : state === 'error' ? 'Failed' : 'Waiting');
  }
}

function setPipeLine(id, done) {
  ['pl','pd1','pd2'].forEach(pfx => {
    const el = document.getElementById(pfx + '-' + id);
    if (el) el.className = (pfx === 'pl' ? 'pn-line' : 'pn-dot') + (done ? ' done' : '');
  });
}

function setOverall(idx, total, label, isErr = false) {
  const pct  = Math.round((idx / total) * 100);
  const fill = document.getElementById('pp-fill');
  const prog = document.getElementById('pipeline-progress');
  if (!fill || !prog) return;
  fill.style.width = pct + '%';
  fill.className   = 'pp-fill' + (isErr ? ' err' : '');
  const lbl  = document.getElementById('pp-label');
  const pctEl= document.getElementById('pp-pct');
  if (lbl)   lbl.textContent  = label;
  if (pctEl) pctEl.textContent= pct + '%';
  prog.classList.add('show');
}

function clearLog() {
  const log = document.getElementById('flow-log');
  if (log) { log.innerHTML = ''; log.classList.add('show'); }
}

function logLine(agent, msg, kind) {
  const log = document.getElementById('flow-log');
  if (!log) return;
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
  if (log.children.length > 80) log.removeChild(log.firstChild);
}

function resetPipeline() {
  buildPipelineRow();
  const prog = document.getElementById('pipeline-progress');
  const log  = document.getElementById('flow-log');
  if (prog) prog.classList.remove('show');
  if (log)  { log.classList.remove('show'); log.innerHTML = ''; }
}

/* ══════════════════════════════════════════
   AGENT-01: TRIGGER AGENT
   Real work: validate file exists, check size,
   confirm it looks like a PUML file.
══════════════════════════════════════════ */
function runTriggerAgent() {
  return new Promise((resolve, reject) => {
    setPipeNode('trigger', 'active', 'Receiving file...');
    logLine('Trigger Agent', 'Received file: ' + (fileTitle || 'diagram') + '.puml');

    setTimeout(() => {
      if (!pumlContent || !pumlContent.trim()) {
        reject(new Error('No file content found. Please upload a PUML file.'));
        return;
      }

      const lines = pumlContent.trim().split('\n').length;
      const bytes = new Blob([pumlContent]).size;
      logLine('Trigger Agent', `File size: ${bytes} bytes, ${lines} lines`);

      // Basic format check
      const hasStart = pumlContent.includes('@startuml');
      const hasArrow = /->|-->|->>/.test(pumlContent);
      if (!hasStart && !hasArrow) {
        reject(new Error('File does not appear to be a valid PlantUML diagram.'));
        return;
      }

      logLine('Trigger Agent', 'File validation passed', 'ok');
      resolve({ lines, bytes });
    }, 200);
  });
}

/* ══════════════════════════════════════════
   AGENT-02: PARSER AGENT
   Real work: parse actors, messages, conditions,
   notes from PUML text. Return structured data.
══════════════════════════════════════════ */
function runParserAgent() {
  return new Promise((resolve, reject) => {
    setPipeNode('parser', 'active', 'Parsing PUML structure...');
    logLine('Parser Agent', 'Parsing sequence flows...');

    setTimeout(() => {
      try {
        const lines      = pumlContent.split('\n').map(l => l.trim()).filter(Boolean);
        const actors     = [];
        const messages   = [];
        const conditions = [];
        const notes      = [];
        let   title      = '';

        lines.forEach(line => {
          // Title
          if (/^title\s+/i.test(line)) {
            title = line.replace(/^title\s+/i, '').trim();
          }
          // Arrows / messages — check FIRST (most specific pattern,
          // prevents message lines like "Database --> Server : ..."
          // from being mis-matched by the looser actor-declaration regex)
          else if (/->|-->|->>|-->>/.test(line)) {
            const m = line.match(/^(\w+)\s*(?:->|-->|->>|-->>)\s*(\w+)\s*:\s*(.+)/);
            if (m) messages.push({ from: m[1], to: m[2], label: m[3].trim() });
          }
          // Actors / participants
          else if (/^(actor|participant|boundary|control|entity|database|component)\s+/i.test(line)) {
            const m = line.match(/\S+\s+"?([^"]+)"?(?:\s+as\s+(\w+))?/i);
            if (m) actors.push(m[2] || m[1].trim());
          }
          // Alt/opt/loop conditions
          else if (/^(alt|opt|loop|else|break)\s+/i.test(line)) {
            conditions.push(line.trim());
          }
          // Notes
          else if (/^note\s/i.test(line)) {
            notes.push(line.trim());
          }
        });

        logLine('Parser Agent', `Found ${actors.length} actors, ${messages.length} messages`);
        logLine('Parser Agent', `Found ${conditions.length} conditions, ${notes.length} notes`);
        if (title) logLine('Parser Agent', `Diagram title: "${title}"`);

        if (messages.length === 0) {
          logLine('Parser Agent', 'Warning: no sequence messages found — results may be limited', 'err');
        } else {
          logLine('Parser Agent', 'Parsing complete', 'ok');
        }

        resolve({ title, actors, messages, conditions, notes });
      } catch (e) {
        reject(new Error('Parser failed: ' + e.message));
      }
    }, 150);
  });
}

/* ══════════════════════════════════════════
   AGENT-03: CONTEXT AGENT
   Real work: merge knowledge base data,
   read VDB config, build context payload
   that will be sent to the LLM.
══════════════════════════════════════════ */
function runContextAgent(parsed) {
  return new Promise((resolve) => {
    setPipeNode('context', 'active', 'Loading knowledge base...');
    logLine('Context Agent', 'Reading knowledge base settings...');

    setTimeout(() => {
      // Read knowledge from global (set by knowledge.js)
      const kb = (typeof getKnowledge === 'function') ? getKnowledge() : knowledge;

      // Report what context was found
      if (kb.project)  logLine('Context Agent', `Project: "${kb.project}"`);
      if (kb.tech)     logLine('Context Agent', `Tech stack: ${kb.tech}`);
      if (kb.tags && kb.tags.length)
        logLine('Context Agent', `Domain keywords: ${kb.tags.join(', ')}`);
      if (kb.rules)    logLine('Context Agent', `Business rules loaded (${kb.rules.length} chars)`);
      if (kb.vdb)      logLine('Context Agent', `Vector DB configured: ${kb.vdb}`);
      else             logLine('Context Agent', 'No vector DB configured — using local context only');

      const minCases = parseInt(document.getElementById('tc-limit')?.value) || kb.mincount || 8;
      logLine('Context Agent', `Target test case count: ${minCases}`);
      logLine('Context Agent', `Focus area: ${kb.focus || 'all'}`);
      logLine('Context Agent', 'Context merged successfully', 'ok');

      resolve({
        project:     kb.project     || '',
        description: kb.desc        || '',
        tech:        kb.tech        || '',
        keywords:    kb.tags        || [],
        rules:       kb.rules       || '',
        focus:       kb.focus       || 'all',
        min_cases:   minCases,
        extra:       kb.extra       || '',
        vdb:         kb.vdb         || '',
        collection:  kb.collection  || '',
      });
    }, 150);
  });
}

/* ══════════════════════════════════════════
   AGENT-04: VALIDATOR AGENT
   Real work: check the parsed data and context
   are sufficient to generate good test cases.
   Warns about gaps. Can reject if too broken.
══════════════════════════════════════════ */
function runValidatorAgent(parsed, ctx) {
  return new Promise((resolve, reject) => {
    setPipeNode('validate', 'active', 'Validating inputs...');
    logLine('Validator Agent', 'Checking diagram completeness...');

    setTimeout(() => {
      const warnings = [];
      const errors   = [];

      // Check diagram
      if (!parsed.title)
        warnings.push('No diagram title found');
      if (parsed.actors.length === 0)
        warnings.push('No actors/participants detected');
      if (parsed.messages.length === 0)
        errors.push('No sequence messages found — cannot generate meaningful test cases');
      if (parsed.messages.length < 2)
        warnings.push('Very few messages — test cases may be limited');

      // Check context
      if (!ctx.project && !ctx.description)
        warnings.push('No project context provided (optional but improves quality)');

      // Log results
      warnings.forEach(w => logLine('Validator Agent', 'Warning: ' + w));
      errors.forEach(e   => logLine('Validator Agent', 'Error: '   + e, 'err'));

      if (errors.length > 0) {
        reject(new Error(errors[0]));
        return;
      }

      const actorList = parsed.actors.length > 0
        ? parsed.actors.join(', ')
        : 'not explicitly declared';
      logLine('Validator Agent', `Actors: ${actorList}`);
      logLine('Validator Agent', `Messages to cover: ${parsed.messages.length}`);
      logLine('Validator Agent', warnings.length === 0
        ? 'All checks passed — ready for LLM'
        : `Passed with ${warnings.length} warning(s)`, 'ok');

      resolve({ warnings, messageCount: parsed.messages.length });
    }, 200);
  });
}

/* ══════════════════════════════════════════
   AGENT-05: GENERATOR AGENT
   Real work: build the actual LLM prompt using
   parsed data + context, call /generate,
   stream status updates while waiting.
══════════════════════════════════════════ */
async function runGeneratorAgent(ctx) {
  setPipeNode('llm', 'active', 'Building prompt...');
  logLine('Generator Agent', 'Constructing LLM prompt...');
  await delay(200);

  const promptSize = pumlContent.length + JSON.stringify(ctx).length;
  logLine('Generator Agent', `Prompt payload: ~${promptSize} characters`);
  logLine('Generator Agent', `Min test cases requested: ${ctx.min_cases}`);
  logLine('Generator Agent', `Focus: ${ctx.focus}`);

  setPipeNode('llm', 'active', 'Sending to LLM...');
  logLine('Generator Agent', 'Sending request to LLM endpoint...');

  const startTime = Date.now();
  const timerInterval = setInterval(() => {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    setPipeNode('llm', 'active', `Waiting for LLM... (${elapsed}s)`);
  }, 500);

  try {
    const res = await fetch(BACKEND + '/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ puml: pumlContent, knowledge: ctx }),
    });

    clearInterval(timerInterval);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    logLine('Generator Agent', `LLM responded in ${elapsed}s`);

    setPipeNode('llm', 'active', 'Receiving response...');

    // Non-200 response
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${res.status} — LLM endpoint unreachable`);
    }

    const data = await res.json();

    // Backend returned an error field
    if (data.error) {
      throw new Error(data.error);
    }

    // No cases at all
    if (!data.cases || !Array.isArray(data.cases) || data.cases.length === 0) {
      throw new Error('LLM returned no test cases. Try rephrasing or adding more context in the Knowledge Base.');
    }

    // ── Critical fix: validate cases are actual objects, not error strings ──
    // When the LLM fails it sometimes returns a string-wrapped error in the
    // cases array (e.g. ["LLM generation failed..."]) instead of TC objects.
    const validCases = data.cases.filter(tc => {
      if (typeof tc !== 'object' || tc === null) return false;
      // A real TC must have at least a name or tc_id field
      return tc.name || tc.tc_id || tc.steps || tc.expected_output;
    });

    if (validCases.length === 0) {
      // All items were strings/garbage — likely LLM returned an error embedded in JSON
      const firstItem = data.cases[0];
      const errText = typeof firstItem === 'string'
        ? firstItem
        : JSON.stringify(firstItem).slice(0, 200);
      throw new Error(`LLM returned invalid data instead of test cases: "${errText}"`);
    }

    if (validCases.length < data.cases.length) {
      logLine('Generator Agent',
        `Warning: ${data.cases.length - validCases.length} malformed cases removed`, 'err');
    }

    logLine('Generator Agent', `Received ${validCases.length} valid test cases`, 'ok');
    return { ...data, cases: validCases };

  } catch (err) {
    clearInterval(timerInterval);
    throw err;
  }
}

/* ══════════════════════════════════════════
   AGENT-06: FORMATTER AGENT
   Real work: validate each TC has required
   fields, assign missing IDs, normalise types
   and priorities, count and report.
══════════════════════════════════════════ */
function runFormatterAgent(rawData) {
  return new Promise((resolve, reject) => {
    setPipeNode('format', 'active', 'Validating test case schema...');

    // ── Guard: rawData must be valid before we even start ──
    if (!rawData || !Array.isArray(rawData.cases) || rawData.cases.length === 0) {
      reject(new Error('Formatter received empty or invalid data from Generator Agent.'));
      return;
    }

    // Double-check no string entries snuck through
    const nonObjects = rawData.cases.filter(tc => typeof tc !== 'object' || tc === null);
    if (nonObjects.length > 0) {
      const sample = String(nonObjects[0]).slice(0, 120);
      reject(new Error(`Formatter received non-object entries in cases array: "${sample}"`));
      return;
    }

    logLine('Formatter Agent', `Processing ${rawData.cases.length} test cases...`);

    setTimeout(() => {
      try {
        const REQUIRED = ['tc_id','module','name','type','priority','prerequisite','steps','expected_output'];
        const VALID_TYPES = ['Positive','Negative','Functional','Security'];
        const VALID_PRIS  = ['High','Medium','Low'];

        let fixed = 0;

        const formatted = rawData.cases.map((tc, i) => {
          const out = { ...tc };

          // Assign missing IDs
          if (!out.tc_id) { out.tc_id = 'TC-' + String(i + 1).padStart(3,'0'); fixed++; }

          // Ensure all fields exist
          REQUIRED.forEach(k => { if (!out[k]) out[k] = ''; });

          // Default status
          if (!out.status) out.status = 'Pending';

          // Normalise type
          if (!VALID_TYPES.includes(out.type)) {
            const guess = VALID_TYPES.find(t => out.type?.toLowerCase().includes(t.toLowerCase()));
            out.type = guess || 'Functional';
            fixed++;
          }

          // Normalise priority
          if (!VALID_PRIS.includes(out.priority)) {
            out.priority = 'Medium';
            fixed++;
          }

          return out;
        });

        // Stats
        const byType = {};
        const byPri  = {};
        formatted.forEach(tc => {
          byType[tc.type]     = (byType[tc.type]     || 0) + 1;
          byPri[tc.priority]  = (byPri[tc.priority]  || 0) + 1;
        });

        logLine('Formatter Agent', `Schema fixes applied: ${fixed}`);
        logLine('Formatter Agent', 'Type breakdown: ' +
          Object.entries(byType).map(([k,v]) => `${k}:${v}`).join(', '));
        logLine('Formatter Agent', 'Priority breakdown: ' +
          Object.entries(byPri).map(([k,v]) => `${k}:${v}`).join(', '));
        logLine('Formatter Agent',
          `${formatted.length} test cases formatted and ready`, 'ok');

        resolve({ ...rawData, cases: formatted });
      } catch (e) {
        reject(new Error('Formatter error: ' + e.message));
      }
    }, 150);
  });
}

/* ══════════════════════════════════════════
   MAIN RUN — orchestrates all real agents
══════════════════════════════════════════ */
async function runGenerate() {
  if (!pumlContent || !pumlContent.trim()) {
    const errBanner = document.getElementById('tc-err');
    if (errBanner) {
      errBanner.innerHTML = '<strong>No file uploaded</strong><br>Please upload a PUML file first.';
      errBanner.classList.add('show');
    }
    return;
  }

  // Reset UI
  const errBanner = document.getElementById('tc-err');
  if (errBanner) errBanner.classList.remove('show');
  buildPipelineRow();
  clearLog();
  setOverall(0, AGENTS.length, 'Starting pipeline...');

  logLine('Pipeline', '═══ Starting AI Agent Pipeline ═══');
  logLine('Pipeline', `File: ${fileTitle}.puml`);

  let parsed, ctx, validResult, rawData, finalData;

  /* ── AGENT 01: Trigger ── */
  try {
    setPipeNode('trigger', 'active', 'Validating file...');
    setOverall(0, AGENTS.length, 'Agent 01 — Trigger');
    const result = await runTriggerAgent();
    logLine('Trigger Agent', `✓ ${result.lines} lines, ${result.bytes} bytes`);
    setPipeNode('trigger', 'done', `${result.lines} lines read`);
    setPipeLine('trigger', true);
  } catch (err) {
    setPipeNode('trigger', 'error', err.message);
    logLine('Trigger Agent', err.message, 'err');
    setOverall(0, AGENTS.length, 'Failed at Trigger', true);
    showError(err.message); return;
  }

  await delay(80);

  /* ── AGENT 02: Parser ── */
  try {
    setOverall(1, AGENTS.length, 'Agent 02 — Parser');
    parsed = await runParserAgent();
    setPipeNode('parser', 'done',
      `${parsed.actors.length} actors · ${parsed.messages.length} msgs`);
    setPipeLine('parser', true);
  } catch (err) {
    setPipeNode('parser', 'error', err.message);
    logLine('Parser Agent', err.message, 'err');
    setOverall(1, AGENTS.length, 'Failed at Parser', true);
    showError(err.message); return;
  }

  await delay(80);

  /* ── AGENT 03: Context ── */
  try {
    setOverall(2, AGENTS.length, 'Agent 03 — Context');
    ctx = await runContextAgent(parsed);
    const ctxItems = [
      ctx.project && 'project',
      ctx.tech    && 'tech',
      ctx.keywords?.length && 'keywords',
      ctx.rules   && 'rules',
    ].filter(Boolean);
    setPipeNode('context', 'done',
      ctxItems.length ? `Loaded: ${ctxItems.join(', ')}` : 'No knowledge context');
    setPipeLine('context', true);
  } catch (err) {
    setPipeNode('context', 'error', err.message);
    logLine('Context Agent', err.message, 'err');
    setOverall(2, AGENTS.length, 'Failed at Context', true);
    showError(err.message); return;
  }

  await delay(80);

  /* ── AGENT 04: Validator ── */
  try {
    setOverall(3, AGENTS.length, 'Agent 04 — Validator');
    validResult = await runValidatorAgent(parsed, ctx);
    setPipeNode('validate', 'done',
      validResult.warnings.length === 0
        ? `${validResult.messageCount} messages — all checks passed`
        : `${validResult.warnings.length} warnings — continuing`);
    setPipeLine('validate', true);
  } catch (err) {
    setPipeNode('validate', 'error', err.message);
    logLine('Validator Agent', err.message, 'err');
    setOverall(3, AGENTS.length, 'Failed at Validator', true);
    showError(err.message); return;
  }

  await delay(80);

  /* ── AGENT 05: Generator (real LLM call) ── */
  try {
    setOverall(4, AGENTS.length, 'Agent 05 — LLM Generation');
    rawData = await runGeneratorAgent(ctx);
    // Only mark done AFTER we have confirmed valid data back
    setPipeNode('llm', 'done', `${rawData.cases.length} cases received`);
    setPipeLine('llm', true);
  } catch (err) {
    // Mark Generator as error — Formatter never runs
    setPipeNode('llm', 'error', err.message.slice(0, 60));
    logLine('Generator Agent', 'FAILED: ' + err.message, 'err');
    setOverall(4, AGENTS.length, 'Failed at Generator Agent', true);
    showError(err.message);
    return;  // ← hard stop: nothing below this runs
  }

  await delay(80);

  /* ── AGENT 06: Formatter (real schema work) ── */
  try {
    setOverall(5, AGENTS.length, 'Agent 06 — Formatter');
    finalData = await runFormatterAgent(rawData);
    setPipeNode('format', 'done', `${finalData.cases.length} cases ready`);
    setPipeLine('format', true);
  } catch (err) {
    setPipeNode('format', 'error', err.message.slice(0, 60));
    logLine('Formatter Agent', 'FAILED: ' + err.message, 'err');
    setOverall(5, AGENTS.length, 'Failed at Formatter Agent', true);
    showError(err.message);
    return;
  }

  /* ── All done ── */
  setOverall(AGENTS.length, AGENTS.length, `Complete — ${finalData.cases.length} test cases`);
  logLine('Pipeline', `═══ Pipeline complete: ${finalData.cases.length} test cases ═══`, 'ok');

  // Hand off to table
  cases     = finalData.cases;
  fileTitle = finalData.title || fileTitle;
  if (typeof renderTable === 'function') renderTable();

  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = false;
}

/* ── Error helper ── */
function showError(msg) {
  const el = document.getElementById('tc-err');
  if (el) {
    el.innerHTML = `<strong>Pipeline failed</strong><br>${escHtml(msg)}`;
    el.classList.add('show');
  }
}
