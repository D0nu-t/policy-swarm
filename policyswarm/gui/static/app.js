"use strict";

// PolicySwarm dashboard front end.
// Forms are generated from GET /api/experiments, so adding a ParamSpec to an
// experiment class is enough to make it editable here. All run output is
// inserted with textContent, never as HTML.

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};

const state = {
  catalogue: null,        // response of /api/experiments
  classToName: {},        // "EnforcementLagExperiment" -> "lag"
  inputs: {},             // experiment name -> { param name -> reader }
  simInputs: {},          // SimConfig field -> reader
  runId: null,
  source: null,           // EventSource
};

// ---------------------------------------------------------------------------
// Parameter inputs. Each builder returns { node, read() } where read() gives
// the JSON value or throws an Error with a message for the user.
// ---------------------------------------------------------------------------

function parseNumber(text, spec) {
  const value = Number(text);
  if (text.trim() === "" || !Number.isFinite(value)) throw new Error(`${spec.name}: "${text}" is not a number`);
  if (spec.kind === "int" && !Number.isInteger(value)) throw new Error(`${spec.name}: ${text} is not a whole number`);
  return value;
}

function checkboxGroup(spec, options, selected) {
  const boxes = options.map(([value, label]) => {
    const box = el("input", { type: "checkbox", checked: selected.includes(value) });
    return { value, box, label: el("label", {}, box, label) };
  });
  const node = el("fieldset", {}, el("legend", { textContent: spec.name }),
                  el("div", { className: "checks" }, ...boxes.map((b) => b.label)));
  return {
    node,
    read() {
      const chosen = boxes.filter((b) => b.box.checked).map((b) => b.value);
      if (chosen.length === 0) throw new Error(`${spec.name}: select at least one`);
      return chosen;
    },
  };
}

function buildInput(spec) {
  let control;
  if (spec.many && spec.kind === "choice") {
    control = checkboxGroup(spec, spec.choices.map((c) => [c, c]), spec.default);
  } else if (spec.many && spec.kind === "bool") {
    control = checkboxGroup(spec, [[true, "on"], [false, "off"]], spec.default);
  } else if (spec.many) {
    const input = el("input", { type: "text", value: spec.default.join(", "), autocomplete: "off" });
    control = {
      node: el("label", { className: "param" }, el("span", { textContent: spec.name }), input),
      read() {
        const parts = input.value.split(",").map((s) => s.trim()).filter((s) => s !== "");
        if (parts.length === 0) throw new Error(`${spec.name}: enter at least one value`);
        return parts.map((p) => parseNumber(p, spec));
      },
    };
  } else if (spec.kind === "choice") {
    const select = el("select", {}, ...spec.choices.map((c) => el("option", { value: c, textContent: c })));
    select.value = spec.default;
    control = { node: el("label", { className: "param" }, el("span", { textContent: spec.name }), select),
                read: () => select.value };
  } else if (spec.kind === "bool") {
    const box = el("input", { type: "checkbox", checked: spec.default });
    control = { node: el("label", { className: "checks" }, box, spec.name), read: () => box.checked };
  } else {
    const input = el("input", { type: "number", step: spec.kind === "int" ? "1" : "any",
                                value: spec.default === null ? "" : String(spec.default) });
    if (spec.minimum !== null) input.min = spec.minimum;
    if (spec.maximum !== null) input.max = spec.maximum;
    control = {
      node: el("label", { className: "param" }, el("span", { textContent: spec.name }), input),
      read() {
        if (input.value.trim() === "") {
          if (spec.optional) return null;
          throw new Error(`${spec.name}: a value is required`);
        }
        return parseNumber(input.value, spec);
      },
    };
  }
  if (spec.help) control.node.append(el("small", { textContent: spec.help }));
  return control;
}

/** Read every input; keep only values that differ from the declared default. */
function readChanged(specs, readers) {
  const changed = {};
  for (const spec of specs) {
    const value = readers[spec.name].read();
    if (JSON.stringify(value) !== JSON.stringify(spec.default)) changed[spec.name] = value;
  }
  return changed;
}

// ---------------------------------------------------------------------------
// Setup form
// ---------------------------------------------------------------------------

