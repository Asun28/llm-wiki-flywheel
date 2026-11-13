# intent/ (Stage 1: Plan)

Ideas enter as version-controlled intent, not as tickets waiting for a
committee. One file per idea: `intent/<slug>.md`, from `_TEMPLATE.md`.

Flow:
1. The originator brainstorms in plain language; Claude synthesizes the
   template (problem, proposed outcome, affected users/systems, constraints,
   open questions); the originator corrects misunderstandings.
   For T1/T2, Claude works the open questions in rounds
   (`.claude/skills/grilling/SKILL.md`): numbered, recommended answer
   first, facts looked up, decisions the originator's. T0 skips this.
2. The product owner reviews and merges (status `accepted`) or closes.
3. `aidlc intent validate <file>` checks sections and status.
4. An accepted intent feeds Stage 2 (`specs/<slug>.md`).

Findings from monitoring, security scans and on-call arrive here too, with
`source: incident|security-scan|on-call` and an Evidence section.

Metrics: time from first conversation to committed intent (leading); share
of intents accepted into a spec, and spec churn after build starts (lagging).
