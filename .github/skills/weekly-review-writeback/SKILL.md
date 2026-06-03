---
name: weekly-review-writeback
description: 'Write a structured weekly review into review_weekly_reviews. Use for weekly review persistence, plan-vs-reality week conclusions, and next-week plan decisions.'
user-invocable: false
---

# Weekly Review Writeback

This skill packages the contract and script for writing one row into `review_weekly_reviews`.
It also writes a markdown logbook file for the same assessment under the season folder.

## When To Use

- The user explicitly wants to save a weekly assessment.
- The user wants to write a next-week decision into the database.
- The user wants a dry-run preview before persisting a weekly review.
- The request arrives as a persistence handoff from `Weekly Performance Coach` after a concrete week assessment.
