# Copy Voice

Load before writing or editing ANY user-facing string in DDE surfaces.
Authority: `docs/planning/dde-frontend-ux-playbook.md` §4.6, §6.5. Gate:
`interfaces/dde-studio/shared/clientHonesty.test.ts` (`FORBIDDEN_HELPER`
superset).

## Voice rules

- Verb-first controls: "Start local Core", not "Local Core can be started".
- Sentence case everywhere; figures not words ("3 missions" not "three missions").
- Manufacturing-vocabulary exactness: mission/run/lease/gate terms come from
  the schemas — never invented synonyms, never "jobs" or "workflows".
- Errors state cause + next action. Unreachable ≠ misconfigured. No blame.
- Terse. If a sentence explains what the user can already see, delete it.

## Forbidden (blocking)

- Exclamation marks.
- "Welcome to", "simply", "easily", "just".
- Marketing superlatives ("blazingly fast", "powerful", "seamless").
- Emoji anywhere in UI strings.
- Helper essays and instructional paragraphs in empty states.

## Before PR

Run the studio suite locally (`npm --prefix interfaces/dde-studio test`);
the copy gate must be green. New strings that dodge the regexes but violate
the voice still block in review — the gate is mechanical, taste is human.
