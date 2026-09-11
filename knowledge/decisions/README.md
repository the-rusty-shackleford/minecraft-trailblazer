---
title: Trailblazer — decisions log
type: index
layer: store
tags: [index]
---

# Trailblazer — decisions log

**Append-only.** Never edit an entry's rationale; supersede via a new entry with
`supersedes: D-NNNN`. Every entry has a status: `Active` / `Superseded` / `Rejected`.

| Id | Topic |
|----|-------|
| D-0001 | The cab repair is a scripted edit of the bundle, not a re-export and not a runtime fix |
| D-0002 | The truck is designed as a Blockbench project in code, to the reference, and reviewed as renders (supersedes D-0001) |
| D-0003 | The hand-built Blockbench project is the truck; `adopt.py` splits it and reads the profile off it (supersedes D-0002) |
