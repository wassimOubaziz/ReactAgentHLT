const $ = (id) => document.getElementById(id);
const trace = $("trace");
let examples = [];
let selected = -1;
let dirty = false;
let running = false;
let ctx = {};

const AGENTS = { default: "Standard", cot: "CoT", react: "ReAct", focused: "Focused ReAct" };
const FLOWS = {
  default: ["Question", "LLM call", "Answer"],
  cot: ["Question", "LLM call · step by step", "Answer"],
  react: ["Question", "LLM call", "Action", "Observation", "↻ repeat", "Finish"],
  focused: ["Question", "LLM call", "Action ⇄ Observation", "Early stop", "Forced Finish"],
};
const BLURBS = {
  default: "One LLM call. The model answers directly, with no tools and no reasoning scaffold.",
  cot: "One LLM call. The model reasons step by step, then writes Answer:.",
  react: "A loop of Thought → Action → Observation, up to 7 LLM calls. Search or Calculate runs between calls.",
  focused: "The same loop, but the question is restated every turn and repeated actions stop it early. It then gets one forced final call.",
};

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const speed = () => Number($("speed").value);
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const rate = () => (speed() === 0 || reduced() ? 0 : speed() / 700);
const wait = (ms) => new Promise((r) => setTimeout(r, ms * rate()));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function bump(id, n = 1) {
  $(id).textContent = String(Number($(id).textContent) + n);
}

function addCard(cls, title, html) {
  const el = document.createElement("div");
  el.className = `card ${cls}`;
  el.innerHTML = `<h3>${title}</h3>${html}`;
  trace.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return el;
}

async function type(el, text, budget = 800) {
  text = String(text ?? "");
  if (!rate()) {
    el.textContent = text;
    return;
  }
  el.textContent = "";
  el.classList.add("typing");
  const perChar = Math.min(8, budget / Math.max(1, text.length));
  const chunk = Math.max(1, Math.round(8 / perChar));
  for (let i = 0; i < text.length; i += chunk) {
    el.textContent += text.slice(i, i + chunk);
    if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight;
    await wait(perChar * chunk);
  }
  el.classList.remove("typing");
}

function pulse(kind) {
  document.querySelectorAll("#pipeline span").forEach((s) => s.classList.remove("active"));
  const stage = {
    meta: "question", question: "question", prompt: "prompt", completion: "llm", thought: "thought",
    action: "tool", tool_result: "tool", invalid_action: "tool", observation: "observation",
    stop: "finish", finish: "finish", result: "finish",
  }[kind];
  if (stage) document.querySelector(`#pipeline span[data-stage="${stage}"]`)?.classList.add("active");
}

function highlight(text, query) {
  let safe = esc(text);
  const terms = [...new Set(String(query).split(/\s+/).filter((w) => w.length > 2))]
    .slice(0, 6)
    .map((w) => esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!terms.length) return safe;
  return safe.replace(new RegExp(`(${terms.join("|")})`, "gi"), "<mark>$1</mark>");
}

async function loadExamples() {
  const res = await fetch(`/api/examples?dataset=${$("dataset").value}`);
  const data = await res.json();
  examples = data.items;
  $("example").innerHTML = examples
    .map((ex) => `<option value="${ex.index}">#${ex.index} · ${esc(ex.question.slice(0, 110))}</option>`)
    .join("");
  selected = examples.length ? 0 : -1;
  if (selected >= 0) $("question").value = examples[selected].question;
  dirty = false;
}

function syncRetriever() {
  const needs = ["react", "focused"].includes($("agent").value) && $("dataset").value === "hotpotqa";
  $("retriever-label").style.display = needs ? "" : "none";
}

$("dataset").onchange = () => { syncRetriever(); loadExamples(); };
$("agent").onchange = syncRetriever;
$("example").onchange = () => {
  selected = Number($("example").value);
  $("question").value = examples[selected].question;
  dirty = false;
};
$("question").oninput = () => { dirty = true; };
$("random").onclick = () => {
  if (!examples.length) return;
  const i = Math.floor(Math.random() * examples.length);
  $("example").value = String(i);
  $("example").onchange();
  run();
};
$("run").onclick = run;

