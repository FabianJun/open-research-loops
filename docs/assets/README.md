# Visual roles

| Role | Light | Dark | Icon | Meaning |
|---|---|---|---|---|
| You decide | `#b51f33` | `#ff6470` | person | Your question, choices, prediction, verdict and own words |
| Your agent | `#2f5bea` | `#7c9cff` | checkbox | Technical work: code, workers, tools and compute |
| Route and evidence | `#0e7c7b` | `#2fb8b0` | knotted thread | The route, protected evaluator, checked evidence, report and what you keep |
| Neutral | `#59636e` | `#9198a1` | none | Infrastructure, notes and facts |

Where each role appears:

- **Badges** double as the legend: `you decide` carmine, `your agent` blue, `evidence` teal, then
  facts (Python, licence, status) in grey.
- **Pictures:** `loop-*` is the main diagram, `competence-*` the coaching principle, `route-*` who
  does what in coached mode. The social preview is the riso print.
- **Icons:** in the step table of `docs/COACHED.md`, a 14 px `icon-you.svg` marks the moments where
  your view comes first (`alt="your view first"`); 16 px role icons in table headers take `alt=""`.
  Their light colours stay readable on both themes.
- **Mermaid** (`docs/HOW-IT-WORKS.md`): role strokes on GitHub's theme fills; sequence groups use
  transparent role tints.

For new visuals:

- Supply matching light and dark SVGs with the same geometry and wording, viewBox width 1100.
- Font stack: `-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif`.
- Card geometry: 196 × 70, radius 12, 18 px text inset, 22 px line spacing. Preserve an existing
  diagram's geometry when recolouring it.
- `role="img"`, a title and a description (a title suffices for an icon), full alt text where
  embedded, no metadata or editor attributes.
- Colour never works alone: pair it with a label or icon. No coloured emoji, gradients or tinted
  fills.
- Preview both themes at 1100 and 830 px; keep PNG previews outside the repository.

Documentation licensed CC BY 4.0.
