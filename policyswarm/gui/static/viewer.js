"use strict";

// Simulation viewer, part 1 of 4: state, data access, playback and loading.
//
//   viewer.js         this file
//   viewer-views.js   where agents are placed: network, 2-D slice, 3-D, distance map
//   viewer-draw.js    canvas drawing: agents, conversations, timeline, histograms
//   viewer-panels.js  the text beside the pictures
//
// POST /api/simulate returns { shared, runs }: one run per geometry, all from
// the same seed. A run holds, per tick, the opinions after the tick, every
// conversation attempt as [listener, speaker, outcome, distance, moved], the
// shocks, how far each phase moved every agent, and distance measurements.
//
// Playback position is (tick, frac), shared by every run: tick -1 is the
// starting state and frac runs 0..1 through the phases of a tick. While paused
// frac is 1 and the pictures show a still summary of the tick.
//
// A "pane" is one picture: { run, kind: "net" | "space", canvas, layout }.
// With one geometry there are two panes (network and opinions); with several
// there is one pane per geometry, all of the same kind.
//
// Uses $, el, state, buildInput, readChanged and errorDetail from app.js.

const Viewer = (() => {
  const C = {
    BLOCKED: 0, FAR: 1, HEARD: 2, PENALISED: 3,
    TICK_SECONDS: 3.2,       // length of one tick at normal speed
    SPAN: 0.22,              // share of the conversation phase one exchange stays visible
    PHASES: ["shock", "media", "peer", "policy"],
    NEG: [74, 163, 255], MID: [214, 219, 226], POS: [255, 159, 67],
    INK: { heard: "61,220,151", far: "255,107,107", blocked: "125,133,144",
           violator: "255,77,109", policy: "255,209,102", media: "199,146,234",
           text: "201,209,217" },
    RUN_INK: ["138,180,255", "255,154,213", "214,230,133"],   // one per compared geometry
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const v = {
    description: null, inputs: {},
    shared: null, runs: [], focus: 0, panes: [],
    picture: "space",          // what every pane shows when several geometries are compared
    view: "slice",             // opinion picture: slice | cube | map
    dims: [0, 1, 2], colourBy: 0,
    rotation: { yaw: -0.6, pitch: 0.35 }, sphere: false, spin: false,
    tick: -1, frac: 1, playing: false, speed: 1, last: 0, timer: 0,
    selected: null, hover: null,
  };

  // -------------------------------------------------------------------------
  // Helpers shared by the other viewer files
  // -------------------------------------------------------------------------

  const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (t) => t * t * (3 - 2 * t);
  const easeOut = (t) => 1 - (1 - t) * (1 - t);
  const signed = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(2);
  const rgba = (ink, alpha) => `rgba(${ink},${alpha})`;
  const percent = (share) => `${Math.round((share ?? 0) * 100)}%`;

  function colourFor(value) {
    const [from, to, t] = value < 0 ? [C.MID, C.NEG, -value] : [C.MID, C.POS, value];
    const k = clamp(t);
    return `rgb(${from.map((c, i) => Math.round(lerp(c, to[i], k))).join(",")})`;
  }

  const focusRun = () => v.runs[v.focus];
  const opinionsAfter = (run, k) => (k < 0 ? v.shared.initial : run.ticks[k].opinions);
  const policyAt = (run, k) => (k < 0 ? v.shared.initial_policy : run.ticks[k].policy);
  const measureAt = (run, k) => (k < 0 ? run.initial_measure : run.ticks[k].measure);

  /** Opinion of agent i on dimension d at the current playback position. */
  function opinion(run, i, d) {
    if (v.tick < 0) return v.shared.initial[i][d];
    return lerp(opinionsAfter(run, v.tick - 1)[i][d], opinionsAfter(run, v.tick)[i][d], smooth(v.frac));
  }

  /** Start and end of each phase inside a tick, as fractions of the tick. */
  function phaseWindows(t) {
    const weight = {
      shock: t.shocks.length ? 1.2 : 0,
      media: t.moved.media ? 1 : 0,
      peer: t.conversations.length ? 6 : 0,
      policy: t.moved.policy ? 1.2 : 0,
    };
    const total = C.PHASES.reduce((sum, p) => sum + weight[p], 0) || 1;
    const windows = {};
    let start = 0;
    for (const phase of C.PHASES) {
      windows[phase] = [start, start + weight[phase] / total];
      start = windows[phase][1];
    }
    return windows;
  }

  /** Progress 0..1 through a phase window, or null when outside it. */
  function progress([from, to]) {
    if (to <= from || v.frac < from || v.frac >= to) return null;
    return (v.frac - from) / (to - from);
  }

  /** Whether the still picture and the log show this conversation. */
  function shown([listener, speaker, code]) {
    if (code === C.FAR && !$("v-show-far").checked) return false;
    if (code === C.BLOCKED && !$("v-show-blocked").checked) return false;
    if ($("v-only-agent").checked && v.selected !== null
        && listener !== v.selected && speaker !== v.selected) return false;
    return true;
  }

  // -------------------------------------------------------------------------
  // Playback
  // -------------------------------------------------------------------------

  const lastTick = () => v.shared.meta.n_ticks - 1;
  const draw = () => { if (v.shared) Viewer.drawAll(); };
  const animating = () => v.playing && !reducedMotion.matches;
  const drawIfIdle = () => { if (!animating() && !spinning()) draw(); };
  const spinning = () => v.spin && v.view === "cube" && !reducedMotion.matches
    && v.panes.some((pane) => pane.kind === "space");

  function pause() {
    v.playing = false;
    v.frac = 1;
    clearInterval(v.timer);
    $("v-play").textContent = "Play";
  }

  function show(tick) {
    pause();
    v.tick = clamp(tick, -1, lastTick());
    v.hover = null;
    Viewer.renderTick();
    draw();
  }

  /** Move to the next tick while playing. Returns false at the end of the run. */
  function advance() {
    if (v.tick >= lastTick()) return false;
    v.tick += 1;
    v.hover = null;
    Viewer.renderTick();
    return true;
  }

  /** One animation frame: advances playback and / or the 3-D spin. */
  function frame(now) {
    const elapsed = Math.min(now - v.last, 100) / 1000;
    v.last = now;
    if (animating()) {
      v.frac += elapsed * (v.speed / C.TICK_SECONDS);
      if (v.frac >= 1) {
        if (advance()) v.frac = Math.min(v.frac - 1, 0.5);
        else pause();
      }
    }
    if (spinning()) v.rotation.yaw += elapsed * 0.25;
    draw();
    if (animating() || spinning()) requestAnimationFrame(frame);
    else v.looping = false;
  }

  function startLoop() {
    if (v.looping) return;
    v.looping = true;
    v.last = performance.now();
    requestAnimationFrame(frame);
  }

  function play() {
    if (v.tick >= lastTick()) v.tick = -1;       // replay from the start
    v.playing = true;
    $("v-play").textContent = "Pause";
    if (reducedMotion.matches) {       // no motion: step through still summaries
      v.timer = setInterval(() => { if (!advance()) pause(); draw(); }, 900 / v.speed);
      return;
    }
    advance();
    v.frac = 0;
    startLoop();
  }

  function select(agent) {
    v.selected = agent === v.selected ? null : agent;
    Viewer.renderTick();
    drawIfIdle();
  }

  function focus(index) {
    if (index === v.focus) return;
    v.focus = index;
    for (const pane of v.panes) pane.figure.classList.toggle("focused", pane.run.index === index);
    Viewer.renderRules();
    Viewer.renderTick();
    drawIfIdle();
  }

  // -------------------------------------------------------------------------
  // Panes
  // -------------------------------------------------------------------------

  /** Click an agent to follow it; click empty space to stop following. */
  function pick(pane, event) {
    const box = pane.canvas.getBoundingClientRect();
    const [x, y] = [event.clientX - box.left, event.clientY - box.top];
    const { P, R } = pane.layout;
    let best = null, bestDistance = Infinity;
    P.forEach(([px, py], i) => {
      const distance = Math.hypot(px - x, py - y) - R[i];
      if (distance < bestDistance) { best = i; bestDistance = distance; }
    });
    if (bestDistance <= 8) select(best);
    else if (v.selected !== null) select(v.selected);
  }

  function makePane(run, kind, title) {
    const canvas = el("canvas", { className: "stage", role: "img" });
    canvas.setAttribute("aria-label", `${title}: ${kind === "net" ? "network of agents" : "agents by opinion"}`);
    const stats = el("span", { className: "hint" });
    const note = el("p", { className: "hint note" });
    const caption = el("figcaption", {}, el("b", { textContent: title }), stats);
    if (v.runs.length > 1) {
      const swatch = el("i", { className: "swatch" });
      swatch.style.background = rgba(C.RUN_INK[run.index], 1);
      caption.prepend(swatch);
    }
    const figure = el("figure", { className: "pane" }, caption, canvas, note);
    figure.classList.toggle("focused", v.runs.length > 1 && run.index === v.focus);
    const pane = { run, kind, canvas, figure, stats, note, layout: { P: [], R: [] } };

    // A drag rotates the 3-D view; a press without movement is a click.
    let drag = null;
    canvas.addEventListener("pointerdown", (event) => {
      drag = { x: event.clientX, y: event.clientY, moved: false };
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!drag || kind !== "space" || v.view !== "cube") return;
      const [dx, dy] = [event.clientX - drag.x, event.clientY - drag.y];
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      drag.moved = true;
      v.rotation.yaw += dx * 0.01;
      v.rotation.pitch = clamp(v.rotation.pitch + dy * 0.01, -1.5, 1.5);
      [drag.x, drag.y] = [event.clientX, event.clientY];
      drawIfIdle();
    });
    canvas.addEventListener("pointerup", (event) => {
      const wasDrag = drag && drag.moved;
      drag = null;
      if (wasDrag) return;
      focus(run.index);
      pick(pane, event);
    });
    return pane;
  }

  function buildPanes() {
    const single = v.runs.length === 1;
    v.panes = single
      ? [makePane(v.runs[0], "net", "Who talks to whom"), makePane(v.runs[0], "space", "Where opinions sit")]
      : v.runs.map((run) => makePane(run, v.picture, run.label));
    $("v-panes").replaceChildren(...v.panes.map((pane) => pane.figure));
    $("v-picture").hidden = single;
    syncControls();
  }

  /** Show only the controls that apply to the pictures on screen. */
  function syncControls() {
    const hasSpace = v.panes.some((pane) => pane.kind === "space");
    const dimensions = v.shared.meta.dimensions.length;
    for (const button of $("v-view").children) {
      button.setAttribute("aria-pressed", String(button.dataset.value === v.view));
      button.disabled = button.dataset.value === "cube" && dimensions < 3;
    }
    for (const button of $("v-picture").children) {
      button.setAttribute("aria-pressed", String(button.dataset.value === v.picture));
    }
    $("v-view").hidden = !hasSpace;
    $("v-dims").hidden = !hasSpace || v.view === "map";
    $("v-z-wrap").hidden = v.view !== "cube";
    $("v-sphere-wrap").hidden = !hasSpace || v.view !== "cube" || !v.runs.some((run) => run.angular);
    $("v-spin-wrap").hidden = !hasSpace || v.view !== "cube" || reducedMotion.matches;
    $("v-view-hint").textContent = !hasSpace
      ? "The social network. Agents can only talk along these links; bigger agents have more of them."
      : Viewer.VIEW_HINTS[v.view];
    if (spinning()) startLoop();
  }

  // -------------------------------------------------------------------------
  // Loading a trace
  // -------------------------------------------------------------------------

  function load(response) {
    pause();
    v.shared = response.shared;
    v.runs = response.runs.map((run, index) => {
      const counts = run.ticks.map((t) => {
        const count = [0, 0, 0, 0];
        for (const exchange of t.conversations) count[exchange[2]] += 1;
        count[C.HEARD] += count[C.PENALISED];        // a penalised speaker is still heard
        return count;
      });
      let heard = 0, allowed = 0;
      const heardSoFar = counts.map((count) => {     // share of allowed attempts heard, up to each tick
        heard += count[C.HEARD];
        allowed += count[C.HEARD] + count[C.FAR];
        return allowed ? heard / allowed : 0;
      });
      return { ...run, index, counts, heardSoFar };
    });
    Object.assign(v, { focus: 0, selected: null, hover: null, tick: -1 });

    const names = v.shared.meta.dimensions;
    const options = () => names.map((name, d) => el("option", { value: String(d), textContent: name }));
    $("v-colour").replaceChildren(...options(), el("option", { value: "ideology", textContent: "ideology (fixed)" }));
    v.colourBy = 0;
    v.dims = [0, 1, Math.min(2, names.length - 1)];
    ["v-x", "v-y", "v-z"].forEach((id, axis) => {
      $(id).replaceChildren(...options());
      $(id).value = String(v.dims[axis]);
    });
    if (v.view === "cube" && names.length < 3) v.view = "slice";
    $("v-scrub").max = v.shared.meta.n_ticks;

    $("viewer-stage").hidden = false;
    buildPanes();
    Viewer.buildHistograms();
    Viewer.renderRules();
    Viewer.renderTick();
    draw();
  }

  function fail(message) {
    $("viewer-error").textContent = message || "";
    $("viewer-error").hidden = !message;
  }

  async function simulate() {
    fail("");
    let request;
    try {
      request = {
        params: readChanged(v.description.params, v.inputs),
        sim_config: readChanged(state.catalogue.sim_config, state.simInputs),
        policy_text: $("policy-text").value.trim() || null,
        opinion_space: SpaceEditor.isCustom() ? SpaceEditor.read() : null,
      };
    } catch (error) {
      fail(error.message);
      return;
    }
    $("viewer-run").disabled = true;
    $("viewer-status").textContent = "Simulating...";
    try {
      const response = await fetch("/api/simulate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
      });
      const body = await response.json();
      if (!response.ok) {
        fail(errorDetail(body));
        $("viewer-status").textContent = "";
        return;
      }
      load(body);
      const attempts = body.runs[0].ticks.reduce((sum, t) => sum + t.conversations.length, 0);
      const meta = body.shared.meta;
      $("viewer-status").textContent = `${meta.n_agents} agents, ${meta.n_ticks} ticks, `
        + `${attempts.toLocaleString()} conversation attempts`
        + (body.runs.length > 1 ? ` in each of ${body.runs.length} geometries.` : ".");
    } catch (error) {
      fail(`Could not run the simulation: ${error.message}`);
      $("viewer-status").textContent = "";
    } finally {
      $("viewer-run").disabled = false;
    }
  }

  function segmented(id, onChoose) {
    for (const button of $(id).children) {
      button.addEventListener("click", () => { onChoose(button.dataset.value); });
    }
  }

  function init(description) {
    v.description = description;
    for (const spec of description.params) {
      v.inputs[spec.name] = buildInput(spec);
      $("viewer-params").append(v.inputs[spec.name].node);
    }
    Viewer.renderGeometryCards(description.geometries);

    $("viewer-run").addEventListener("click", simulate);
    $("v-play").addEventListener("click", () => {
      if (v.playing) { pause(); draw(); } else play();
    });
    $("v-prev").addEventListener("click", () => show(v.tick - 1));
    $("v-next").addEventListener("click", () => show(v.tick + 1));
    $("v-scrub").addEventListener("input", () => show(Number($("v-scrub").value) - 1));
    $("v-speed").addEventListener("change", () => {
      v.speed = Number($("v-speed").value);
      if (v.playing && reducedMotion.matches) { pause(); play(); }
    });
    $("v-colour").addEventListener("change", () => {
      const value = $("v-colour").value;
      v.colourBy = value === "ideology" ? value : Number(value);
      drawIfIdle();
    });
    ["v-x", "v-y", "v-z"].forEach((id, axis) => {
      $(id).addEventListener("change", () => { v.dims[axis] = Number($(id).value); drawIfIdle(); });
    });
    segmented("v-view", (value) => { v.view = value; syncControls(); drawIfIdle(); });
    segmented("v-picture", (value) => { v.picture = value; buildPanes(); draw(); });
    $("v-sphere").addEventListener("change", () => { v.sphere = $("v-sphere").checked; drawIfIdle(); });
    $("v-spin").addEventListener("change", () => {
      v.spin = $("v-spin").checked;
      if (spinning()) startLoop();
    });
    for (const id of ["v-show-far", "v-show-blocked", "v-only-agent"]) {
      $(id).addEventListener("change", () => { Viewer.renderTick(); drawIfIdle(); });
    }
    $("v-timeline").addEventListener("click", (event) => {
      const box = $("v-timeline").getBoundingClientRect();
      const share = (event.clientX - box.left - Viewer.TIMELINE_PAD) / (box.width - 2 * Viewer.TIMELINE_PAD);
      show(Math.floor(clamp(share, 0, 0.9999) * v.shared.meta.n_ticks));
    });
    new ResizeObserver(drawIfIdle).observe($("v-panes"));
  }

  return {
    init, v, C, reducedMotion,
    clamp, lerp, smooth, easeOut, signed, rgba, percent, colourFor,
    focusRun, opinionsAfter, policyAt, measureAt, opinion, phaseWindows, progress, shown,
    select, drawIfIdle,
  };
})();