const counts = {};
function registerAction(tool, arg) {
  const key = `${tool}[${arg.trim().toLowerCase()}]`;
  counts[key] = (counts[key] || 0) + 1;
  if (counts[key] > 1) {
    const advice = $("agent").value === "focused"
      ? "Focused ReAct will stop after this and force an answer."
      : "Vanilla ReAct will keep going until max_steps.";
    $("loop").innerHTML = `⚠ <b>${esc(key)}</b> repeated ${counts[key]} times. ${advice}`;
    $("loop").className = "loop-hit";
    return counts[key];
  }
  return 0;
}

function route(event) {
  const steps = FLOWS[event.agent] || FLOWS.default;
  return steps.map((s, i) => `
    <span class="route-step" style="--i:${i}">${esc(s)}</span>
    ${i < steps.length - 1 ? '<span class="route-arrow" style="--i:' + (i + 0.5) + '">→</span>' : ""}
  `).join("");
}

function metaCard(event) {
  const agent = AGENTS[event.agent] || event.agent;
  const usesSearch = event.dataset === "hotpotqa" && ["react", "focused"].includes(event.agent);
  const tools = event.agent === "react" || event.agent === "focused"
    ? (event.dataset === "gsm8k" ? "Calculate" : "Search")
    : "none";
  const goldCount = (event.gold_titles || []).length;
  const chips = [
    `dataset: ${event.dataset}`,
    `agent: ${agent}`,
    `tools: ${tools}`,
    usesSearch ? `corpus: ${Number(event.corpus || 0).toLocaleString()} paragraphs` : "closed book",
    usesSearch && goldCount ? `gold: ${goldCount} supporting passage${goldCount > 1 ? "s" : ""}` : null,
    `model: ${event.model}`,
  ].filter(Boolean);
  return addCard("question meta-setup", `Run setup <span class="tokens">${esc(agent)}</span>`, `
    <div class="chips">${chips.map((c) => `<span>${esc(c)}</span>`).join("")}</div>
    <div class="route">${route(event)}</div>
    <div class="question-text">${esc(event.question)}</div>
    <div class="muted setup-note">${esc(BLURBS[event.agent] || "")}</div>
  `);
}

function addToolCard(tool, arg, repeats) {
  ctx.tools += 1;
  bump("stat-tools");
  const title = `Tool call #${ctx.tools} · ${esc(tool)}` +
    (repeats ? ` <span class="badge repeat">repeat #${repeats}</span>` : "");
  const status = tool === "Search"
    ? `searching ${ctx.corpus ? ctx.corpus.toLocaleString() : "the corpus"} paragraphs…`
    : "evaluating the expression…";
  const el = addCard("action tool-live", title, `
    <div class="console">
      <div class="console-bar"><i class="dot red"></i><i class="dot amber"></i><i class="dot green"></i>
        <span class="console-title">${esc(tool)}</span></div>
      <div class="console-line"><span class="chev">›</span><span class="cmd"></span></div>
      <div class="console-status"><span class="spinner"></span><span class="status-text">${esc(status)}</span></div>
    </div>`);
  return type(el.querySelector(".cmd"), `${tool}[${arg}]`, 500).then(() => el);
}

