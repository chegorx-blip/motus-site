# Companion tooling not installed

The original Superpowers plugin (obra/superpowers-skills) ships ~90 skills as one bundle. This project installed only 5, picked for the CRM/bot/website work ahead: `test-driven-development`, `brainstorming`, `writing-plans`, `systematic-debugging`, `verification-before-completion`.

Referenced in the original TDD skill but **not installed here**:
- `testing/condition-based-waiting` — replacing timeout-based waits in tests with condition polling
- `debugging/defense-in-depth` — adding validation layers after a root cause is found

If a task needs one of these (or any of the other ~85 skills in the pool — architecture, research, git worktrees, parallel agents, code review, etc.), pull the specific `SKILL.md` from https://github.com/obra/superpowers-skills/tree/main/skills (MIT license, same process used to install these 5) rather than installing the whole library.
