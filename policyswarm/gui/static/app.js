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

/** The label a person sees: the server's label, or the field name made readable. */
function labelOf(spec) {
  if (spec.label) return spec.label;
  const words = spec.name.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function parseNumber(text, spec) {
  const value = Number(text);
  if (text.trim() === "" || !Number.isFinite(value)) throw new Error(`${labelOf(spec)}: "${text}" is not a number`);
  if (spec.kind === "int" && !Number.isInteger(value)) throw new Error(`${labelOf(spec)}: ${text} is not a whole number`);
  return value;
}

/** Mark a field as wrong next to where it is, and move focus to it. */
function markInvalid(field, message) {
  if (!field) return;
  field.classList.add("invalid");
  field.setAttribute("aria-invalid", "true");
  let note = field.parentElement.querySelector(".field-error");
  if (!note) {
    note = el("span", { className: "field-error", role: "alert" });
    field.insertAdjacentElement("afterend", note);
  }
  note.textContent = message;
  field.focus({ preventScroll: false });
  const clear = () => {
    field.classList.remove("invalid");
    field.removeAttribute("aria-invalid");
    note.remove();
    field.removeEventListener("input", clear);
  };
  field.addEventListener("input", clear);
}

function checkboxGroup(spec, options, selected) {
  const boxes = options.map(([value, label]) => {
    const box = el("input", { type: "checkbox", checked: selected.includes(value) });
    return { value, box, label: el("label", {}, box, label) };
  });
  const node = el("fieldset", {}, el("legend", { textContent: labelOf(spec) }),
                  el("div", { className: "checks" }, ...boxes.map((b) => b.label)));
  return {
    node,
    read() {
      const chosen = boxes.filter((b) => b.box.checked).map((b) => b.value);
      if (chosen.length === 0) throw new Error(`${labelOf(spec)}: select at least one`);
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
      node: el("label", { className: "param" }, el("span", { textContent: labelOf(spec) }), input),
      field: input,
      read() {
        const parts = input.value.split(",").map((s) => s.trim()).filter((s) => s !== "");
        if (parts.length === 0) throw new Error(`${labelOf(spec)}: enter at least one value`);
        return parts.map((p) => parseNumber(p, spec));
      },
    };
  } else if (spec.kind === "choice") {
    const select = el("select", {}, ...spec.choices.map((c) => el("option", { value: c, textContent: c })));
    select.value = spec.default;
    control = { node: el("label", { className: "param" }, el("span", { textContent: labelOf(spec) }), select),
                field: select, read: () => select.value };
  } else if (spec.kind === "bool") {
    const box = el("input", { type: "checkbox", checked: spec.default });
    control = { node: el("label", { className: "checks" }, box, labelOf(spec)), read: () => box.checked };
  } else {
    const input = el("input", { type: "number", step: spec.kind === "int" ? "1" : "any",
                                value: spec.default === null ? "" : String(spec.default) });
    if (spec.minimum !== null) input.min = spec.minimum;
    if (spec.maximum !== null) input.max = spec.maximum;
    control = {
      node: el("label", { className: "param" }, el("span", { textContent: labelOf(spec) }), input),
      field: input,
      read() {
        if (input.value.trim() === "") {
          if (spec.optional) return null;
          throw new Error(`${labelOf(spec)}: a value is required`);
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
    let value;
    try {
      value = readers[spec.name].read();
    } catch (error) {
      const reader = readers[spec.name];
      reader.node.closest("details")?.setAttribute("open", "");
      markInvalid(reader.field, error.message);
      throw error;
    }
    if (JSON.stringify(value) !== JSON.stringify(spec.default)) changed[spec.name] = value;
  }
  return changed;
}

const HIDDEN_GROUP = "Hidden choices";
const HIDDEN_NOTE = "Choices that can create or hide an effect without anyone noticing "
  + "(see the methods note). The defaults are the audited model; change one at a time.";

/** Render specs into labelled groups; the hidden choices get their own, marked box. */
function renderGroups(specs, container, readers) {
  const groups = new Map();
  for (const spec of specs) {
    const name = spec.group || "Settings";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(spec);
  }
  const named = groups.size > 1;
  for (const [name, list] of groups) {
    const grid = el("div", { className: "grid" });
    for (const spec of list) {
      readers[spec.name] = buildInput(spec);
      grid.append(readers[spec.name].node);
    }
    if (!named) { container.append(grid); continue; }
    const wide = name === HIDDEN_GROUP || list.length > 6;      // many fields: use the full width
    const box = el("fieldset", { className: `group${wide ? " wide" : ""}${name === HIDDEN_GROUP ? " hidden-choices" : ""}` },
                   el("legend", { textContent: name }));
    if (name === HIDDEN_GROUP) box.append(el("p", { className: "hint", textContent: HIDDEN_NOTE }));
    box.append(grid);
    container.append(box);
  }
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
  renderGroups(catalogue.sim_config, $("sim-config"), state.simInputs);
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
  $("results-empty").hidden = true;
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
  const button = $("run");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  $("estimate").textContent = "Starting…";
  try {
    const response = await fetch("/api/runs", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
    });
    const body = await response.json();
    if (!response.ok) {
      showError(errorDetail(body));
      button.disabled = false;
      return;
    }
    $("estimate").textContent = "";
    follow(body);
    location.hash = "#results";
  } catch (error) {
    showError(`Could not start the run: ${error.message}`);
    button.disabled = false;
  } finally {
    button.removeAttribute("aria-busy");
    if ($("estimate").textContent === "Starting…") $("estimate").textContent = "";
  }
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

const CHOICE_TEXT = {
  gate_space: "Gate measured from", policy_pull: "Policy pull", trust_anchor: "Low trust perceives",
};

function percentText(x) { return `${Math.round(100 * x)}%`; }
/** Two significant figures, so very small effects are not shown as 0.000. */
function sig(x) { return Number.isFinite(x) ? Number(x.toPrecision(2)).toString() : "–"; }

function renderAudit(audit) {
  const box = $("audit");
  const parts = [el("h3", { textContent: "Hidden-choices check" }),
                 el("p", { className: "hint", textContent: "Read from this run's own files. "
                   + "It lists the choices that can create or hide an effect, and the test that "
                   + "actually compares geometries." })];
  parts.push(el("ul", { className: "choice-list" }, ...audit.choices.map((c) =>
    el("li", {}, el("span", { textContent: `${CHOICE_TEXT[c.name] ?? c.name}: ` }),
       el("b", { textContent: c.value }),
       el("span", { className: c.default ? "tag ok" : "tag", textContent: c.default ? "default" : "changed" })))));
  for (const exp of audit.experiments) {
    const title = state.catalogue.experiments.find((e) => e.name === exp.name)?.title ?? exp.name;
    const section = el("div", { className: "audit-exp" }, el("h4", { textContent: title }));
    if (exp.geometries.length) {
      const rows = exp.geometries.map((g) => el("tr", {},
        el("th", { scope: "row", textContent: g.geometry }),
        el("td", { textContent: g.epsilon === null ? "–" : g.epsilon.toFixed(3) }),
        el("td", { textContent: g.pass_rate === null ? "–" : percentText(g.pass_rate) })));
      section.append(el("div", { className: "table-wrap" }, el("table", {},
        el("caption", { className: "sr-only", textContent: `${title}: threshold and realised pass rate by geometry` }),
        el("thead", {}, el("tr", {}, el("th", { scope: "col", textContent: "Geometry" }),
          el("th", { scope: "col", textContent: "ε" }), el("th", { scope: "col", textContent: "Realised pass rate" }))),
        el("tbody", {}, ...rows))));
    }
    if (exp.interaction) {
      const i = exp.interaction;
      const cells = i.cells ? ` Single cells marked significant: ${i.cells.significant} of ${i.cells.total}; `
        + "those test each cell against zero and do not compare the geometries." : "";
      section.append(el("p", { textContent:
        `Geometry × lag interaction (${i.pair}, relative effect): ${sig(i.estimate)} `
        + `[95% CI ${sig(i.ci_low)}, ${sig(i.ci_high)}], p = ${i.p_value.toPrecision(2)}. `
        + "This is the test that compares the geometries." + cells }));
    }
    parts.push(section);
  }
  if (audit.warnings.length) {
    parts.push(el("ul", { className: "warnings" }, ...audit.warnings.map((w) =>
      el("li", {}, el("b", { textContent: "Check: " }), w))));
  } else {
    parts.push(el("p", { className: "hint", textContent: "No warnings for this run." }));
  }
  box.replaceChildren(...parts);
  box.hidden = false;
}

async function loadResults(runId) {
  const response = await fetch(`/api/runs/${runId}/results`);
  if (!response.ok) return;
  const results = await response.json();
  $("result-list").replaceChildren(...results.experiments.map(renderResult));
  $("results").hidden = false;
  const audit = await fetch(`/api/runs/${runId}/audit`);
  if (audit.ok) renderAudit(await audit.json());
}

// ---------------------------------------------------------------------------
// Views (top navigation; the URL hash names the view, so it can be linked)
// ---------------------------------------------------------------------------

const VIEWS = ["run", "watch", "explorer", "results"];

function showView() {
  const name = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "run";
  for (const view of VIEWS) $(`view-${view}`).hidden = view !== name;
  for (const link of document.querySelectorAll("nav a")) {
    if (link.hash === `#${name}`) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (name === "explorer" && typeof Explorer !== "undefined") Explorer.show();
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
  window.addEventListener("hashchange", showView);
  showView();
  $("run").addEventListener("click", startRun);
  $("cancel").addEventListener("click", cancelRun);

  // Re-attach after a page reload: follow the newest run of this server session.
  const runs = await (await fetch("/api/runs")).json();
  if (runs.length > 0) follow(runs[runs.length - 1]);
}

init().catch((error) => showError(`Could not load the dashboard: ${error.message}`));