async function finishTool(card, event) {
  const hits = event.hits || [];
  const isSearch = event.tool === "Search";
  const sentK = Math.min(ctx.searchK || 3, hits.length);
  const status = card.querySelector(".console-status");

  const out = document.createElement("div");
  out.className = "tool-output";
  if (isSearch) {
    const max = Math.max(...hits.map((h) => Math.abs(Number(h.score) || 0)), 1e-9);
    const method = ctx.retriever === "dense" ? "cosine similarity" : "BM25";
    const goldSet = new Set((ctx.goldTitles || []).map((t) => String(t).toLowerCase()));
    status.innerHTML = `<span class="spinner"></span><span class="status-text">ranking ${hits.length} candidates…</span>`;
    out.innerHTML = `
      <div class="retrieval-head"><span>Top ${hits.length} candidates <span class="muted">· ${method}</span></span>
        <span class="muted">query: ${esc(event.argument)}</span></div>
      <div class="scan-progress"><i></i></div>
      <div class="cand-list">${hits.map((h, i) => `
        <div class="cand" data-i="${i}">
          <span class="cursor">▶</span>
          <span class="cand-rank">${i + 1}</span>
          <div class="cand-main">
            <div class="cand-top">
              <span class="cand-title">${highlight(h.title, event.argument)}</span>
              <span class="cand-badges"></span>
              <span class="cand-score">${h.score}</span>
            </div>
            <div class="cand-snippet">${highlight(h.snippet, event.argument)}</div>
            <div class="cand-bar"><i style="--w:${Math.min(100, (Math.abs(Number(h.score) || 0) / max) * 100).toFixed(1)}%"></i></div>
          </div>
        </div>`).join("")}</div>
      <div class="retrieval-summary muted">Scanning ${hits.length} candidates…</div>`;
    card.appendChild(out);

    const rows = [...out.querySelectorAll(".cand")];
    const list = out.querySelector(".cand-list");
    const progress = out.querySelector(".scan-progress i");
    await wait(250);
    for (let i = 0; i < rows.length; i++) {
      rows[i].classList.add("scanning", "scanned");
      progress.style.width = `${((i + 1) / rows.length) * 100}%`;
      const top = rows[i].getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
      list.scrollTop = Math.max(0, top - 36);
      await wait(110);
      rows[i].classList.remove("scanning");
    }
    await wait(150);
    list.scrollTop = 0;
    await wait(150);

    for (let i = 0; i < sentK; i++) {
      rows[i].classList.add("sent");
      rows[i].querySelector(".cand-badges").insertAdjacentHTML("beforeend", '<span class="badge sent-badge">sent</span>');
      await wait(80);
    }

    const goldRanks = [];
    let gold10 = 0;
    let goldTop = 0;
    for (let i = 0; i < rows.length; i++) {
      if (!goldSet.has(String(hits[i].title).toLowerCase())) continue;
      rows[i].classList.add("gold");
      rows[i].querySelector(".cand-badges").insertAdjacentHTML("beforeend", '<span class="badge gold-badge">gold</span>');
      gold10 += 1;
      goldRanks.push(i + 1);
      if (i < sentK) goldTop += 1;
      await wait(90);
    }

    const totalGold = (ctx.goldTitles || []).length;
    const missing = (ctx.goldTitles || []).filter(
      (t) => !hits.some((h) => String(h.title).toLowerCase() === String(t).toLowerCase()));
    let summary;
    if (totalGold) {
      summary = `Gold supporting passages: <b>${gold10}/${totalGold}</b> in the top ${hits.length}` +
        (goldRanks.length ? ` (ranks ${goldRanks.join(", ")})` : "") +
        ` · <b>${goldTop}/${totalGold}</b> in the ${sentK} sent.`;
      if (missing.length) summary += ` <span class="miss">Not retrieved: ${esc(missing.join(", "))}</span>`;
    } else {
      summary = "Custom question: no gold supporting titles to check.";
    }
    out.querySelector(".retrieval-summary").innerHTML = summary +
      ' <span class="legend">gold = official supporting passage · sent = passed to Qwen</span>';

    status.innerHTML = `<span class="check">✓</span><span class="status-text">${
      hits.length} candidates · top ${sentK} sent</span>`;
    ctx.cands += hits.length;
    ctx.hits += sentK;
    bump("stat-cand", hits.length);
    bump("stat-hits", sentK);
  } else {
    const err = String(event.text).startsWith("Error:");
    status.innerHTML = `<span class="check">✓</span><span class="status-text">result returned</span>`;
    out.innerHTML = `<div class="calc ${err ? "bad" : ""}">${esc(event.argument)} <span class="eq">=</span>
      <b>${esc(event.text)}</b></div>`;
    card.appendChild(out);
  }
  card.classList.add("done");
}