function renderSetup(catalogue) {
  for (const exp of catalogue.experiments) {
    state.classToName[exp.class] = exp.name;
    state.inputs[exp.name] = {};
    const box = el("input", { type: "checkbox", value: exp.name });
    const params = el("div", { className: "params" });
    for (const spec of exp.params) {
      const control = buildInput(spec);
      state.inputs[exp.name][spec.name] = control;
      params.append(control.node);
    }
    const card = el("div", { className: "card" }, el("label", {}, box, exp.title), params);
    box.addEventListener("change", () => card.classList.toggle("selected", box.checked));
    card.dataset.name = exp.name;
    $("experiments").append(card);
  }
  for (const spec of catalogue.sim_config) {
    const control = buildInput(spec);
    state.simInputs[spec.name] = control;
    $("sim-config").append(control.node);
  }
}

function parseSeeds(text) {
  const seeds = [];
  for (const part of text.split(",").map((s) => s.trim()).filter(Boolean)) {
    const range = part.match(/^(\d+)\s*-\s*(\d+)$/);
    if (range) {
      const [lo, hi] = [Number(range[1]), Number(range[2])];
      if (hi < lo) throw new Error(`Seeds: "${part}" runs backwards`);
      for (let s = lo; s <= hi; s++) seeds.push(s);
    } else if (/^\d+$/.test(part)) {
      seeds.push(Number(part));
    } else {
      throw new Error(`Seeds: "${part}" is not a seed or a range`);
    }
  }
  if (seeds.length === 0) throw new Error("Seeds: enter at least one seed");
  if (new Set(seeds).size !== seeds.length) throw new Error("Seeds: the same seed appears twice");
  return seeds;
}

function buildRequest() {
  const selected = [...document.querySelectorAll("#experiments input[type=checkbox][value]")]
    .filter((box) => box.checked).map((box) => box.value);
  if (selected.length === 0) throw new Error("Select at least one experiment");
  const params = {};
  for (const exp of state.catalogue.experiments.filter((e) => selected.includes(e.name))) {
    const changed = readChanged(exp.params, state.inputs[exp.name]);
    if (Object.keys(changed).length > 0) params[exp.name] = changed;
  }
  return {
    experiments: selected,
    seeds: parseSeeds($("seeds").value),
    policy_text: $("policy-text").value.trim() || null,
    sim_config: readChanged(state.catalogue.sim_config, state.simInputs),
    params,
    opinion_space: SpaceEditor.isCustom() ? SpaceEditor.read() : null,
  };
}

function showError(message) {
  $("error").textContent = message || "";
  $("error").hidden = !message;
}

function errorDetail(body) {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("\n");
  return "The request was rejected";
}

// ---------------------------------------------------------------------------
// Running
// ---------------------------------------------------------------------------

function setStatus(status) {
  $("status").textContent = status;
  $("status").className = `badge ${status}`;
  const running = status === "running";
  $("run").disabled = running;
  $("cancel").hidden = !running;
}

function barRow(name) {
  let row = document.querySelector(`.bar-row[data-name="${name}"]`);
  if (!row) {
    const title = state.catalogue.experiments.find((e) => e.name === name)?.title ?? name;
    row = el("div", { className: "bar-row" },
             el("span", { textContent: title }),
             el("div", { className: "bar", role: "progressbar", ariaLabel: title }, el("i")),
             el("span", { className: "count", textContent: "waiting" }));
    row.dataset.name = name;
    $("bars").append(row);
  }
  return row;
}

function setProgress(name, completed, total) {
  const row = barRow(name);
  row.querySelector("i").style.width = `${total ? (100 * completed) / total : 0}%`;
  row.querySelector(".count").textContent = `${completed} / ${total}`;
  const bar = row.querySelector(".bar");
  bar.ariaValueNow = completed; bar.ariaValueMin = 0; bar.ariaValueMax = total;
}

