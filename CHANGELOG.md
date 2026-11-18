# Changelog

## 0.2.0 - 2026-11-18

- `rloop status --json` and `rloop report --json` print the status and the finished report as JSON for a local job runner, and `rloop cancel` asks the active job to stop.
- The README and the How-it-works page describe the report's evidence tags and links as the report shows them, and say which runs link their evidence.
- The README opens with who the tool is for, what goes in and what comes out, and a real example with its negative result.
- Both starter prompts include the repository URL and a clone step.
- Each mode says where your data goes and who approves a new service.
- The assessment lessons are written as general patterns, without team or project names.
- The loop diagram marks your decisions, your agent and its workers, and the route and evidence with their own icons and colours.
- A bug report template for GitHub issues that asks for the version you use.
- Licence: code, `SKILL.md` and prompt files are under Apache-2.0; texts and images are under CC BY 4.0. The review rubric in the self-assess skill and the rubric questions in `assessment.py` are adapted from upstream material and stay under CC BY 4.0, credited in `NOTICE` with source, commit and URL. Versions published up to commit a21c598 keep `SKILL.md` and the skill footers under CC BY 4.0, as `NOTICE` states.

## 0.1.0 - 2026-11-15

First release: parallel research loops with a locked contract, a protected evaluator and evidence-tagged reports, in coached and autonomous mode.
