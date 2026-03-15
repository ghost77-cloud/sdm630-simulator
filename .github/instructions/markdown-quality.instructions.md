---
name: "markdown-rules"
description: "Rules for writing clean, lint-compliant Markdown documents (markdownlint / markdownlint-cli2)."
applyTo: "**/*.md"
---

# Markdown Quality Standards

Follow these rules when creating or editing Markdown documents to ensure compliance with markdownlint.

## Document Structure

- **One H1 per document** on the very first line (MD025 `single-h1`, MD041 `first-line-h1`)
- **Never skip heading levels** — go H1 → H2 → H3, not H1 → H3 (MD001 `heading-increment`)
- **Use ATX-style headings** (`# Heading`) consistently (MD003 `heading-style`)
- **Headings must start at column 1** — no leading spaces (MD023 `heading-start-left`)
- **No duplicate sibling headings** at the same level (MD024 `no-duplicate-heading`)
- **No trailing punctuation** in headings such as `.`, `:`, or `!` (MD026 `no-trailing-punctuation`)

## Blank Lines (Most Common Violation Source)

Blank lines are required around block-level elements:

- **Before and after headings** (MD022 `blanks-around-headings`)
- **Before and after lists** (MD032 `blanks-around-lists`)
- **Before and after fenced code blocks** (MD031 `blanks-around-fences`)
- **No multiple consecutive blank lines** — maximum one (MD012 `no-multiple-blanks`)

## Code Blocks

- **Always specify a language** for fenced code blocks: `` ```python ``, `` ```bash ``, `` ```json `` (MD040 `fenced-code-language`)
- Use `` ```text `` for plain, unformatted output
- **Use consistent fence style** — backticks (`` ``` ``) or tildes (`~~~`), not mixed (MD048 `code-fence-style`)

## Whitespace and Indentation

- **No trailing spaces** at end of lines (MD009 `no-trailing-spaces`)
- **No hard tab characters** — use spaces for indentation (MD010 `no-hard-tabs`)
- **Indent nested list items by 2 spaces** (MD007 `ul-indent`)
- **No spaces inside emphasis markers** — `*bold*` not `* bold *` (MD037 `no-space-in-emphasis`)
- **No spaces inside link text** — `[link](url)` not `[ link ](url)` (MD039 `no-space-in-links`)

## Lists

- **Use a single, consistent list marker** — `-` is preferred; do not mix `-`, `*`, and `+` (MD004 `ul-style`)
- **Ordered lists must use sequential numbering** — `1.`, `2.`, `3.` (MD029 `ol-prefix`)

## Links, URLs, and Images

- **No bare URLs** — wrap in angle brackets `<https://example.com>` or use a descriptive link `[Example](https://example.com)` (MD034 `no-bare-urls`)
- **No empty links** — every link must have a destination (MD042 `no-empty-links`)
- **Images should have alt text** — `![description](image.png)` not `![](image.png)` (MD045 `no-alt-text`)

## Tables

- **Pad cells with spaces** — `| Column | Column |` not `|Column|Column|`

## Line Length

- Keep lines under **80 characters** where possible (MD013 `line-length`)
- Lines with long URLs (no internal whitespace) are automatically exempt
- This rule can be relaxed per-project via configuration

## File Ending

- **File must end with a single newline** character (MD047 `single-trailing-newline`)

## Horizontal Rules

- **Use a consistent style** — `---` is recommended (MD035 `hr-style`)

## Inline HTML

- **Avoid inline HTML** — use Markdown syntax instead (MD033 `no-inline-html`)
- If inline HTML is necessary (e.g., comments), document the exception in config

## Validation

Run the linter before committing:

```bash
npx markdownlint-cli2 "**/*.md"
```

Auto-fix supported violations:

```bash
npx markdownlint-cli2 --fix "**/*.md"
```

## Configuration

Place a `.markdownlint-cli2.yaml` in the project root to customise rules:

```yaml
config:
  default: true
  MD013:
    line_length: 500
    code_blocks: false
    tables: false
  MD033: false
```
