---
description: Append a worklog entry to WORKLOG.md based on this session
---

Based on everything discussed and done in this conversation, write a worklog entry
for today and append it to WORKLOG.md (create the file if it doesn't exist).

First, check the last few entries in WORKLOG.md to stay consistent with the log's
existing style and avoid repeating content already logged.

Then follow this format:

## [today's date]
### **Working on:** [what area/feature/problem this session was about]
**Did:** [bullet list of concrete things accomplished — code changed, bugs fixed,
decisions made. Be specific: file/function names, not vague summaries]
**Decisions & why:** [any choices made and the reasoning, especially if we considered
alternatives — this is the most important part, don't skip it]
**Dead ends:** [anything tried that didn't work, and why — even short ones]
**Blockers:** [anything unresolved or waiting on input]
**Next:** [what's queued up for next session]

Rules:
- Pull from what actually happened in this conversation, don't invent or pad content
- If a section has nothing relevant, write "None" rather than forcing content into it
- Keep bullets terse — this is a log, not a report
- Cross-reference with `git diff` and `git log` for this session if useful, to verify
  what actually changed
