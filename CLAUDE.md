@AGENTS.md

## Claude Code 向け補足

- `.claude/skills/` は案内のみで、スキルの本体は `.agents/skills/`（Codex と共用）。スキルを編集するときは本体を直し、`python python/cli.py sync-skills` を実行する。
- music-composition-skills をプラグインとして導入している場合は、作曲の設計（ARR-SPEC）にそのワークフローを使う。
