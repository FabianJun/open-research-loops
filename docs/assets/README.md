# Visual roles

| Role | Light | Dark | Icon | Meaning |
|---|---|---|---|---|
| You decide | `#c4432b` | `#ff8a70` | person | Your question, choices, prediction, verdict and own words |
| Your agent | `#2f5bea` | `#7c9cff` | checkbox | Technical work: code, workers, tools and compute |
| Route and evidence | `#0e7c7b` | `#2fb8b0` | arrow or check | The route, protected evaluator, checked evidence, report and what you keep |
| Neutral | `#59636e` | `#9198a1` | none | Infrastructure, notes and facts |

The start page uses `competence-*` for the coaching principle, `route-*` for
decisions and technical work, and `loop-*` for registration through reporting.
The loop legend labels each role. The 16 px `icon-you.svg` and `icon-agent.svg`
mark table headers; their light-palette colours remain readable on both themes.
Mermaid flowcharts use role strokes without replacing theme fills; sequence
groups use transparent role tints. Audience, agent compatibility and coding-help
badges use coral, blue and teal respectively; the licence badge is neutral.
The existing social preview is the start page's print illustration.

For new visuals:

- Supply matching light and dark SVGs with the same geometry and wording.
  Small icons may use one colour readable on both white and `#0d1117`.
- Use the PresentTogether (PT) font stack from `route-light.svg`:
  `-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif`.
- Reuse its card geometry: 196 × 70, radius 12, 18 px text inset, 22 px line spacing.
  Preserve an existing diagram's geometry when recolouring it.
- Include no metadata or editor attributes. Give SVGs a title and description
  (a title suffices for a simple icon), and provide full alt text where embedded.
- Colour is never the only carrier: pair it with a label or icon, including in
  print and for screen readers. Avoid coloured emoji, extra banners and colour hacks.
- Preview both themes at 1100 and 830 px; keep PNG previews outside the repository.

Documentation licensed CC BY 4.0.
