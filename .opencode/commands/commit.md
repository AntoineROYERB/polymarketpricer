---
description: Generate Conventional Commit proposals from staged changes
---

Review the staged changes and propose the best Conventional Commit strategy.

Requirements:

- Use english only
- Analyze all staged changes.
- If changes are unrelated, propose splitting them into multiple commits.
- Generate 1-5 commit proposals using the format:
  `<type>(optional-scope): description`
- Choose the most appropriate type:
  - feat
  - fix
  - refactor
  - perf
  - test
  - docs
  - build
  - ci
  - chore
- Keep commit titles under 72 characters.
- Use imperative mood.
- Focus on why the change matters.
- Suggest logical commit boundaries when applicable.

For each proposal, provide:
- Commit message
- 0-5 bullet points summarizing the changes included in that commit

After the proposals, provide:

### Recommended action
- Create a single commit
- Split into multiple commits

### Execution options
1. First, Run all test and pre-commit checks then create the recommended commit(s)
2. Let me choose a proposal
3. Let me edit the commit message(s)
4. Cancel

Do not push.
Do not create commits automatically.
Only propose them and wait for confirmation.

All pre-commit checks must pass before any commit is created:
- Run `ruff check app/`
- Run `mypy app/`
- Run `python -m pytest app/tests/test_api/ -v`
---