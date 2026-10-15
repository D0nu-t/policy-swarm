"use strict";

// Opinion-space editor: the dimensions, the violator rule, and how the policy
// position is obtained (keyword rules applied to the policy text, or set by
// hand). Uses the $ and el helpers from app.js. The editor keeps its own model
// (`space`); typing writes straight into it, and the tables are only rebuilt
// on structural changes so focus is not lost while editing.

const SpaceEditor = (() => {
  const BLANK = {
    dimensions: [
      { name: "dimension_1", description: "", ideology_sensitivity: 0, tightening: 0 },
      { name: "dimension_2", description: "", ideology_sensitivity: 0, tightening: 0 },
    ],
    violator_dimension: "dimension_1", violator_threshold: 0.6, keywords: [],
    position: { dimension_1: 0, dimension_2: 0 },
  };
  let presets = {};
  let space = null;       // { dimensions[], violator_dimension, violator_threshold, keywords[], mode }

  /** Copy a server-side description into the editor model. */
  function load(description) {
    const copy = JSON.parse(JSON.stringify(description));
    space = {
      dimensions: copy.dimensions.map((d) => ({ ...d, position: copy.position ? copy.position[d.name] : 0 })),
      violator_dimension: copy.violator_dimension,
      violator_threshold: copy.violator_threshold,
      keywords: copy.keywords ?? [],
      mode: copy.position ? "hand" : "text",
    };
    render();
  }

  const names = () => space.dimensions.map((d) => d.name);

  function textCell(object, key, className = "") {
    const input = el("input", { type: "text", value: object[key] ?? "", autocomplete: "off" });
    input.addEventListener("input", () => { object[key] = input.value; });
    return { cell: el("td", { className }, input), input };
  }

  function numberCell(object, key, label) {
    const input = el("input", { type: "number", step: "any", value: String(object[key] ?? 0), ariaLabel: label });
    input.addEventListener("input", () => { object[key] = input.value; });
    return el("td", { className: "num" }, input);
  }

  function dimensionSelect(current, onChange, label) {
    const select = el("select", { ariaLabel: label },
                      ...names().map((n) => el("option", { value: n, textContent: n })));
    select.value = current;
    select.addEventListener("change", () => onChange(select.value));
    return select;
  }

  function removeButton(label, onClick) {
    const button = el("button", { type: "button", className: "remove", textContent: "Remove", ariaLabel: label });
    button.addEventListener("click", onClick);
    return el("td", {}, button);
  }

  function renameDimension(dimension, newName) {
    const old = dimension.name;
    dimension.name = newName.trim();
    if (space.violator_dimension === old) space.violator_dimension = dimension.name;
    for (const rule of space.keywords) if (rule.dimension === old) rule.dimension = dimension.name;
    render();
  }

  function removeDimension(index) {
    const [removed] = space.dimensions.splice(index, 1);
    space.keywords = space.keywords.filter((rule) => rule.dimension !== removed.name);
    if (space.violator_dimension === removed.name) space.violator_dimension = names()[0] ?? "";
    render();
  }

  function render() {
    $("space-editor").classList.toggle("hand", space.mode === "hand");
    for (const radio of document.querySelectorAll("input[name=space-mode]")) radio.checked = radio.value === space.mode;

    $("dim-table").tBodies[0].replaceChildren(...space.dimensions.map((dimension, index) => {
      const name = textCell(dimension, "name");
      name.input.ariaLabel = `Dimension ${index + 1} name`;
      // Other controls refer to dimensions by name, so re-render once the edit is finished.
      name.input.addEventListener("change", () => renameDimension(dimension, name.input.value));
      const description = textCell(dimension, "description", "wide");
      description.input.ariaLabel = `${dimension.name} description`;
      const positive = textCell(dimension, "positive_means", "wide");
      positive.input.ariaLabel = `${dimension.name}: what the positive end means`;
      const negative = textCell(dimension, "negative_means", "wide");
      negative.input.ariaLabel = `${dimension.name}: what the negative end means`;
      for (const cell of [positive, negative]) cell.input.addEventListener("change", renderEndsNote);
      const position = numberCell(dimension, "position", `${dimension.name} policy position`);
      position.classList.add("hand-only");
      return el("tr", {}, name.cell, description.cell, positive.cell, negative.cell,
                numberCell(dimension, "ideology_sensitivity", `${dimension.name} ideology sensitivity`),
                numberCell(dimension, "tightening", `${dimension.name} tightening`),
                position,
                removeButton(`Remove dimension ${dimension.name}`, () => removeDimension(index)));
    }));

    $("violator-dim").replaceChildren(...names().map((n) => el("option", { value: n, textContent: n })));
    $("violator-dim").value = space.violator_dimension;
    $("violator-threshold").value = space.violator_threshold;

    $("kw-table").tBodies[0].replaceChildren(...space.keywords.map((rule, index) => {
      const keyword = textCell(rule, "keyword");
      keyword.input.ariaLabel = `Rule ${index + 1} word or phrase`;
      // Rules proposed by the decision model keep a marker until a person edits or removes them.
      const note = el("td", {});
      if (rule.suggested) {
        note.append(el("span", {
          className: "tag", textContent: `suggested · p ${rule.confidence.toFixed(2)}`,
          title: "Proposed by the decision model. Check the dimension and delta.",
        }));
      }
      return el("tr", {}, keyword.cell,
                el("td", {}, dimensionSelect(rule.dimension, (value) => { rule.dimension = value; },
                                             `Rule ${index + 1} dimension`)),
                numberCell(rule, "delta", `Rule ${index + 1} delta`),
                removeButton(`Remove rule ${rule.keyword}`, () => { space.keywords.splice(index, 1); render(); }), note);
    }));
    $("preview-out").textContent = "";
    renderEndsNote();
  }

  /** Say which dimensions lack the two end descriptions the suggestion model relies on. */
  function renderEndsNote() {
    const missing = space.dimensions
      .filter((d) => !(d.positive_means ?? "").trim() || !(d.negative_means ?? "").trim())
      .map((d) => d.name);
    $("dim-ends-note").hidden = missing.length === 0;
    $("dim-ends-note").textContent = missing.length === 0 ? ""
      : `No end descriptions for: ${missing.join(", ")}. They are optional notes for readers and `
        + "do not affect the simulation, but a keyword rule's sign only makes sense once you "
        + "have decided which end is positive.";
  }

  function number(value, what) {
    const parsed = Number(value);
    if (String(value).trim() === "" || !Number.isFinite(parsed)) throw new Error(`Opinion space: ${what} is not a number`);
    return parsed;
  }

  /** The editor's content as the JSON the API expects. Throws on unparsable numbers. */
  function read() {
    const byHand = space.mode === "hand";
    return {
      dimensions: space.dimensions.map((d) => ({
        name: d.name.trim(),
        description: d.description ?? "",
        ...((d.positive_means ?? "").trim() ? { positive_means: d.positive_means.trim() } : {}),
        ...((d.negative_means ?? "").trim() ? { negative_means: d.negative_means.trim() } : {}),
        ideology_sensitivity: number(d.ideology_sensitivity, `${d.name} ideology sensitivity`),
        tightening: number(d.tightening, `${d.name} tightening`),
      })),
      violator_dimension: space.violator_dimension,
      violator_threshold: number(space.violator_threshold, "violator threshold"),
      keywords: byHand ? [] : space.keywords.map((rule) => ({
        keyword: rule.keyword, dimension: rule.dimension, delta: number(rule.delta, `delta of "${rule.keyword}"`),
      })),
      position: byHand
        ? Object.fromEntries(space.dimensions.map((d) => [d.name.trim(), number(d.position, `${d.name} position`)]))
        : null,
    };
  }

  async function preview() {
    const out = $("preview-out");
    let body;
    try {
      body = { policy_text: $("policy-text").value.trim() || null, opinion_space: read() };
    } catch (error) {
      out.textContent = error.message;
      return;
    }
    const response = await fetch("/api/policy/preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      out.textContent = typeof result.detail === "string" ? result.detail : "The opinion space was rejected";
      return;
    }
    const position = Object.entries(result.position)
      .map(([name, value]) => `${name} ${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`).join("   ");
    const matched = result.source === "policy text"
      ? `\nMatched: ${result.matched_keywords.join(", ") || "no keywords"}` : "\nSet by hand";
    out.textContent = position + matched;
  }

  // -------------------------------------------------------------------------
  // Suggest from text: topics as candidate dimensions, then keyword rules
  // -------------------------------------------------------------------------

  let topics = [];        // [{ name, terms, examples, in_text, keep }]

  async function post(url, body, status) {
    const response = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (response.ok) return result;
    status.textContent = typeof result.detail === "string" ? result.detail : "The request was rejected";
    return null;
  }

  function renderTopics() {
    $("sg-topic-list").replaceChildren(...topics.map((topic, index) => {
      const keep = el("input", { type: "checkbox", checked: topic.keep, ariaLabel: `Use topic ${index + 1}` });
      keep.addEventListener("change", () => { topic.keep = keep.checked; });
      const name = el("input", { type: "text", value: topic.name, autocomplete: "off",
                                 ariaLabel: `Name for topic ${index + 1}` });
      name.addEventListener("input", () => { topic.name = name.value; });
      return el("div", { className: "geo-card" },
                el("label", { className: "checks" }, keep, el("b", { textContent: `Topic ${index + 1}` })),
                name,
                el("p", { textContent: topic.terms.map((t) => t.term).join(", ") }),
                el("small", { className: "hint", textContent: topic.examples[0] ? `e.g. "${topic.examples[0]}"` : "" }));
    }));
    $("sg-use").hidden = topics.length === 0;
  }

  async function findTopics() {
    const status = $("sg-topics-status");
    status.textContent = "Finding topics...";
    const result = await post("/api/suggest/topics", {
      policy_text: $("policy-text").value.trim() || null,
      corpus_dir: $("sg-corpus").value.trim() || null,
      n_topics: Number($("sg-n").value),
    }, status);
    if (!result) return;
    topics = result.topics.map((topic) => ({ ...topic, keep: true }));
    status.textContent = `${topics.length} topics from ${result.units} sentences or passages.`;
    renderTopics();
  }

  function useTopics(replace) {
    const chosen = topics.filter((topic) => topic.keep).map((topic) => ({
      name: topic.name.trim(), description: `About: ${topic.terms.slice(0, 6).map((t) => t.term).join(", ")}.`,
      positive_means: "", negative_means: "",
      ideology_sensitivity: 0, tightening: 0, position: 0,
    }));
    if (chosen.length === 0) return;
    if (replace) {
      space.dimensions = chosen;
      space.keywords = [];
      space.violator_dimension = chosen[0].name;
    } else {
      space.dimensions.push(...chosen);
    }
    space.mode = "text";
    render();
    $("sg-topics-status").textContent = "Dimensions updated below. Rewrite each description to say what the dimension is about.";
  }

  async function suggestRules() {
    const status = $("sg-rules-status");
    let body;
    try {
      body = {
        policy_text: $("policy-text").value.trim() || null,
        opinion_space: { ...read(), keywords: space.keywords.filter((rule) => rule.keyword.trim() !== "")
          .map((rule) => ({ keyword: rule.keyword, dimension: rule.dimension, delta: number(rule.delta, "delta") })),
                         position: null },
        phrases: topics.length ? topics.filter((t) => t.keep).flatMap((t) => t.in_text) : null,
      };
    } catch (error) {
      status.textContent = error.message;
      return;
    }
    $("sg-rules").disabled = true;
    status.textContent = "Asking the decision model. This can take a minute or two on a CPU...";
    const result = await post("/api/suggest/keywords", body, status);
    $("sg-rules").disabled = false;
    if (!result) return;
    space.keywords.push(...result.rules.map((rule) => ({ ...rule, suggested: true })));
    space.mode = "text";
    render();
    const unsure = result.rules.filter((rule) => rule.low_confidence).length;
    status.textContent = `${result.rated} phrases rated, ${result.rules.length} rules suggested `
      + `(${result.rated - result.rules.length} judged unrelated; ${unsure} with a probability under 0.5). `
      + "They are marked in the keyword table below: check each one, then use Preview.";
  }

  function initSuggest(capability) {
    $("sg-topics").addEventListener("click", findTopics);
    $("sg-replace").addEventListener("click", () => useTopics(true));
    $("sg-append").addEventListener("click", () => useTopics(false));
    $("sg-rules").addEventListener("click", suggestRules);
    if (!capability.topics) {
      $("sg-topics").disabled = true;
      $("sg-topics-status").textContent = 'Needs scikit-learn: pip install -e ".[topics]"';
    }
    if (!capability.keywords) {
      $("sg-rules").disabled = true;
      $("sg-rules-status").textContent = 'Needs Laya: pip install -e ".[decision]"';
    }
  }

  function init(catalogue, capability) {
    initSuggest(capability);
    presets = { ...catalogue.presets, "Blank (two dimensions)": BLANK };
    $("space-preset").replaceChildren(...Object.keys(presets).map((name) => el("option", { value: name, textContent: name })));
    load(catalogue.default);

    $("space-custom").addEventListener("change", () => { $("space-editor").hidden = !$("space-custom").checked; });
    $("space-preset").addEventListener("change", () => load(presets[$("space-preset").value]));
    $("dim-add").addEventListener("click", () => {
      let n = space.dimensions.length + 1;
      while (names().includes(`dimension_${n}`)) n += 1;
      space.dimensions.push({ name: `dimension_${n}`, description: "", ideology_sensitivity: 0, tightening: 0, position: 0 });
      if (!space.violator_dimension) space.violator_dimension = `dimension_${n}`;
      render();
    });
    $("kw-add").addEventListener("click", () => {
      space.keywords.push({ keyword: "", dimension: names()[0] ?? "", delta: 0.2 });
      render();
    });
    $("violator-dim").addEventListener("change", () => { space.violator_dimension = $("violator-dim").value; });
    $("violator-threshold").addEventListener("input", () => { space.violator_threshold = $("violator-threshold").value; });
    for (const radio of document.querySelectorAll("input[name=space-mode]")) {
      radio.addEventListener("change", () => { space.mode = radio.value; render(); });
    }
    $("space-preview").addEventListener("click", preview);
  }

  return { init, read, isCustom: () => $("space-custom").checked };
})();
