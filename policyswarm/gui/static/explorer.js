"use strict";

// ε explorer: the share of pairs a confidence threshold admits under each
// geometry (GET /api/explorer/coverage), and, when the methods note's runs
// exist, outcomes against realised coverage (GET /api/explorer/outcomes).
// Charts are plain SVG. Series differ by colour AND line style, carry direct
// labels and a legend, and have a crosshair tooltip and a table view.
// Uses $ and el from app.js.

const Explorer = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  const SERIES = {
    euclidean: { label: "Euclidean", colour: "var(--series-1)", dash: "" },
    cosine:    { label: "cosine",    colour: "var(--series-2)", dash: "7 4" },
    manifold:  { label: "angular",   colour: "var(--series-3)", dash: "2 4" },
  };
  const OUTCOME_TEXT = {
    groups_common: "opinion groups (≥1% of agents, common ruler)",
    eff_groups_common: "effective number of groups (common ruler)",
    clusters: "opinion groups (each metric's own ruler)",
    variance: "final variance", radial_var: "spread of opinion strength",
    dispersion: "spread of opinion direction", converged_at: "rounds until settled",
  };
  let loaded = false;
  let outcomes = null;
  let timer = null;

  const svg = (tag, attrs = {}) => {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  };
  const fmt = (x) => (Math.abs(x) >= 100 ? x.toFixed(0) : Math.abs(x) >= 1 ? x.toFixed(2) : x.toFixed(3));

  /** A line chart. series: [{key, label, colour, dash, points: [[x, y], ...]}]. */
  function lineChart(container, series, opts) {
    const W = 720, H = 340, M = { l: 52, r: 96, t: 14, b: 44 };
    const xs = series.flatMap((s) => s.points.map((p) => p[0]));
    const ys = series.flatMap((s) => s.points.map((p) => p[1]));
    const xMax = opts.xMax ?? Math.max(...xs, 1e-9), yMax = opts.yMax ?? Math.max(...ys, 1e-9);
    const xMin = opts.xMin ?? 0, yMin = opts.yMin ?? 0;
    const X = (x) => M.l + ((x - xMin) / (xMax - xMin || 1)) * (W - M.l - M.r);
    const Y = (y) => H - M.b - ((y - yMin) / (yMax - yMin || 1)) * (H - M.t - M.b);
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.title, class: "linechart" });

    for (let k = 0; k <= 4; k++) {                       // recessive grid and axis labels
      const yv = yMin + (k / 4) * (yMax - yMin), xv = xMin + (k / 4) * (xMax - xMin);
      root.append(svg("line", { x1: M.l, x2: W - M.r, y1: Y(yv), y2: Y(yv), class: "grid-line" }));
      const yt = svg("text", { x: M.l - 8, y: Y(yv) + 4, class: "tick", "text-anchor": "end" });
      yt.textContent = opts.yPercent ? `${Math.round(100 * yv)}%` : fmt(yv);
      const xt = svg("text", { x: X(xv), y: H - M.b + 18, class: "tick", "text-anchor": "middle" });
      xt.textContent = opts.xPercent ? `${Math.round(100 * xv)}%` : fmt(xv);
      root.append(yt, xt);
    }
    root.append(svg("line", { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b, class: "axis" }));
    const xl = svg("text", { x: (M.l + W - M.r) / 2, y: H - 6, class: "axis-label", "text-anchor": "middle" });
    xl.textContent = opts.xLabel;
    const yl = svg("text", { x: 14, y: (M.t + H - M.b) / 2, class: "axis-label", "text-anchor": "middle",
                             transform: `rotate(-90 14 ${(M.t + H - M.b) / 2})` });
    yl.textContent = opts.yLabel;
    root.append(xl, yl);

    if (opts.markerX !== undefined) {
      root.append(svg("line", { x1: X(opts.markerX), x2: X(opts.markerX), y1: M.t, y2: H - M.b, class: "marker" }));
      const t = svg("text", { x: X(opts.markerX) + 4, y: M.t + 10, class: "tick" });
      t.textContent = opts.markerLabel ?? "";
      root.append(t);
    }

    const labelSpots = [];
    for (const s of series) {
      const d = s.points.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
      root.append(svg("path", { d, fill: "none", stroke: s.colour, "stroke-width": 2,
                                "stroke-dasharray": s.dash, "stroke-linejoin": "round" }));
      for (const dot of s.dots ?? []) {
        root.append(svg("circle", { cx: X(dot[0]), cy: Y(dot[1]), r: 5, fill: s.colour,
                                    stroke: "var(--surface)", "stroke-width": 2 }));
      }
      // Label at the end of the line, or (opts.labelAtY) where it first reaches that height.
      let anchor = s.points[s.points.length - 1], lx = W - M.r + 6;
      if (opts.labelAtY !== undefined) {
        anchor = s.points.find((p) => p[1] >= opts.labelAtY) ?? anchor;
        lx = X(anchor[0]) + 8;
      }
      let y = Y(anchor[1]);
      while (labelSpots.some((v) => Math.abs(v - y) < 14)) y += 14;   // keep labels apart
      labelSpots.push(y);
      const label = svg("text", { x: lx, y: y + 4, class: "direct-label" });
      label.textContent = s.label;
      root.append(label);
    }

    // Crosshair + tooltip: the nearest point of every series at the pointer's x.
    const cross = svg("line", { y1: M.t, y2: H - M.b, class: "crosshair", visibility: "hidden" });
    const hit = svg("rect", { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b,
                              fill: "transparent", tabindex: "0", "aria-label": "Move along the chart to read values" });
    root.append(cross, hit);
    const tip = el("div", { className: "chart-tip", hidden: true });
    const readAt = (fx) => {
      const x = xMin + fx * (xMax - xMin);
      cross.setAttribute("x1", X(x)); cross.setAttribute("x2", X(x)); cross.setAttribute("visibility", "visible");
      tip.replaceChildren(el("b", { textContent: `${opts.xName}: ${opts.xPercent ? `${Math.round(100 * x)}%` : fmt(x)}` }),
        ...series.map((s) => {
          const p = s.points.reduce((a, b) => (Math.abs(b[0] - x) < Math.abs(a[0] - x) ? b : a));
          return el("div", { textContent: `${s.label}: ${opts.yPercent ? `${Math.round(100 * p[1])}%` : fmt(p[1])}` });
        }));
      tip.hidden = false;
      tip.style.left = `${(100 * X(x)) / W}%`;
    };
    hit.addEventListener("pointermove", (e) => {
      const box = hit.getBoundingClientRect();
      readAt(Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)));
    });
    hit.addEventListener("pointerleave", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });
    let keyX = 0.5;
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        keyX = Math.min(1, Math.max(0, keyX + (e.key === "ArrowRight" ? 0.02 : -0.02)));
        readAt(keyX); e.preventDefault();
      }
    });
    hit.addEventListener("focus", () => readAt(keyX));
    hit.addEventListener("blur", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });

    const legend = el("ul", { className: "chart-legend" }, ...series.map((s) => el("li", {},
      (() => { const k = svg("svg", { width: 26, height: 10, "aria-hidden": "true" });
               k.append(svg("line", { x1: 0, x2: 26, y1: 5, y2: 5, stroke: s.colour, "stroke-width": 2.5,
                                      "stroke-dasharray": s.dash })); return k; })(),
      s.label)));
    const wrap = el("div", { className: "chart-wrap" }, root, tip);
    container.replaceChildren(wrap, legend);
  }

  async function loadCoverage() {
    const space = $("ex-space").value, d = Number($("ex-d").value), eps = Number($("ex-eps").value);
    if (!(d >= 2 && d <= 16) || !(eps > 0)) {
      $("ex-status").textContent = "Dimensions must be 2 to 16 and ε above 0.";
      return;
    }
    $("ex-status").textContent = "Counting pairs…";
    const res = await fetch(`/api/explorer/coverage?space=${space}&d=${d}&epsilon=${eps}`);
    if (!res.ok) { $("ex-status").textContent = "Could not compute coverage."; return; }
    const body = await res.json();
    const series = body.metrics.map((m) => ({ key: m.metric, ...SERIES[m.metric], points: m.curve,
                                             dots: [[m.matched_epsilon, body.euclidean_share]] }));
    lineChart($("ex-chart"), series, {
      title: `Share of pairs within ε, ${space} space, ${d} dimensions`, xLabel: "threshold ε (each geometry's own units)",
      yLabel: "share of pairs within ε", xName: "ε", yPercent: true, yMax: 1,
      markerX: eps, markerLabel: `ε = ${eps}`, labelAtY: 0.55,
    });
    const shared = body.metrics.map((m) => `${SERIES[m.metric].label} ${Math.round(100 * m.at_shared)}%`).join(", ");
    $("ex-caption").textContent = `At the same number ε = ${eps}: ${shared} of pairs. `
      + `Dots mark each geometry's matched ε, where it admits the same share as Euclidean `
      + `(${Math.round(100 * body.euclidean_share)}%).`;
    $("ex-status").textContent = "";
    const head = el("tr", {}, el("th", { scope: "col", textContent: "Geometry" }),
      el("th", { scope: "col", textContent: `Share at ε = ${eps}` }),
      el("th", { scope: "col", textContent: "Matched ε" }));
    const rows = body.metrics.map((m) => el("tr", {}, el("th", { scope: "row", textContent: SERIES[m.metric].label }),
      el("td", { textContent: `${Math.round(100 * m.at_shared)}%` }), el("td", { textContent: m.matched_epsilon.toFixed(3) })));
    $("ex-table").replaceChildren(el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows)));
    drawOutcomes();
  }

  function drawOutcomes() {
    if (!outcomes?.available) return;
    const space = $("ex-space").value, d = Number($("ex-d").value), key = $("ex-outcome").value;
    const rows = outcomes.rows.filter((r) => r.space === space && r.d === d);
    if (!rows.length) {
      $("ex-out-note").textContent = "The paper's runs cover 2, 4 and 8 dimensions; pick one of those.";
      $("ex-out-figure").hidden = true;
      return;
    }
    $("ex-out-note").textContent = "From the methods note's ε-response runs (minimal model, 500 agents, 2,000 rounds).";
    const series = Object.keys(SERIES).map((metric) => ({
      key: metric, ...SERIES[metric],
      points: rows.filter((r) => r.metric === metric).map((r) => [r.pass_rate, r[key]]).sort((a, b) => a[0] - b[0]),
    })).filter((s) => s.points.length);
    lineChart($("ex-out-chart"), series, {
      title: `${OUTCOME_TEXT[key] ?? key} against realised pass rate`, xLabel: "realised pass rate over the run",
      yLabel: OUTCOME_TEXT[key] ?? key, xName: "pass rate", xPercent: true, xMax: 1,
    });
    $("ex-out-figure").hidden = false;
  }

  async function loadOutcomes() {
    const res = await fetch("/api/explorer/outcomes");
    outcomes = res.ok ? await res.json() : null;
    if (!outcomes?.available) {
      $("ex-out-note").textContent = "The methods note's ε-response runs have not been generated yet "
        + "(paper/methods_note/run_curves.py).";
      return;
    }
    $("ex-outcome").replaceChildren(...outcomes.outcomes.map((o) =>
      el("option", { value: o, textContent: OUTCOME_TEXT[o] ?? o })));
    $("ex-out-controls").hidden = false;
    $("ex-outcome").addEventListener("change", drawOutcomes);
    drawOutcomes();
  }

  function show() {
    if (loaded) return;
    loaded = true;
    const later = () => { clearTimeout(timer); timer = setTimeout(loadCoverage, 250); };
    for (const id of ["ex-space", "ex-d", "ex-eps"]) $(id).addEventListener("input", later);
    loadCoverage();
    loadOutcomes();
  }

  return { show, lineChart };
})();
