# Frontend and AI quiz verification — 2026-09-10

- Production build: `npm run build` passed.
- Backend suite: 62 tests passed (two dependency deprecation warnings).
- Ruff checks passed for changed Python files.
- Browser checked desktop chat, collapse/expand, dashboard, and mobile quiz form/navigation at 390px.
- Live configured provider generated five Python questions; selecting and checking an answer displayed its explanation and source.
- Known catalog topics now retrieve exact course passages without loading embeddings. Unknown topics retain semantic retrieval and the groundedness gate.
- Course picker defaults to an enrolled course with materials and labels courses without materials.
- Quiz progress remains in memory when switching workspace views; refreshing the page starts a new practice form. Scores are practice feedback, not institutional assessment grades.
- Strict server prompt specifies difficulty, one correct answer, four plausible options, exact question count, evidence-only facts and source references. Schema validation checks structure, count, distinct questions/options, answer membership and source IDs; it does not prove semantic correctness.
