"use strict";

// Simulation viewer, part 3 of 4: canvas drawing.
// Agents and this tick's conversations on every pane, the timeline, and the
// neighbour-distance histograms. Positions come from Viewer.project.

(() => {
  const { v, C, clamp, lerp, easeOut, rgba, percent, colourFor, focusRun, opinion, measureAt,
          phaseWindows, progress, shown } = Viewer;
  const { BLOCKED, FAR, HEARD, PENALISED, INK } = C;

  Viewer.TIMELINE_PAD = 10;

  function fit(canvas) {
    const box = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const [w, h] = [Math.round(box.width * ratio), Math.round(box.height * ratio)];
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, box.width, box.height);
    return { ctx, w: box.width, h: box.height };
  }

  function ring(ctx, [x, y], radius, colour, width = 1.5) {
    ctx.beginPath();
    ctx.arc(x, y, Math.max(radius, 0.1), 0, 2 * Math.PI);
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function segment(ctx, a, b, colour, width, dash = []) {
    ctx.beginPath();
    ctx.setLineDash(dash);
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  const along = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];

  function arrowHead(ctx, from, to, inset, colour) {
    const angle = Math.atan2(to[1] - from[1], to[0] - from[0]);
    const tip = [to[0] - Math.cos(angle) * inset, to[1] - Math.sin(angle) * inset];
    ctx.beginPath();
    ctx.moveTo(tip[0], tip[1]);
    ctx.lineTo(tip[0] - 7 * Math.cos(angle - 0.4), tip[1] - 7 * Math.sin(angle - 0.4));
    ctx.lineTo(tip[0] - 7 * Math.cos(angle + 0.4), tip[1] - 7 * Math.sin(angle + 0.4));
    ctx.closePath();
    ctx.fillStyle = colour;
    ctx.fill();
  }

  function label(ctx, text, [x, y], colour, align = "left") {
    ctx.font = "600 11px system-ui, sans-serif";
    ctx.textAlign = align;
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(13,17,23,.85)";
    ctx.strokeText(text, x, y);
    ctx.fillStyle = colour;
    ctx.fillText(text, x, y);
  }

  // -------------------------------------------------------------------------
  // What happens during a tick
  // -------------------------------------------------------------------------

  /** Broadcast phases: a pulse on every agent the phase moved. */
  function drawPulses(ctx, P, R, moved, p, ink) {
    if (!moved || p === null) return;
    for (let i = 0; i < moved.length; i++) {
      if (moved[i] <= 0) continue;
      const strength = clamp(moved[i] * 60, 0.15, 1);
      ring(ctx, P[i], R[i] + 2 + 9 * p, rgba(ink, (1 - p) * strength), 1.5);
    }
  }

  function drawShocks(ctx, P, R, t, p) {
    if (p === null) return;
    for (const shock of t.shocks) {
      for (const target of shock.targets) {
        ring(ctx, P[target], R[target] + 26 * easeOut(p), rgba("255,255,255", 1 - p), 2.5);
        ring(ctx, P[target], R[target] + 12 * easeOut(p), rgba("255,255,255", (1 - p) * 0.6), 1);
      }
    }
  }

  /** One exchange in flight, speaker a to listener b: q runs 0..1 over its lifetime. */
  function drawExchange(ctx, a, b, code, q, listenerRadius, speakerRadius) {
    if (code === BLOCKED) {
      const reach = along(a, b, 0.16 * easeOut(clamp(q * 2)));
      segment(ctx, a, reach, rgba(INK.blocked, (1 - q) * 0.9), 1.5, [2, 3]);
      return;
    }
    if (code === FAR) {
      const reach = along(a, b, 0.5 * easeOut(clamp(q / 0.6)));
      const fade = q < 0.6 ? 0.9 : 0.9 * (1 - (q - 0.6) / 0.4);
      segment(ctx, a, reach, rgba(INK.far, fade), 1.4, [4, 4]);
      if (q >= 0.6) {            // the message dies half way: a small cross
        const [x, y] = reach;
        segment(ctx, [x - 4, y - 4], [x + 4, y + 4], rgba(INK.far, fade), 2);
        segment(ctx, [x - 4, y + 4], [x + 4, y - 4], rgba(INK.far, fade), 2);
      }
      return;
    }
    const head = along(a, b, easeOut(clamp(q / 0.75)));
    const fade = q < 0.75 ? 1 : 1 - (q - 0.75) / 0.25;
    const gradient = ctx.createLinearGradient(a[0], a[1], head[0], head[1]);
    gradient.addColorStop(0, rgba(INK.heard, 0));
    gradient.addColorStop(1, rgba(INK.heard, 0.9 * fade));
    segment(ctx, a, head, gradient, 2.2);
    ctx.beginPath();
    ctx.arc(head[0], head[1], 3.2, 0, 2 * Math.PI);
    ctx.fillStyle = rgba("220,255,240", fade);
    ctx.fill();
    if (q >= 0.75) ring(ctx, b, listenerRadius + 12 * (1 - fade), rgba(INK.heard, fade), 2);
    if (code === PENALISED) ring(ctx, a, speakerRadius + 5, rgba(INK.violator, fade), 2);
  }

  /** Still summary: a conversation as an arrow from speaker to listener. */
  function drawExchangeStill(ctx, a, b, code, listenerRadius) {
    if (code === BLOCKED) {
      segment(ctx, a, b, rgba(INK.blocked, 0.28), 1, [1, 4]);
    } else if (code === FAR) {
      segment(ctx, a, b, rgba(INK.far, 0.38), 1, [4, 4]);
    } else {
      segment(ctx, a, b, rgba(INK.heard, 0.7), 1.6);
      arrowHead(ctx, a, b, listenerRadius + 1, rgba(INK.heard, 0.95));
    }
  }

  function drawConversations(ctx, P, R, t, windows) {
    const list = t.conversations;
    const animated = v.frac < 1;
    const p = animated ? progress(windows.peer) : 1;
    if (p === null) return;
    ctx.save();
    ctx.lineCap = "round";
    if (animated) ctx.globalCompositeOperation = "lighter";
    for (let c = 0; c < list.length; c++) {
      const [listener, speaker, code] = list[c];
      const [a, b] = [P[speaker], P[listener]];
      if (animated) {
        const q = (p - (c / list.length) * (1 - C.SPAN)) / C.SPAN;
        if (q > 0 && q < 1) drawExchange(ctx, a, b, code, q, R[listener], R[speaker]);
      } else if (shown(list[c])) {
        drawExchangeStill(ctx, a, b, code, R[listener]);
      }
    }
    ctx.restore();
  }

  function drawEffects(ctx, run, P, R) {
    if (v.tick < 0) return;
    const t = run.ticks[v.tick];
    const windows = phaseWindows(t);
    if (v.frac < 1) {
      drawShocks(ctx, P, R, t, progress(windows.shock));
      drawPulses(ctx, P, R, t.moved.media, progress(windows.media), INK.media);
      drawPulses(ctx, P, R, t.moved.policy, progress(windows.policy), INK.policy);
    }
    drawConversations(ctx, P, R, t, windows);
  }

  function drawAgents(ctx, run, { P, R, order, alpha }) {
    const { agents, meta } = v.shared;
    const sequence = order ?? P.map((_, i) => i);
    for (const i of sequence) {
      const value = v.colourBy === "ideology" ? agents.ideology[i] : opinion(run, i, v.colourBy);
      ctx.globalAlpha = alpha ? alpha[i] : 1;
      ctx.beginPath();
      ctx.arc(P[i][0], P[i][1], R[i], 0, 2 * Math.PI);
      ctx.fillStyle = colourFor(value);
      ctx.fill();
      if (opinion(run, i, meta.violator_dimension) > meta.violator_threshold) {
        ring(ctx, P[i], R[i] + 1.5, rgba(INK.violator, 0.95), 1.6);
      }
    }
    ctx.globalAlpha = 1;
    if (v.hover) {
      const [listener, speaker] = v.hover;
      segment(ctx, P[speaker], P[listener], "rgba(255,255,255,.9)", 2.2);
      arrowHead(ctx, P[speaker], P[listener], R[listener] + 2, "#fff");
      ring(ctx, P[speaker], R[speaker] + 4, "#fff", 2);
      ring(ctx, P[listener], R[listener] + 4, "#fff", 2);
      label(ctx, `speaker #${speaker}`, [P[speaker][0] + R[speaker] + 7, P[speaker][1] - 6], "#fff");
      label(ctx, `listener #${listener}`, [P[listener][0] + R[listener] + 7, P[listener][1] + 14], "#fff");
    }
    if (v.selected !== null) {
      const s = v.selected;
      ring(ctx, P[s], R[s] + 4, "#fff", 2);
      if (!v.hover) label(ctx, `#${s}`, [P[s][0] + R[s] + 7, P[s][1] + 4], "#fff");
    }
  }

  function drawPane(pane) {
    const { ctx, w, h } = fit(pane.canvas);
    const layout = Viewer.project(pane, w, h);
    pane.layout = layout;
    layout.before(ctx);
    drawEffects(ctx, pane.run, layout.P, layout.R);
    drawAgents(ctx, pane.run, layout);
    layout.after(ctx);
    if (pane.note.textContent !== layout.note) pane.note.textContent = layout.note;
  }

  // -------------------------------------------------------------------------
  // Timeline: conversation outcomes per tick (bars) and opinion variance (lines)
  // -------------------------------------------------------------------------

  function drawTimeline() {
    const { ctx, w, h } = fit($("v-timeline"));
    const meta = v.shared.meta;
    const n = meta.n_ticks;
    const pad = Viewer.TIMELINE_PAD;
    const x = (position) => pad + (position / n) * (w - 2 * pad);
    const slot = (w - 2 * pad) / n;
    const focused = focusRun();
    const most = Math.max(1, ...focused.counts.map((c) => c[BLOCKED] + c[FAR] + c[HEARD]));

    focused.counts.forEach((count, k) => {
      let y = h - 6;
      for (const [code, ink] of [[HEARD, INK.heard], [FAR, INK.far], [BLOCKED, INK.blocked]]) {
        const height = (count[code] / most) * h * 0.42;
        ctx.fillStyle = rgba(ink, k === v.tick ? 1 : 0.5);
        ctx.fillRect(x(k) + 0.5, y - height, Math.max(slot - 1, 1), height);
        y -= height;
      }
    });

    const marks = [
      [meta.policy_split_tick, INK.policy, "policy tightens"],
      [meta.policy_pull_onset, INK.media, "pull starts"],
      [meta.enforcement_lag, INK.violator, "enforcement starts"],
    ].filter(([tick]) => tick < n);
    marks.forEach(([tick, ink, text], row) => {
      segment(ctx, [x(tick), 4], [x(tick), h - 6], rgba(ink, 0.75), 1, [3, 3]);
      ctx.font = "10px system-ui, sans-serif";
      ctx.fillStyle = rgba(ink, 1);
      const right = x(tick) + 4 + ctx.measureText(text).width > w - pad;
      ctx.textAlign = right ? "right" : "left";
      ctx.fillText(text, x(tick) + (right ? -4 : 4), 12 + row * 11);
    });
    ctx.fillStyle = "#fff";
    for (const tick of meta.shock_ticks) {      // a shock: small white wedge on the top edge
      ctx.beginPath();
      ctx.moveTo(x(tick + 0.5) - 3, 0); ctx.lineTo(x(tick + 0.5) + 3, 0); ctx.lineTo(x(tick + 0.5), 6);
      ctx.fill();
    }

    // One variance line per geometry, on a shared scale so they can be compared.
    const series = v.runs.map((run) => [v.shared.initial_variance, ...run.ticks.map((t) => t.variance)]);
    const [low, high] = [Math.min(...series.flat()), Math.max(...series.flat())];
    const vy = (value) => h - 10 - ((value - low) / (high - low || 1)) * (h - 24);
    series.forEach((values, index) => {
      ctx.beginPath();
      values.forEach((value, k) => ctx.lineTo(x(k), vy(value)));
      ctx.strokeStyle = v.runs.length > 1 ? rgba(C.RUN_INK[index], 1) : rgba(INK.text, 0.95);
      ctx.lineWidth = index === v.focus ? 2.2 : 1.3;
      ctx.stroke();
    });
    label(ctx, v.runs.length > 1 ? "opinion variance (one line per geometry)" : "opinion variance (line)",
          [w - pad, 26], rgba(INK.text, 0.9), "right");

    const head = x(v.tick < 0 ? 0 : v.tick + v.frac);
    segment(ctx, [head, 0], [head, h], "#fff", 1.5);
  }

  // -------------------------------------------------------------------------
  // Histograms: distances between network neighbours under each geometry
  // -------------------------------------------------------------------------

  Viewer.buildHistograms = () => {
    v.histograms = v.runs.map((run) => {
      const canvas = el("canvas", { className: "hist", role: "img" });
      const sentence = el("p", { className: "hint" });
      const caption = el("figcaption", {}, el("b", { textContent: run.label }));
      if (v.runs.length > 1) {
        const swatch = el("i", { className: "swatch" });
        swatch.style.background = rgba(C.RUN_INK[run.index], 1);
        caption.prepend(swatch);
      }
      return { run, canvas, sentence, figure: el("figure", {}, caption, canvas, sentence) };
    });
    $("v-hists").replaceChildren(...v.histograms.map((histogram) => histogram.figure));
  };

  function drawHistogram({ run, canvas, sentence }) {
    const { ctx, w, h } = fit(canvas);
    const measure = measureAt(run, v.tick);
    const bins = measure.histogram;
    const [left, right, base] = [10, w - 10, h - 16];
    const tallest = Math.max(1, ...bins);
    const slot = (right - left) / bins.length;
    const threshold = left + (run.epsilon / run.max_distance) * (right - left);
    bins.forEach((count, k) => {
      const height = (count / tallest) * (base - 12);
      const centre = left + (k + 0.5) * slot;
      ctx.fillStyle = rgba(centre <= threshold ? INK.heard : INK.far, 0.8);
      ctx.fillRect(left + k * slot + 0.5, base - height, Math.max(slot - 1, 1), height);
    });
    segment(ctx, [left, base + 0.5], [right, base + 0.5], "rgba(255,255,255,.25)", 1);
    segment(ctx, [threshold, 4], [threshold, base], "#fff", 1.5, [4, 3]);
    const flip = threshold > w - 70;
    label(ctx, `ε = ${run.epsilon.toFixed(2)}`, [threshold + (flip ? -5 : 5), 13], "#fff", flip ? "right" : "left");
    ctx.font = "10px system-ui, sans-serif";
    ctx.fillStyle = rgba(INK.text, 0.8);
    ctx.textAlign = "left";
    ctx.fillText("0 (identical)", left, h - 3);
    ctx.textAlign = "right";
    ctx.fillText(`${run.max_distance.toFixed(2)} (furthest possible)`, right, h - 3);

    const undefined_ = measure.undefined
      ? ` ${measure.undefined} pair(s) have no defined distance (an agent exactly at neutral).` : "";
    const text = `${percent(measure.coverage)} of neighbour pairs are within ε and can talk.${undefined_}`;
    if (sentence.textContent !== text) sentence.textContent = text;
  }

  Viewer.drawAll = () => {
    v.panes.forEach(drawPane);
    drawTimeline();
    v.histograms.forEach(drawHistogram);
    Viewer.renderPhases();
  };
})();
