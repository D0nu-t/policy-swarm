# Dashboard usability audit (2026-10-16)

Method: headless Edge over the DevTools protocol at 375 and 1440 px, light and dark (forced with `prefers-color-scheme` emulation), every `<details>` opened. Checks follow the priority order of the `ui-ux-pro-max` skill: accessibility, then interaction, layout, typography and colour, forms, navigation, charts. Before screenshots: `scratchpad/audit-before/` (not kept in the repo).

Measured on the page as it was:
- page width equals viewport width at 375 px (no horizontal scroll under mobile emulation);
- every input has a label (0 unlabelled);
- 94 text elements under 13 px;
- 19 controls under 32 px tall;
- no JavaScript errors.

## Findings, by priority

| # | Priority | Finding | Where | Fix |
|---|---|---|---|---|
| 1 | Accessibility | Help text and hints are 12.5 px; 94 text elements are under 13 px | `style.css` `small, .hint`, tables, legends | Base 16 px; hints and legends at least 13.5 px |
| 2 | Interaction | 19 controls under 32 px tall: segmented buttons, small selects, checkboxes, "remove" buttons | `.seg button`, `.transport select`, `button.remove`, native checkboxes | Minimum 40 px, 44 px on coarse pointers; checkboxes 18 px |
| 3 | Interaction | No feedback between pressing "Run experiments" and the run starting | `app.js startRun` | Busy state on the button; message near the button |
| 4 | Accessibility | Focus ring missing on links, segmented buttons and checkboxes | `style.css` focus rules | One `:focus-visible` rule for every interactive element |
| 5 | Animation | Transitions ignore `prefers-reduced-motion` | progress bars, phase strip | Reduced-motion media query |
| 6 | Forms | Labels are code names (`n_agents`, `ba_m`, `sbm_p_in`, `deployment_rate_cap`) | generated forms (`buildInput`) | Human labels from the server (`ParamSpec.label`), falling back to a humanised name |
| 7 | Forms | Simulation settings are one ungrouped list of 15 fields; the new hidden choices sit among ordinary settings | `#sim-config` | Groups: population and time, interaction, network, **hidden choices** (with a one-line explanation) |
| 8 | Forms | Errors appear only at the bottom of the form, far from the field | `showError` | Mark the field (`aria-invalid`, red border), focus it, keep the message near the action |
| 9 | Navigation | One long page (about 5,500 px on a phone, fully open); no deep links; results appear far below | `index.html` | Top navigation with four views (Run experiments, Watch one simulation, ε explorer, Results), URL hash, `aria-current` |
| 10 | Typography and colour | Two separate `:root` token blocks; raw hex values in the viewer section | `style.css` | One token layer (primitive → semantic); viewer colours as semantic tokens |
| 11 | Charts | (new panels) | explorer, audit | Line style as well as colour, direct labels, a table view, a tooltip (dataviz rules) |

Contrast was not a problem: muted text measures about 6.3:1 in light mode and about 7:1 in dark.

## After (same method, 2026-10-16)

| Check | Before | After |
|---|---|---|
| Text elements under 13 px (run view, all sections open) | 94 | 0–2 (chart axis ticks) |
| Controls under 32 px tall | 19 | 0 |
| Horizontal scroll at 375 px, every view | none on the old single page | none on any of the four views (found and fixed two overflows during the pass: figure grid minimum widths, long file-name links) |
| Unlabelled inputs | 0 | 0 |
| Labels shown as code names | most simulation settings | none (server labels; humanised fallback) |
| JavaScript errors | 0 | 0, in every view, light and dark |
| Keyboard | — | skip link; focus ring visible on navigation links (solid outline) |

What changed:
- **Navigation:** four views (Run experiments · Watch one simulation · ε explorer · Results) with URL-hash deep links and `aria-current`; a skip link.
- **Tokens:** one token layer (primitive → semantic, dark mode from the same names); series colours are the validated dataviz slots.
- **Sizing:** 16 px base, 40 px controls (44 px on coarse pointers), 18 px checkboxes; one `:focus-visible` rule; reduced motion respected.
- **Forms:** grouped settings with human labels; the hidden choices in a marked group with an explanation; errors shown on the field itself, with focus moved to it; busy state on "Run experiments"; the view switches to Results when a run starts.
- **New:**
  - Compare mode in the viewer (one hidden choice per column);
  - the ε explorer (live coverage chart with matched points, table view, keyboard-readable crosshair; outcome curves once the paper's runs exist);
  - the hidden-choices check on every run's results.
- **Found by the audit itself:** with the unit-cube gate, the experiment engine reads ε in unit-cube units, while the viewer keeps the Euclidean gate fixed. The difference is now stated in the field's help text, and the audit warns about it.