async function present(event) {
  pulse(event.kind);
  switch (event.kind) {
    case "loading":
      addCard("meta loading", "Loading", `
        <div class="load-row"><span class="spinner dark"></span><span>${esc(event.text)}</span></div>`);
      break;

    case "meta": {
      const timer = ctx.timer;
      const start = ctx.start || performance.now();
      ctx = {
        corpus: Number(event.corpus || 0), tools: 0, hits: 0, cands: 0, llm: 0,
        promptCard: null, pendingTool: null, start, finished: false, forced: false, timer,
        retriever: event.retriever, goldTitles: event.gold_titles || [],
        searchK: Number(event.search_k || 3),
      };
      trace.innerHTML = "";
      $("scratch").innerHTML = event.agent === "react" || event.agent === "focused"
        ? '<span class="muted">Empty. Thought / Action / Observation will appear here.</span>'
        : '<span class="muted">This agent has no scratchpad: one call, then an answer.</span>';
      metaCard(event);
      await wait(400);
      break;
    }

    case "prompt": {
      ctx.llm += 1;
      const forced = ctx.forced;
      ctx.forced = false;
      ctx.promptCard = addCard("prompt" + (forced ? " forced" : ""),
        `LLM call #${ctx.llm}${forced ? ' <span class="badge forced">forced answer</span>' : ""} <span class="tokens">prompt</span>`, `
        <div class="llm-status"><span class="pulse"></span> sending ${event.prompt.length.toLocaleString()} characters to Qwen…</div>
        <div class="muted meta-line">max_new_tokens=${event.max_new_tokens ?? "?"}${
          event.stop ? ` · stop=${esc(JSON.stringify(event.stop))}` : ""}</div>
        <details><summary>show the full prompt</summary><pre>${esc(event.prompt)}</pre></details>`);
      await wait(350);
      break;
    }

    case "completion": {
      if (ctx.promptCard) {
        const st = ctx.promptCard.querySelector(".llm-status");
        st.innerHTML = `<span class="check">✓</span> answered in ${event.latency_s}s · ${event.input_tokens} in / ${event.output_tokens} out`;
        ctx.promptCard.classList.add("answered");
      }
      bump("stat-steps");
      bump("stat-in", event.input_tokens);
      bump("stat-out", event.output_tokens);
      $("stat-time").textContent = `${(Number.parseFloat($("stat-time").textContent) + event.latency_s).toFixed(1)} s`;
      const card = addCard("completion", `Model output <span class="tokens">${event.output_tokens} tok · ${event.latency_s}s</span>`,
        `<div class="body typed"></div>`);
      await type(card.querySelector(".typed"), event.text || "(empty)");
      await wait(180);
      break;
    }

    case "thought": {
      bump("stat-think", event.tokens);
      const card = addCard("thought", `Thought <span class="tokens">${event.tokens} tok</span>`,
        `<div class="body typed"></div>`);
      await type(card.querySelector(".typed"), event.text);
      await wait(200);
      scratchLine("t", "Thought", event.text);
      break;
    }

    case "action": {
      if (event.tool === "Finish") break;  // shown by the finish card
      const repeats = registerAction(event.tool, event.argument);
      ctx.pendingTool = await addToolCard(event.tool, event.argument, repeats);
      await wait(450);
      scratchLine("a", "Action", `${event.tool}[${event.argument}]`);
      break;
    }

    case "tool_result": {
      const card = ctx.pendingTool || await addToolCard(event.tool, event.argument, 0);
      await finishTool(card, event);
      ctx.pendingTool = null;
      await wait(200);
      break;
    }

    case "invalid_action": {
      const card = addCard("warn", "No valid action", `<div class="body typed"></div>`);
      await type(card.querySelector(".typed"), event.text);
      await wait(250);
      break;
    }

    case "observation": {
      bump("stat-obs", event.tokens);
      addCard("observation", `Observation <span class="tokens">${event.tokens} tok</span>`, `
        <div class="obs-line"><span class="arrow">↳</span> returned to the model and appended to the scratchpad</div>
        <details><summary>show the exact text</summary><pre>${esc(event.text)}</pre></details>`);
      await wait(300);
      scratchLine("o", "Observation", event.text);
      break;
    }

    case "stop": {
      const why = event.reason === "max_steps" ? "Step budget reached" : "Repeated action detected";
      ctx.forced = true;
      addCard("warn stop-banner", "Early stop", `
        <div class="stop-row"><span class="stop-icon">■</span>
          <div><b>${esc(why)}</b>
            <div class="muted">reason: ${esc(event.reason)} · the agent now gets one forced final call.</div></div></div>`);
      await wait(500);
      break;
    }

    case "finish": {
      const failed = event.reason === "parse_error";
      const missing = !event.prediction;
      const card = addCard(failed || missing ? "warn final" : "finish final", "Final answer", `
        <div class="final-answer ${failed || missing ? "bad" : ""}">${esc(event.prediction || "(none)")}</div>
        <div class="muted">stop reason: ${esc(event.reason)}${
          failed ? " · the forced call did not produce Finish[...], the fallback answer is scored" : ""}</div>`);
      card.classList.add("stamped");
      if (event.prediction) scratchLine("f", "Finish", event.prediction);
      await wait(450);
      break;
    }

    case "result": {
      $("stat-steps").textContent = event.steps;
      $("stat-in").textContent = event.input_tokens;
      $("stat-out").textContent = event.output_tokens;
      $("stat-think").textContent = event.thinking_tokens;
      $("stat-obs").textContent = event.observation_tokens;
      $("stat-time").textContent = `${event.latency_s} s`;
      const ok = event.correct;
      clearInterval(ctx.timer);
      addCard("result-card " + (ok ? "good" : "bad"), "Result", `
        <div class="stamp ${ok ? "ok" : "bad"}">${ok ? "✓ Correct" : "✗ Incorrect"}</div>
        <div class="result-grid">
          <div><span class="k">Prediction</span><b>${esc(event.prediction || "(none)")}</b></div>
          <div><span class="k">Gold</span><b>${esc(event.gold || "(custom question)")}</b></div>
          <div><span class="k">Stop reason</span><b>${esc(event.stop_reason)}</b></div>
          <div><span class="k">LLM calls</span><b>${event.steps}</b></div>
          <div><span class="k">Tokens in / out</span><b>${event.input_tokens} / ${event.output_tokens}</b></div>
          <div><span class="k">Agent run</span><b>${event.latency_s} s</b></div>
          ${event.f1 !== undefined ? `<div><span class="k">Token F1</span><b>${event.f1}</b></div>` : ""}
          ${ctx.cands ? `<div><span class="k">Candidates / sent</span><b>${ctx.cands} / ${ctx.hits}</b></div>` : ""}
        </div>`);
      const verdict = $("verdict");
      verdict.textContent = ok ? "✓ Correct" : "✗ Incorrect";
      verdict.className = `verdict ${ok ? "ok" : "bad"}`;
      const wall = ((performance.now() - (ctx.start || performance.now())) / 1000).toFixed(1);
      $("status").textContent = `Done · ${wall}s replay`;
      await wait(250);
      break;
    }

    case "error":
      addCard("error", "Error", `<div class="body">${esc(event.text)}</div>`);
      break;
  }
}

