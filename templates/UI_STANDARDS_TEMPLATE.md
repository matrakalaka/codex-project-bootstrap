# UI_STANDARDS.md

## PURPOSE
Stable UI/UX implementation standards for this project.

## PRINCIPLES
- prioritize task clarity over decoration
- preserve information hierarchy
- keep actions discoverable
- provide visible feedback
- support keyboard use
- preserve readable contrast
- design responsive behavior intentionally

## ACCESSIBILITY
Dialogs/overlays should have:
- accessible role/name
- intentional initial focus
- keyboard traversal
- Escape behavior where appropriate
- focus restoration

Status feedback should have:
- visible feedback
- appropriate live-region semantics where required

## RESPONSIVE TARGETS
- Desktop:
- Tablet/compact:
- Mobile:

## FORMS
- persistent labels where appropriate
- stable control association
- clear errors
- no color-only state communication

## STATES
Consider:
- loading
- empty
- error
- success
- disabled
- selected/active

## THEME
If light/dark exists:
- use shared tokens
- keep focus visible in both themes
- maintain readable status/control contrast

## VALIDATION
Use Playwright or equivalent for objective rendered behavior:
- keyboard
- focus
- dialog semantics
- responsive regressions
- theme regressions
- screenshots

Subjective visual approval remains a human review step.