function handleEvent(event) {
  const name = state.classToName[event.experiment] ?? event.experiment;
  if (event.type === "start") setProgress(name, 0, event.total);
  else if (event.type === "seed_complete") setProgress(name, event.completed, event.total);
  else if (event.type === "complete") barRow(name).classList.add("done");
  else if (event.type === "error") {
    const row = barRow(name);
    row.classList.add("error");
    row.querySelector(".count").textContent = "failed";
  }
}

function appendLog(line) {
  const log = $("log");
  const pinned = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
  log.append(line + "\n");
  if (pinned) log.scrollTop = log.scrollHeight;
}

function follow(run) {
  state.runId = run.id;
  $("progress").hidden = false;
  $("results").hidden = true;
  $("bars").replaceChildren();
  $("log").replaceChildren();
  $("result-list").replaceChildren();
  run.spec.experiments.forEach(barRow);
  setStatus(run.status);

  state.source?.close();
  state.source = new EventSource(`/api/runs/${run.id}/events`);
  state.source.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.kind === "event") handleEvent(data.event);
    else if (data.kind === "log") appendLog(data.line);
    else if (data.kind === "status") {
      setStatus(data.status);
      if (data.status !== "running") {
        state.source.close();      // the stream is complete; do not auto-reconnect
        loadResults(run.id);
      }
    }
  };
}

async function startRun() {
  showError("");
  let request;
  try {
    request = buildRequest();
  } catch (error) {
    showError(error.message);
    return;
  }
  const response = await fetch("/api/runs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
  });
  const body = await response.json();
  if (!response.ok) {
    showError(errorDetail(body));
    return;
  }
  follow(body);
}

async function cancelRun() {
  if (state.runId) await fetch(`/api/runs/${state.runId}/cancel`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

function formatCell(value) {
  if (value === null) return "–";
  if (typeof value !== "number" || Number.isInteger(value)) return String(value);
  const magnitude = Math.abs(value);
  return magnitude !== 0 && (magnitude < 1e-4 || magnitude >= 1e6) ? value.toExponential(2) : value.toFixed(5);
}

function renderResult(result) {
  const title = state.catalogue.experiments.find((e) => e.name === result.name)?.title ?? result.name;
  const node = el("div", { className: "result" }, el("h3", { textContent: title }));
  if (result.stats) {
    const head = el("tr", {}, ...result.stats.columns.map((c) => el("th", { textContent: c, scope: "col" })));
    const rows = result.stats.rows.map((r) => el("tr", {}, ...r.map((v) => el("td", { textContent: formatCell(v) }))));
    node.append(el("div", { className: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows))));
  } else {
    node.append(el("p", { className: "hint", textContent: "No results were written for this experiment." }));
  }
  if (result.figures.length > 0) {
    node.append(el("div", { className: "figures" }, ...result.figures.map((url) =>
      el("a", { href: url, target: "_blank", rel: "noopener" },
         el("img", { src: url, loading: "lazy", alt: `${title}: ${url.split("/").pop()}` })))));
  }
  if (result.files.length > 0) {
    node.append(el("div", { className: "files" }, ...result.files.map((url) =>
      el("a", { href: url, textContent: url.split("/").pop(), download: "" }))));
  }
  return node;
}

async function loadResults(runId) {
  const response = await fetch(`/api/runs/${runId}/results`);
  if (!response.ok) return;
  const results = await response.json();
  $("result-list").replaceChildren(...results.experiments.map(renderResult));
  $("results").hidden = false;
}

// ---------------------------------------------------------------------------
// Start-up
// ---------------------------------------------------------------------------

async function init() {
  state.catalogue = await (await fetch("/api/experiments")).json();
  renderSetup(state.catalogue);
  SpaceEditor.init(state.catalogue.opinion_space, state.catalogue.suggest);
  Viewer.init(state.catalogue.viewer);
  $("policy-text").placeholder = state.catalogue.default_policy_text.trim().slice(0, 400) + " ...";
  $("run").addEventListener("click", startRun);
  $("cancel").addEventListener("click", cancelRun);

  // Re-attach after a page reload: follow the newest run of this server session.
  const runs = await (await fetch("/api/runs")).json();
  if (runs.length > 0) follow(runs[runs.length - 1]);
}

init().catch((error) => showError(`Could not load the dashboard: ${error.message}`));
