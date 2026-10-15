"use strict";

// Simulation viewer, part 2 of 4: where agents are placed in a picture.
//
// Viewer.project(pane, w, h) returns a layout:
//   P        screen position of every agent
//   R        drawn radius of every agent
//   order    drawing order (3-D only: far agents first)
//   alpha    opacity per agent (3-D only: far agents fainter)
//   before   draws what sits under the agents (axes, links, trails)
//   after    draws what sits on top (the policy marker)
//   note     one line of text shown under the picture
//
// To add a view: write a function with this return shape, add it to VIEWS and
// VIEW_HINTS, and add a button with the same data-value to #v-view.

(() => {
  const { v, C, clamp, lerp, smooth, rgba, percent, opinion, opinionsAfter, policyAt, measureAt,
          phaseWindows, progress } = Viewer;

  const meta = () => v.shared.meta;
  const count = () => meta().n_agents;

  function line(ctx, a, b, colour, width = 1, dash = []) {
    ctx.beginPath();
    ctx.setLineDash(dash);
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  function text(ctx, string, [x, y], colour, align = "left", weight = "") {
    ctx.font = `${weight} 11px system-ui, sans-serif`;
    ctx.textAlign = align;
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(13,17,23,.85)";
    ctx.strokeText(string, x, y);
    ctx.fillStyle = colour;
    ctx.fillText(string, x, y);
  }

  /** The policy marker: a diamond that pulses while the policy phase plays. */
  function policyMarker(ctx, run, at, size = 5.5) {
    const pull = v.tick >= 0 && v.frac < 1 ? progress(phaseWindows(run.ticks[v.tick]).policy) : null;
    if (pull !== null) {
      ctx.beginPath();
      ctx.arc(at[0], at[1], 8 + 46 * (1 - pull), 0, 2 * Math.PI);
      ctx.strokeStyle = rgba(C.INK.policy, pull * 0.8);
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.save();
    ctx.translate(at[0], at[1]);
    ctx.rotate(Math.PI / 4);
    ctx.fillStyle = rgba(C.INK.policy, 1);
    ctx.strokeStyle = "#0d1117";
    ctx.lineWidth = 2;
    ctx.fillRect(-size, -size, 2 * size, 2 * size);
    ctx.strokeRect(-size, -size, 2 * size, 2 * size);
    ctx.restore();
    text(ctx, "policy", [at[0] + size + 6, at[1] + 4], rgba(C.INK.policy, 1), "left", "600");
  }

  /** Faint lines showing how far each agent travels during this tick. */
  function trails(ctx, from, to) {
    if (v.tick < 0) return;
    ctx.beginPath();
    for (let i = 0; i < to.length; i++) {
      ctx.moveTo(from[i][0], from[i][1]);
      ctx.lineTo(to[i][0], to[i][1]);
    }
    ctx.strokeStyle = "rgba(255,255,255,.22)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  const policyNow = (run, d) =>
    lerp(policyAt(run, v.tick - 1)[d], policyAt(run, v.tick)[d], v.tick < 0 ? 1 : smooth(v.frac));

  // -------------------------------------------------------------------------
  // Network: fixed positions from the server's layout
  // -------------------------------------------------------------------------

  function network(pane, w, h) {
    const { agents, edges } = v.shared;
    const pad = 28;
    const scale = clamp(Math.min(w, h) / 460, 0.6, 1.3);
    const P = agents.x.map((x, i) => [pad + x * (w - 2 * pad), pad + agents.y[i] * (h - 2 * pad)]);
    const R = agents.degree.map((d) => (2.2 + 1.25 * Math.sqrt(d)) * scale);
    const before = (ctx) => {
      ctx.beginPath();
      for (const [a, b] of edges) { ctx.moveTo(P[a][0], P[a][1]); ctx.lineTo(P[b][0], P[b][1]); }
      ctx.strokeStyle = "rgba(255,255,255,.07)";
      ctx.lineWidth = 1;
      ctx.stroke();
      if (v.selected === null) return;      // the selected agent's own links: who it can talk to
      ctx.beginPath();
      for (const [a, b] of edges) {
        if (a !== v.selected && b !== v.selected) continue;
        ctx.moveTo(P[a][0], P[a][1]); ctx.lineTo(P[b][0], P[b][1]);
      }
      ctx.strokeStyle = "rgba(255,255,255,.4)";
      ctx.stroke();
    };
    return { P, R, before, after: () => {}, note: "" };
  }

  // -------------------------------------------------------------------------
  // 2-D slice: two chosen dimensions
  // -------------------------------------------------------------------------

  function slice(pane, w, h) {
    const run = pane.run;
    const [xDim, yDim] = v.dims;
    const pad = 34;
    const sx = (value) => pad + ((value + 1) / 2) * (w - 2 * pad);
    const sy = (value) => h - pad - ((value + 1) / 2) * (h - 2 * pad);
    const n = count();
    const P = Array.from({ length: n }, (_, i) => [sx(opinion(run, i, xDim)), sy(opinion(run, i, yDim))]);
    const R = new Array(n).fill(3.6);

    const before = (ctx) => {
      const m = meta();
      const threshold = m.violator_threshold;
      ctx.fillStyle = rgba(C.INK.violator, 0.1);          // violator zone
      if (xDim === m.violator_dimension) {
        ctx.fillRect(sx(threshold), pad, w - pad - sx(threshold), h - 2 * pad);
      } else if (yDim === m.violator_dimension) {
        ctx.fillRect(pad, pad, w - 2 * pad, sy(threshold) - pad);
      }
      if (xDim === m.violator_dimension || yDim === m.violator_dimension) {
        text(ctx, "violators", [w - pad - 4, pad + 14], rgba(C.INK.violator, 0.95), "right", "600");
      }
      ctx.strokeStyle = "rgba(255,255,255,.16)";
      ctx.lineWidth = 1;
      ctx.strokeRect(pad, pad, w - 2 * pad, h - 2 * pad);
      line(ctx, [sx(0), pad], [sx(0), h - pad], "rgba(255,255,255,.1)", 1, [2, 4]);
      line(ctx, [pad, sy(0)], [w - pad, sy(0)], "rgba(255,255,255,.1)", 1, [2, 4]);
      ctx.font = "11px system-ui, sans-serif";
      ctx.fillStyle = rgba(C.INK.text, 0.8);
      ctx.textAlign = "center";
      ctx.fillText(m.dimensions[xDim], w / 2, h - 10);
      ctx.fillText("−1", pad, h - 10);
      ctx.fillText("+1", w - pad, h - 10);
      ctx.save();
      ctx.translate(13, h / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(m.dimensions[yDim], 0, 0);
      ctx.restore();
      if (v.tick >= 0) {
        const previous = opinionsAfter(run, v.tick - 1);
        trails(ctx, previous.map((o) => [sx(o[xDim]), sy(o[yDim])]), P);
      }
    };
    const after = (ctx) => policyMarker(ctx, run, [sx(policyNow(run, xDim)), sy(policyNow(run, yDim))]);
    return { P, R, before, after, note: "" };
  }

  // -------------------------------------------------------------------------
  // 3-D: three chosen dimensions in a cube you can rotate
  // -------------------------------------------------------------------------

  const CAMERA = 5;        // distance of the eye from the centre, in opinion units

  function cube(pane, w, h) {
    const run = pane.run;
    const m = meta();
    const dims = v.dims;
    const onSphere = v.sphere && run.angular;
    const [cy_, sy_] = [Math.cos(v.rotation.yaw), Math.sin(v.rotation.yaw)];
    const [cp, sp] = [Math.cos(v.rotation.pitch), Math.sin(v.rotation.pitch)];
    const size = Math.min(w, h) * (onSphere ? 0.36 : 0.25);

    /** Rotate a 3-D point and project it: [screen x, screen y, depth, scale]. */
    const project = ([x, y, z]) => {
      const x1 = x * cy_ + z * sy_;
      const z1 = -x * sy_ + z * cy_;
      const y2 = y * cp - z1 * sp;
      const z2 = y * sp + z1 * cp;
      const k = CAMERA / (CAMERA - z2);
      return [w / 2 + x1 * size * k, h / 2 - y2 * size * k, z2, k];
    };
    /** "Directions only": scale an opinion to length 1 over all its dimensions. */
    const direction = (full) => {
      const norm = Math.hypot(...full) || 1;
      return dims.map((d) => full[d] / (onSphere ? norm : 1));
    };
    const current = (i) => m.dimensions.map((_, d) => opinion(run, i, d));

    const n = count();
    const projected = Array.from({ length: n }, (_, i) => project(direction(current(i))));
    const P = projected.map(([x, y]) => [x, y]);
    const R = projected.map(([, , , k]) => 3.3 * k);
    const reach = onSphere ? 1 : Math.sqrt(3);
    const alpha = projected.map(([, , depth]) => clamp(0.3 + 0.7 * (depth + reach) / (2 * reach)));
    const order = projected.map((_, i) => i).sort((a, b) => projected[a][2] - projected[b][2]);

    const before = (ctx) => {
      const ink = (depth) => `rgba(255,255,255,${(0.1 + 0.16 * clamp((depth + reach) / (2 * reach))).toFixed(3)})`;
      if (onSphere) {            // three great circles of the unit sphere
        for (const [a, b] of [[0, 1], [0, 2], [1, 2]]) {
          let last = null;
          for (let step = 0; step <= 64; step++) {
            const angle = (step / 64) * 2 * Math.PI;
            const point = [0, 0, 0];
            point[a] = Math.cos(angle);
            point[b] = Math.sin(angle);
            const next = project(point);
            if (last) line(ctx, last, next, ink((last[2] + next[2]) / 2));
            last = next;
          }
        }
      } else {                   // the opinion cube, far edges fainter
        const corners = [];
        for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) corners.push([x, y, z]);
        corners.forEach((a, i) => corners.slice(i + 1).forEach((b) => {
          if (a.filter((value, axis) => value !== b[axis]).length !== 1) return;
          const [from, to] = [project(a), project(b)];
          line(ctx, from, to, ink((from[2] + to[2]) / 2));
        }));
      }
      const origin = project([0, 0, 0]);
      dims.forEach((d, axis) => {       // one labelled arrow per dimension, from neutral to +1
        const tip = [0, 0, 0];
        tip[axis] = 1;
        const end = project(tip);
        line(ctx, origin, end, rgba(C.INK.text, 0.45), 1, [3, 3]);
        const far = [0, 0, 0];
        far[axis] = 1.18;
        const at = project(far);
        text(ctx, `${m.dimensions[d]} +`, [at[0], at[1] + 4], rgba(C.INK.text, 0.9), "center");
      });
      if (v.tick >= 0) {
        const previous = opinionsAfter(run, v.tick - 1);
        trails(ctx, previous.map((o) => project(direction(o))), P);
      }
    };
    const after = (ctx) => {
      const policy = project(direction(m.dimensions.map((_, d) => policyNow(run, d))));
      policyMarker(ctx, run, policy, 5.5 * policy[3]);
    };
    return { P, R, order, alpha, before, after,
             note: onSphere ? "Directions only: each opinion is scaled to length 1 over all dimensions, which is what this geometry compares." : "" };
  }

  // -------------------------------------------------------------------------
  // Distance map: all dimensions, placed by the geometry's own distances
  // -------------------------------------------------------------------------

  function map(pane, w, h) {
    const run = pane.run;
    const pad = 30;
    const scale = (Math.min(w, h) / 2 - pad) / (run.map_extent || 1);
    const place = ([x, y]) => [w / 2 + x * scale, h / 2 - y * scale];
    const [from, to] = [measureAt(run, v.tick - 1), measureAt(run, v.tick)];
    const k = v.tick < 0 ? 1 : smooth(v.frac);
    const between = (a, b) => place([lerp(a[0], b[0], k), lerp(a[1], b[1], k)]);
    const P = to.map.map((point, i) => between(from.map[i], point));
    const R = new Array(P.length).fill(3.6);
    const reach = run.epsilon * scale;

    const before = (ctx) => {
      // Scale bar: how long epsilon is in this picture.
      const [x, y] = [pad, h - 16];
      line(ctx, [x, y], [x + reach, y], rgba(C.INK.heard, 0.95), 2);
      line(ctx, [x, y - 4], [x, y + 4], rgba(C.INK.heard, 0.95), 2);
      line(ctx, [x + reach, y - 4], [x + reach, y + 4], rgba(C.INK.heard, 0.95), 2);
      text(ctx, `ε = ${run.epsilon.toFixed(2)}: closer than this, a listener can hear a speaker`,
           [x, y - 8], rgba(C.INK.text, 0.9));
      if (v.selected !== null) {         // roughly who the selected agent can hear
        ctx.beginPath();
        ctx.arc(P[v.selected][0], P[v.selected][1], reach, 0, 2 * Math.PI);
        ctx.fillStyle = rgba(C.INK.heard, 0.09);
        ctx.fill();
        ctx.strokeStyle = rgba(C.INK.heard, 0.6);
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      trails(ctx, from.map.map(place), P);
    };
    const after = (ctx) => policyMarker(ctx, run, between(from.map_policy, to.map_policy));
    return { P, R, before, after,
             note: `A flat picture keeps ${percent(to.map_fit)} of the true distances at this tick`
                   + (v.selected !== null ? "; the dashed ring is roughly who the selected agent can hear." : ".") };
  }

  const VIEWS = { slice, cube, map };

  Viewer.VIEW_HINTS = {
    slice: "2-D slice: two dimensions at a time. Distance is measured over all dimensions, so two "
           + "agents can look close here and still be too far apart to talk.",
    cube: "3-D: three dimensions at a time. Drag a picture to rotate it; nearer agents are larger "
          + "and brighter. Dashed arrows point from neutral toward +1 on each dimension.",
    map: "Distance map: all dimensions at once. Agents are placed so that distance on screen "
         + "approximates this geometry's own distance, so agents drawn close together can talk. "
         + "The axes have no meaning of their own.",
  };

  Viewer.project = (pane, w, h) =>
    (pane.kind === "net" ? network : VIEWS[v.view])(pane, w, h);
})();
