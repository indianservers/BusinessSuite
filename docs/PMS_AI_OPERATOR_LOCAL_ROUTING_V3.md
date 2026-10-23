# Local PMS actions and follow-ups — model v3

Implemented 24 October 2026. The standard TensorFlow.js model is retrained on **945 curated examples across 36 intent classes**, expanding the v2 corpus of 512 examples and 24 classes. The classifier is still a bounded intent router with strict parsers and local dialogue state, rather than a generative local LLM.

Model files remain `frontend/public/models/operator/model.json` and `frontend/public/models/operator/weights.bin`. Run `npm run train:operator` from `frontend` to regenerate both. Training now runs 400 seeded epochs, checks corpus accuracy and a minimum confidence gate, then reloads the saved files and verifies equivalent predictions. Corpus accuracy is 100% for this release; this is not a generalization or confidence-calibration guarantee. Independent browser tests exercise unseen business text and the conversation flows.

## Added local actions

```text
rename task to "Review checkout"
set description to "Check error handling and acceptance criteria"
set estimated hours to 3.5
set story points to 8
add comment "Ready for QA"
complete checklist item "QA review"
reopen checklist item 31
remove checklist item 32
create milestone "Client handoff" due next Friday
move tasks to sprint "Release"
```

These use existing PMS operations. Comments are internal, plain text; the comment operation retains normal authorized in-app mention behavior. Checklist actions resolve an exact item ID or title inside the selected tasks, or the current authorized project when no task is selected. Duplicate titles produce numbered choices. Named sprint resolution excludes completed sprints, and duplicate names produce numbered choices. Truncated context requires an explicit listed ID instead of assuming that a name is unique.

Task estimates accept 0–10000 hours with at most two decimal places. Story points accept whole numbers from 0–1000. Task titles and checklist titles are bounded at 220 characters; descriptions/comments are bounded at 8000 characters by their tools, and command input retains its existing 4000-character limit.

Quoted business text is preserved and displayed before approval. Qualifiers such as “unless blocked” continue to require contextual reasoning; the local parser must consume the complete request rather than silently omit a condition. Compatible task actions can still be combined in the existing bounded multi-step grammar.

## Added follow-up flows

Bare commands now ask for missing information:

```text
User: rename task
Assistant: What new task title should I use?
User: Review checkout
Assistant: [exact rename plan for review]

User: set estimated hours
Assistant: How many estimated hours?
User: actually 3.5 hours
Assistant: [exact estimate plan for review]

User: set priority
Assistant: Which priority? Choose Low, Medium, High, Urgent.
User: Urgent
Assistant: [exact priority plan for review]

User: complete checklist item "QA review"
Assistant: Which checklist item did you mean? [numbered matches]
User: the second one
Assistant: [the selected item's completion plan for review]
```

Descriptions, story points, comments, checklist titles, status, sprint selection and milestone names also have local follow-up questions. If a complete supported task command has no task selection, the assistant asks for a task key/ID and then completes that command locally. Exact task-title matches are accepted only when unique in complete context; ambiguous titles produce choices. Common corrections such as “actually 5 hours”, “use the second one” and “High instead” are accepted for typed slots without rewriting free-text titles or comment bodies.

The assistant reports when no checklist items or active sprints are available, instead of repeatedly asking for an impossible choice. Help and cancellation remain local. A conversational “yes” never executes work. Dialogue remains in browser memory and retains the original command time/timezone while fields are completed.

## Revising pending plans

Local revisions retain other pending work. A refined task field replaces the same field in pending steps; for example, changing a proposed status removes the earlier proposed status rather than applying both and firing intermediate status automations. An explicit “also…” appends the new action. Checklist completion/removal refinements replace prior pending changes to the same item.

Committed receipt positions are excluded from the revised plan, so completed checkpoint effects are not repeated. Remaining steps use sequential dependencies after filtering. The original task selection remains frozen, and plans above 75 steps require reduction or a separate command. Every revision receives a new preview/hash/approval and invalidates the old pending approval through the existing backend revision checks.

## Execution and verification

`TaskChanges` now permits title, description, estimated hours and story points. New typed tools are `update_checklist`, `remove_checklist` and `add_comment`. The operator calls the same canonical PMS operations with commits deferred to its transaction; normal HTTP endpoints preserve their existing commit behavior. Backend validation verifies checklist item ownership, permissions, schema bounds and task fingerprints before execution. Task fingerprints now explicitly include description, estimates and story points, with stable numeric normalization across checkpoint commits.

Existing pending previews created before this change may fail the expanded fingerprint check; create a new preview rather than bypassing stale-plan protection. There is no new database migration in this slice. Existing operator migrations and the worker are still required for the established background execution paths.

Automated verification covers synchronous, atomic background and checkpointed execution of the new tools, replay without duplicate comments, stale checklist rejection, cross-task item rejection, real saved-model browser inference, missing-field questions, ambiguity selection, milestone dates, named sprints, no-selection follow-ups, and revision merging without replaying committed work. No live provider calls or production deployment were performed.
