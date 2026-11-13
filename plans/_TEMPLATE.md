---
slug: <kebab-slug>
title: <title>
spec: specs/<kebab-slug>.md
size: T1
status: draft
created: <YYYY-MM-DDTHH:MM:SSZ>
---

# Plan: <title> (from specs/<kebab-slug>.md)

## 1. Goal and boundaries
<one-sentence goal; in scope this version; cut; deferred; success criteria>

## 2. Minimal acceptable loop
<the smallest end-to-end path that proves the goal>

## 3. Tech stack
none this version

## 4. Directory structure
none this version

## 4.5 Module design
<modules and their one-line responsibilities; a mermaid graph LR if useful>

## 5. Data model and state machine
none this version

## 6. Contracts and core interfaces
<APIs, events, schemas; frozen contracts named>

## Files that change
- <path/to/file.ts>
- <path/to/new-file.ts> (new)

## Order of work
1. <first bounded step; freeze/interface work first>
2. <next step>

## 7. Task split (dependencies and parallel windows)

| Card | Priority | Output | depends_on | Parallel window | Freeze point |
|---|---|---|---|---|---|
| T1-EXAMPLE-CONTRACT | MUST | <one-line output> | - | - | yes |
| T1-EXAMPLE-IMPL | MUST | <one-line output> | T1-EXAMPLE-CONTRACT | W1 | - |

## Risks
- <what could break: shared resources, rate limits, data contracts>

## Proof
- <test / screenshot / measurement per outcome>

## 10. After merge
none this version (development-only target)
