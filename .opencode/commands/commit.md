---
description: Generate a conventional commit message
---

Review the staged changes and create a single Conventional Commit message.

Requirements:

- Use the format: `<type>(optional-scope): description`
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
- Keep the title under 72 characters.
- Use imperative mood.
- Focus on why the change matters.
- If multiple unrelated changes exist, suggest splitting into separate commits.
- Output only:
  - Commit type
  - Commit message
  - 3-5 bullet points summarizing the changes
- Do not commit automatically.
- Do not add unnecessary explanations.