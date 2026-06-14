---
name: block-review-writeback
description: 'Write a structured block review into review_block_reviews. Use for block review persistence, block closure conclusions, and next-block decisions.'
user-invocable: false
---

# Block Review Writeback

This skill packages the contract and script for writing one row into `review_block_reviews`.
It also writes a markdown logbook file for the same assessment under the season folder.

## When To Use

- The user explicitly wants to save a block assessment.
- The user wants to write a next-block decision into the database.
- The user wants a dry-run preview before persisting a block review.
- The request arrives as a persistence handoff from `Block Performance Coach` after a concrete block assessment.
