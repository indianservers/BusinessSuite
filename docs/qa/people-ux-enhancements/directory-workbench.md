# Member directory workbench

Implementation inventory for the directory enhancements. Existing people/profile behavior is retained alongside the new destination workbench.

1. Rounded member cards with subtle depth and consistent spacing.
2. Hover lift and shadow animation.
3. Reduced-motion support.
4. Always-visible member selection controls.
5. Distinct selected-card border and background.
6. Consistent avatars with image-error fallback initials.
7. Wrapping member names and email tooltips.
8. Classification, employment, department and skill badges.
9. Current project summary on cards.
10. Expandable workspace, team, batch and project membership details.
11. Member preview drawer without leaving directory context.
12. Quick actions exposed on hover and keyboard focus.
13. Single-member native card drag payload.
14. Drag payload for the selected group of members.
15. Project drop destinations.
16. Team drop destinations.
17. Batch drop destinations.
18. Drop hover feedback and stable destination selection area.
19. Unavailable destination explanations and full-batch checks.
20. Review preview before membership writes.
21. Add membership while retaining existing memberships.
22. Transfer from an explicitly selected source.
23. Checkbox and button assignment alternative for keyboard and touch.
24. Bulk project additions.
25. Bulk team additions.
26. Bulk batch additions.
27. Bulk removal with open-work handover safeguards.
28. Bulk project Member and Viewer role changes.
29. Bulk task creation using the selected people.
30. Export selected people, current page or all filtered results.
31. Selection retained across pagination and presentation changes.
32. Selection review and individual removal before bulk actions.
33. Individual result rows with reasons.
34. Review and retry only failed members.
35. Assignment audit records and profile history access.
36. Five-minute undo for eligible additions with subsequent-change guards.
37. Searchable destination list.
38. Pinned destinations scoped to account and organization.
39. Recent destinations scoped to account and organization.
40. Destination member counts, avatars, leads, dates and batch capacity.
41. Existing-membership comparison for the selected people.
42. Open and overdue workload summaries before assignments.
43. Sticky bulk operation toolbar.
44. Unified people search across identities, groups and skills.
45. Quick employee, intern, unassigned and needs-attention filters.
46. Saved views include layout, density and table column selection.
47. Comfortable, compact and detailed density choices.
48. Collapsible destination panel.
49. Responsive destination sheet with explicit close action.
50. Shareable filtered URL, refresh preservation, loading states and accessible focus controls.

## Validation

- Existing people workspace and person management tests: 16 passed.
- New directory action tests: 8 passed, covering destination and tenant scope, duplicate additions, stale previews, transfer and removal guards, mixed batch failures, selected exports, project roles, capacity, transfer history and edited-membership undo guards.
- Frontend TypeScript and targeted ESLint checks passed.
- Local Chrome QA fixture: assignment preview, persisted project addition, successful undo, updated destination count, intern preview details and return to directory were observed.
- Native drag and responsive sheet visual verification remain incomplete. Computer Use stopped because it could not determine the active browser URL reliably. A route update on drag start was removed after the drag attempt; the final drag correction has code checks but no completed browser recheck.

## Operational limits

Up to 100 people and 10 destinations, with at most 500 combinations per request. Transfers require one target and an explicit source. Removal and access reduction with open work require handover through Manage person. Bulk project role changes support Member and Viewer; protected roles require the existing person-management workflow. Undo applies only to additions, expires after five minutes and rejects subsequent membership edits or dependent work. Changes are local and have not been deployed.