function scratchLine(kind, label, text) {
  const box = $("scratch");
  if (box.querySelector(".muted")) box.innerHTML = "";
  const line = document.createElement("div");
  line.className = "line";
  line.innerHTML = `<span class="${kind}">${label}:</span> ${esc(text)}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

async function run() {
  if (running) return;
  running = true;
  $("run").disabled = true;
  $("status").textContent = "Running…";
  $("scratch").innerHTML = '<span class="muted">Waiting for the first call…</span>';
  $("loop").textContent = "No repeated action yet.";
  $("loop").className = "muted";
  $("verdict").textContent = "";
  $("verdict").className = "verdict";
  ["stat-steps", "stat-in", "stat-out", "stat-think", "stat-obs", "stat-tools", "stat-cand", "stat-hits"].forEach((id) => {
    if ($(id)) $(id).textContent = "0";
  });
  $("stat-time").textContent = "0.0 s";
  Object.keys(counts).forEach((k) => delete counts[k]);
  trace.innerHTML = '<p class="placeholder">Starting the agent…</p>';
  ctx = { start: performance.now() };

  const started = performance.now();
  const timer = setInterval(() => {
    if (running) $("status").textContent = `Running · ${((performance.now() - started) / 1000).toFixed(1)} s`;
  }, 200);
  ctx.timer = timer;

  const body = {
    dataset: $("dataset").value,
    agent: $("agent").value,
    retriever: $("retriever").value,
    model: "qwen",
    index: dirty ? -1 : selected,
    question: $("question").value,
  };
  try {
    const res = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.kind === "done") {
          clearInterval(timer);
          if (!ctx.finished) $("status").textContent = "Done";
          continue;
        }
        if (event.kind === "result") ctx.finished = true;
        await present(event);
      }
    }
  } catch (err) {
    addCard("error", "Error", `<div class="body">${esc(err.message)}</div>`);
    $("status").textContent = "Failed";
  } finally {
    clearInterval(timer);
    if ($("status").textContent.startsWith("Running")) $("status").textContent = "Done";
    running = false;
    $("run").disabled = false;
  }
}

syncRetriever();
loadExamples();
