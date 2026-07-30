---
name: brainstorming
description: Turn a rough feature/project idea into a validated design through one-question-at-a-time questioning before any code or plan is written. Use when starting a new CRM feature, Telegram bot, website section, or branding build and the approach isn't decided yet.
license: MIT
metadata:
  derived_from: "https://github.com/obra/superpowers-skills/tree/main/skills/collaboration/brainstorming"
  original_author: "Jesse Vincent (@obra)"
  original_license: MIT
  original_version: "2.2.0"
---

# Brainstorming Ideas Into Designs

> Derived from [obra/superpowers-skills](https://github.com/obra/superpowers-skills/tree/main/skills/collaboration/brainstorming) (MIT). Adapted: the original's Phase 4 hands off to a "Using Git Worktrees" skill not installed in this project — skipped, this project works directly on the main branch per its own git workflow rules. Phase 5 hands off to [[writing-plans]] directly instead of offering a worktree-based parallel session.

## Overview

Transform rough ideas into fully-formed designs through structured questioning and alternative exploration.

**Core principle:** Ask questions to understand, explore alternatives, present design incrementally for validation.

**Announce at start:** "I'm using the Brainstorming skill to refine your idea into a design."

## The Process

### Phase 1: Understanding
- Check current project state in working directory
- Ask ONE question at a time to refine the idea
- Prefer multiple choice when possible
- Gather: Purpose, constraints, success criteria

### Phase 2: Exploration
- Propose 2-3 different approaches
- For each: Core architecture, trade-offs, complexity assessment
- Ask your human partner which approach resonates

### Phase 3: Design Presentation
- Present in 200-300 word sections
- Cover: Architecture, components, data flow, error handling, testing
- Ask after each section: "Does this look right so far?"

### Phase 4: Planning Handoff
Ask: "Ready to create the implementation plan?"

When your human partner confirms (any affirmative response):
- Announce: "I'm using the Writing Plans skill to create the implementation plan."
- Use the [[writing-plans]] skill

## When to Revisit Earlier Phases

**You can and should go backward when:**
- Partner reveals new constraint during Phase 2 or 3 → Return to Phase 1 to understand it
- Validation shows fundamental gap in requirements → Return to Phase 1
- Partner questions approach during Phase 3 → Return to Phase 2 to explore alternatives
- Something doesn't make sense → Go back and clarify

**Don't force forward linearly** when going backward would give better results.

## Remember
- One question per message during Phase 1
- Apply YAGNI ruthlessly
- Explore 2-3 alternatives before settling
- Present incrementally, validate as you go
- Go backward when needed - flexibility > rigid progression
- Announce skill usage at start
