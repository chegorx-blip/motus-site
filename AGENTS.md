# Agent Rules (Modular)

---

## MANDATORY FIRST STEP — EVERY REQUEST

Before responding to ANY user request, you MUST read `AGENTS.md` in full first.
- No exceptions. This applies to every message, not just session start.
- If `AGENTS.md` is already in your context from a Read earlier in THIS session, you may skip re-reading.
- Do not answer, plan, or call other tools until `AGENTS.md` has been read this session.

## Verification Approach (Risk-Based)

### Level 1 (Первый уровень) - READ ONLY (Low Risk)

**Use for:** Reading files, exploration, answering questions

**Process:**
- Read the file
- Answer based on what you see
- No detailed verification needed

**Examples:**
- "Что в этом файле?"
- "Дай суть этого документа"
- "Найди упоминания X"

---

### Level 2 (Второй уровень) - LIGHT VERIFICATION (Default)

**Use for:** Most routine work, simple edits, documentation

**Process:**
- Read the file before editing
- Note source with file/line numbers
- Mark unknowns with `[PLACEHOLDER: owner]`
- Show what will change before editing
- If both input and output files have legal data (numbers, addresses, account details) and prompt asks to "make the same"/"сделай по образцу"/"возьми за основу" - never generate them, write scrypts to copy them symbol-to-symbol

**Examples:**
- "Добавь X в документ"
- "Обнови указанный файл"
- "Измени форматирование/стиль"
- "Создай файл на основе файла X"
- "Создай файл взяв за пример файл X"

---

### Level 3 (Третий уровень) - FULL VERIFICATION (Critical)

**Use for:** Source-of-truth documents, multi-file changes, architecture

**Process:**
- Read + quote specific lines
- Grep to find ALL instances
- List questions before documenting
- Mark interpretations as `[INFERRED: требует уточнения]`
- Wait for explicit confirmation

**Examples:**
- API specifications
- Architecture decisions
- Pricing or financial data
- Database schemas
- Multi-file refactoring

---

### Decision Heuristic

**Ask:** "If I get this wrong, would it cause incorrect decisions or lost money?"

- **YES** → Level 3
- **NO** → Level 2
- **Just exploring** → Level 1

**Default:** Level 2. When in doubt, ask user.

### Verification Checklist (Level 3)

1. [ ] Read all affected files
2. [ ] Grep for all instances of what's changing
3. [ ] List what you found
4. [ ] Confirm with user before proceeding
5. [ ] Show what changed after editing
6. [ ] Wait for approval before committing

---

## Anti-Hallucination & Source Tracking

### Core Principle

Every statement must have a clear, traceable source which is always given - either in project or internet.
Eliminate ambiguities, duplicates, inconsistencies, and unclear sources.

### Source Tracking Markers

| Marker                           | Meaning                  | When to Use                       |
|----------------------------------|--------------------------|-----------------------------------|
| `[CANONICAL]`                    | Authoritative definition | First/only place info is defined  |
| `[REF: file.md#section]`        | Reference to canonical   | When citing info from elsewhere   |
| `[CONFIRMED: source]`           | Verified information     | Info from team/stakeholders       |
| `[PLACEHOLDER: owner]`          | Info to be filled        | Unknown info with clear owner     |
| `[INFERRED: needs verification]`| Interpretation           | When making assumptions           |
| `[DEPRECATED]`                  | Old information          | Kept for reference, not current   |

### Anti-Hallucination Rules

1. **Eliminate Hallucinated Content** — Remove any information not confirmed by reliable sources
2. **Use Real Data** — Specific specs and requirements from actual documentation
3. **Source Every Statement** — Every claim must be `[CANONICAL]` or `[REF:]`
4. **Mark Placeholders** — Clear ownership for missing info: `[PLACEHOLDER: Product Team]`
5. **Date Everything** — Include "Last Updated" timestamps

### Common Error Sources (AVOID)

- Using "planned" values instead of "actual" values
- Remembering old values from earlier in conversation
- Assuming details without checking
- Making changes without reading current file state
- Documenting guesses as facts

### Before Documenting, Ask:

1. [ ] Where did this information come from?
2. [ ] Is it `[CANONICAL]` here or `[REF:]` to elsewhere?
3. [ ] Is there a more authoritative source?
4. [ ] Am I inferring? If yes, mark `[INFERRED]`
5. [ ] Is this up to date?

---

## Git Workflow Guidelines

### Core Principle

User controls all git operations. AI never commits or pushes without explicit permission.

### NEVER Do
- Push without explicit user confirmation
- Commit until user indicates completion
- Edit CLAUDE.md without explicit request
- Force push unless explicitly requested
- Auto-commit after every small change

### ALWAYS Do
- Show `git status` or changes summary before committing
- List what files changed and what was modified
- Wait for explicit user approval before committing
- Write clear, descriptive commit messages
- Suggest commits when coherent set of changes is ready

### Commit Flow

```
1. User completes logical piece of work
   ↓
2. AI: "Ready to commit these changes?"
   ↓
3. AI: Shows git status / changes summary
   ↓
4. User: "Yes" / "Go ahead"
   ↓
5. AI: Commits with descriptive message
   ↓
6. AI: Shows commit result
   ↓
7. AI: "Want me to push to remote?"
   ↓
8. User: "Yes" / "Push"
   ↓
9. AI: Pushes and confirms
```

### Commit Message Format

```
[Type]: Brief description
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code restructuring
- `chore:` Maintenance