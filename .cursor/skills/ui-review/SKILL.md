# UI Review (fresh-context critic)

Load for reviewing any UI change. Also drives the independent fresh-context
critique required by playbook guardrail 7. Authority:
`docs/planning/dde-frontend-ux-playbook.md` §4.7, §8, §6.3.

## Steps

1. Render the changed surfaces from pixels — gallery screenshots or prototype
   pages. NEVER review from diff alone.
2. Score every §8.1 dimension 1–5: pattern fidelity, token discipline,
   hierarchy & rhythm, data presentation, copy voice, states completeness,
   motion restraint, accessibility. Any dimension <4 BLOCKS the merge — name
   the specific pixel and what would raise the score.
3. Walk the anti-tell catalog (§1.1) and flag every observed instance:
   gradients-as-primary, purple defaults, emoji icons, pill-spam, identical
   card grids, glassmorphism, traffic-light dots, marketing hero grammar.
4. Verify: states matrix present (idle/loading/empty/error/disabled); both
   viewport widths hold (~320px panel and ~900–1280px editor); copy voice
   clean; reduced-motion variants exist per animated state; provenance ledger
   row + `References:` footer for anything mined; lint budget not increased.
5. Verdict exactly one of: APPROVE / BLOCK(items) / EDR-needed.

You must have no authorship stake in the change under review.
