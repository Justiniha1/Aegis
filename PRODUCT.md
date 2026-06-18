# Product

## Register

product

## Users

Data operators and client teams who own a dataset's health. They open Comet to answer one question fast: "is my data OK right now, and if not, what broke?" Context is a working session, often glancing between Comet and other tools, sometimes triaging a failed scheduled run. They are technical enough to read a table name, a SQL snippet, and a metric, but they are not living in the tool all day.

## Product Purpose

Comet runs data-quality checks against a client's database (on demand or scheduled) and shows the results. Success is: an operator can see at a glance whether their data is healthy, and act on what's broken, without digging. The History surface specifically answers "what happened across past runs, and why did a given run fail or produce failures?"

## Brand Personality

Calm operator precision. Trustworthy, legible, fast. The interface earns confidence by getting out of the way: clear hierarchy, honest status, no decoration that doesn't carry meaning. Voice is plain and specific, never marketing.

## Anti-references

- Chunky, identical card grids as the primary list affordance.
- Marketing flash: gradients-as-decoration, oversized display type, hero-metric templates, animated choreography on load.
- "Dashboard slop": tinted glass panels, side-stripe accent borders, status conveyed by color alone.

## Design Principles

- Status is the loudest signal. Health (passed / failed / error / skipped) reads instantly and is never carried by color alone.
- Density with hierarchy. Show many runs and many tests without noise; structure and weight do the sorting, not boxes.
- The failure is the story. When something broke, the run-level reason and the failing tests are the most prominent thing on the screen.
- Reuse the system. One status vocabulary, one set of components, identical screen-to-screen; surprise is a bug.

## Accessibility & Inclusion

WCAG AA: body text >=4.5:1, large text/UI >=3:1, verified in both dark and light themes. Status never by color alone (pair with label/badge/icon). Full keyboard operation for expandable rows and run selection; visible focus. All motion has a `prefers-reduced-motion` fallback.
