"use strict";

// Simulation viewer, part 4 of 4: the text beside the pictures.
// With several geometries, the log, agent details and rules describe the
// focused run (the picture last clicked).

(() => {
  const { v, C, signed, percent, colourFor, focusRun, opinionsAfter, policyAt, measureAt,
          phaseWindows, progress, shown, select, drawIfIdle } = Viewer;
  const { BLOCKED, FAR, HEARD, PENALISED } = C;

  const movedCount = (moved) => (moved ? moved.filter((m) => m > 0.0005).length : 0);
  const movedMost = (moved) => (moved ? Math.max(...moved) : 0).toFixed(3);
  const list = (lines) => lines.map((text) => el("li", { textContent: text }));

  /** One card per geometry in the Scenario section: what it measures, in words. */
  Viewer.renderGeometryCards = (geometries) => {
    $("viewer-geometries").replaceChildren(...geometries.map((g) =>
      el("div", { className: "geo-card" },
         el("b", { textContent: g.label }),
         el("p", { textContent: g.summary }),
         el("dl", {},
            el("dt", { textContent: "Distance" }), el("dd", { textContent: g.distance }),
            el("dt", { textContent: "A listener who hears a speaker" }), el("dd", { textContent: g.step }),
            el("dt", { textContent: "The threshold" }), el("dd", { textContent: g.epsilon })))));
  };

  function eventLines(run) {
    const meta = v.shared.meta;
    if (v.tick < 0) {
      return ["Starting state: opinions are spread at random and nobody has spoken yet. "
              + "Press Play, or step forward one tick at a time."];
    }
    const t = run.ticks[v.tick];
    const lines = [];
    if (v.tick === meta.policy_split_tick) lines.push("The policy tightens this tick (its marker moves).");
    if (v.tick === meta.policy_pull_onset) lines.push("From this tick agents are also pulled toward their own reading of the policy.");
    if (v.tick === meta.enforcement_lag) {
      lines.push(`Enforcement starts: a violating speaker now loses ${percent(meta.penalty_severity)} of its influence.`);
    }
    for (const shock of t.shocks) {
      lines.push(`Shock (${shock.mode}, strength ${shock.strength.toFixed(2)}) hits ${shock.targets.length} `
                 + `${shock.type === "hub" ? "of the best-connected" : "random"} agents.`);
    }
    if (t.moved.media) lines.push(`Media moves ${movedCount(t.moved.media)} agents (largest move ${movedMost(t.moved.media)}).`);
    const count = run.counts[v.tick];
    const penalised = count[PENALISED] ? ` (${count[PENALISED]} from a penalised speaker)` : "";
    lines.push(`${t.conversations.length} conversation attempts: ${count[BLOCKED]} blocked, `
               + `${count[FAR]} ignored, ${count[HEARD]} heard${penalised}.`);
    if (t.moved.policy) lines.push(`The policy pull moves ${movedCount(t.moved.policy)} agents (largest move ${movedMost(t.moved.policy)}).`);
    return lines;
  }

  function describeExchange(run, [listener, speaker, code, distance, moved]) {
    const eps = run.epsilon.toFixed(2);
    if (code === BLOCKED) return [`#${listener} could not hear #${speaker}`, "blocked by the deployment cap", "blocked"];
    if (code === FAR) {
      const gap = distance === null ? "no defined distance (one of them is exactly neutral)"
        : `distance ${distance.toFixed(2)} is over ε ${eps}`;
      return [`#${listener} ignored #${speaker}`, gap, "far"];
    }
    const detail = `distance ${distance.toFixed(2)} within ε ${eps} · #${listener} moved ${moved.toFixed(3)}`;
    if (code === PENALISED) {
      return [`#${listener} heard #${speaker} (a violator, influence cut)`, detail, "penalised"];
    }
    return [`#${listener} heard #${speaker}`, detail, "heard"];
  }

  function renderLog(run) {
    const n = v.shared.meta.n_ticks;
    const which = v.runs.length > 1 ? ` (${run.label})` : "";
    $("v-tick").textContent = v.tick < 0 ? `Start · ${n} ticks` : `Tick ${v.tick} of ${n - 1}`;
    $("v-log-title").textContent = v.tick < 0 ? "Before the first tick" : `What happened in tick ${v.tick}${which}`;
    $("v-events").replaceChildren(...list(eventLines(run)));
    $("v-scrub").value = v.tick + 1;

    const rows = v.tick < 0 ? [] : run.ticks[v.tick].conversations.filter(shown).map((exchange) => {
      const [title, detail, className] = describeExchange(run, exchange);
      const row = el("li", { className, tabIndex: 0 },
                     el("div", {}, title, el("small", { className: "hint", textContent: detail })));
      const pair = [exchange[0], exchange[1]];
      const setHover = (value) => { v.hover = value; drawIfIdle(); };
      row.addEventListener("mouseenter", () => setHover(pair));
      row.addEventListener("focus", () => setHover(pair));
      row.addEventListener("mouseleave", () => setHover(null));
      row.addEventListener("blur", () => setHover(null));
      row.addEventListener("click", () => select(exchange[0]));
      return row;
    });
    $("v-log").replaceChildren(...rows);
    $("v-log").hidden = rows.length === 0;
  }

  function renderAgent(run) {
    const { agents, meta } = v.shared;
    const s = v.selected;
    const which = v.runs.length > 1 ? ` (${run.label})` : "";
    $("v-agent-title").textContent = s === null ? "Agent" : `Agent #${s}${which}`;
    if (s === null) {
      $("v-agent").className = "hint";
      $("v-agent").replaceChildren("Click an agent in any picture to follow it.");
      return;
    }
    const now = opinionsAfter(run, v.tick)[s];
    const policy = policyAt(run, v.tick);
    const bars = el("div", { className: "agent-bars" });
    meta.dimensions.forEach((name, d) => {
      const fill = el("i");
      fill.style.left = `${50 + Math.min(now[d], 0) * 50}%`;
      fill.style.width = `${Math.abs(now[d]) * 50}%`;
      fill.style.background = colourFor(now[d]);
      const mark = el("b", { title: "policy" });
      mark.style.left = `${50 + policy[d] * 50}%`;
      bars.append(el("span", { textContent: name }), el("div", { className: "track" }, fill, mark),
                  el("span", { textContent: signed(now[d]) }));
    });
    const violator = now[meta.violator_dimension] > meta.violator_threshold;
    const facts = [
      `${agents.degree[s]} connections, influence ${agents.influence[s].toFixed(2)}`,
      `ideology ${signed(agents.ideology[s])} (pulled by ${agents.ideology[s] > 0 ? "pro" : "anti"}-policy media), `
        + `trust ${agents.trust[s].toFixed(2)}`,
      violator ? "currently a violator" : "not a violator",
    ];
    if (v.tick >= 0) {
      const t = run.ticks[v.tick];
      const part = (name, key) => `${name} ${(t.moved[key] ? t.moved[key][s] : 0).toFixed(3)}`;
      const asListener = t.conversations.filter((c) => c[0] === s);
      const heard = asListener.filter((c) => c[2] >= HEARD).length;
      const spoke = t.conversations.filter((c) => c[1] === s && c[2] >= HEARD).length;
      facts.push(`this tick it listened ${asListener.length} time(s), heard ${heard}, and was heard by ${spoke}`);
      facts.push(`moved by: ${[part("shock", "shock"), part("media", "media"),
                               part("conversations", "peer"), part("policy", "policy")].join(" · ")}`);
    }
    $("v-agent").className = "";
    $("v-agent").replaceChildren(bars, el("ul", { className: "events" }, ...list(facts)));
  }

  /** The line of numbers beside each picture's title. */
  function renderPaneStats() {
    for (const pane of v.panes) {
      const run = pane.run;
      if (v.runs.length === 1 && pane.kind === "net") {
        pane.stats.textContent = "the social network; bigger = more connected";
        continue;
      }
      const heard = v.tick < 0 ? "" : ` · ${percent(run.heardSoFar[v.tick])} of allowed attempts heard so far`;
      pane.stats.textContent = `${v.runs.length === 1 ? `${run.label} · ` : ""}ε ${run.epsilon.toFixed(2)} · `
        + `${percent(measureAt(run, v.tick).coverage)} of neighbours in range${heard}`;
    }
  }

  Viewer.renderTick = () => {
    const run = focusRun();
    renderLog(run);
    renderAgent(run);
    renderPaneStats();
  };

  Viewer.renderRules = () => {
    const m = v.shared.meta;
    const run = focusRun();
    const geometry = v.description.geometries.find((g) => g.key === run.geometry);
    const matched = run.matched_coverage === null ? ""
      : ` ε was set so that ${percent(run.matched_coverage)} of neighbour pairs start within it, the same share in every geometry.`;
    const rules = [
      `Each tick, ${m.interactions} times, a random agent (the listener) picks one of its network neighbours at random (the speaker).`,
      `The attempt goes ahead with probability ${m.deployment_rate_cap} (the deployment cap). Otherwise it is blocked.`,
      `If their ${run.label} distance over all ${m.dimensions.length} dimensions is more than ε = ${run.epsilon.toFixed(2)}, the listener ignores the speaker.${matched}`,
      `Otherwise the listener is influenced, by μ = ${m.mu} times the speaker's influence, so well-connected speakers pull harder. ${geometry.step} The speaker does not move.`,
      `From tick ${m.enforcement_lag}, a speaker who is a violator (${m.dimensions[m.violator_dimension]} above ${m.violator_threshold}) has its influence cut by ${percent(m.penalty_severity)}.`,
    ];
    const total = run.counts.reduce((sum, c) => sum + c[HEARD], 0);
    const penalised = run.counts.reduce((sum, c) => sum + c[PENALISED], 0);
    rules.push(`In this run ${percent(run.gate_pass_rate)} of the attempts that went ahead were heard: `
               + `${total} in all, ${penalised} of them from a penalised speaker.`);
    $("v-rules-title").textContent = v.runs.length > 1 ? `How agents converse (${run.label})` : "How agents converse";
    $("v-rules").replaceChildren(...list(rules));
    $("v-focus-hint").hidden = v.runs.length === 1;
  };

  Viewer.renderPhases = () => {
    const windows = v.tick < 0 ? null : phaseWindows(focusRun().ticks[v.tick]);
    for (const item of $("v-phases").children) {
      const span = windows ? windows[item.dataset.phase] : [0, 0];
      item.classList.toggle("happens", span[1] > span[0]);
      item.classList.toggle("active", v.frac < 1 && progress(span) !== null);
    }
  };
})();
