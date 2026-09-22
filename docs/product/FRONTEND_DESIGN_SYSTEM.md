# Frontend Design System — v1 Foundation

Related: #68, #69

## Purpose

The frontend must behave like one enterprise product, not a collection of unrelated pages.

This foundation standardizes the visual and interaction primitives used by customer-facing pages while keeping authorization and business rules in the backend.

## Principles

1. **Persian-first / RTL-safe**
   - Primary product UI is Persian/RTL.
   - UUIDs, hashes, IPs, URLs, codes and other technical identifiers remain LTR where required.
2. **No fake business data**
   - Loading, empty and error states are explicit.
3. **Backend authorization remains authoritative**
   - A hidden button is not an authorization control.
4. **Accessible by default**
   - Visible focus, label associations, keyboard operation and non-color-only states.
5. **Shared primitives before one-off styling**
   - New screens should use the shared UI layer before adding page-specific controls.
6. **Operational clarity over decoration**
   - Status, scope, source, owner, due date and next action should be understandable.

## Shared primitives

Implemented in `frontend/components/ui.tsx`:

- `Button`
- `Input`
- `Select`
- `Textarea`
- `FormField`
- `StatusMessage`
- `Surface`
- `PageHeader`
- `EmptyState`
- `TechnicalText`

Base tokens and layout helpers live in `frontend/app/design-system.css`.

## Tokens

The CSS custom properties under `:root` are the canonical v1 foundation for:

- colors and semantic states;
- border and surface hierarchy;
- radii;
- spacing;
- focus treatment;
- typography;
- control height;
- shadows.

Page-specific CSS may extend these values but should not duplicate a competing token system.

## Form rules

- Every interactive form field needs a visible label.
- Required state must be visible without relying on placeholder text.
- Validation errors appear next to the field or in a clearly actionable page-level message.
- Busy/disabled state must prevent duplicate user actions where appropriate.
- Technical values use an LTR-safe presentation.

## Table/list rules

Production register pages should have:

- meaningful search/filter controls where useful;
- loading, empty and error states;
- horizontal overflow safety;
- accessible actions;
- server-backed pagination for unbounded datasets;
- drill-down to the authoritative record.

## Migration strategy

The design system is adopted incrementally:

1. security-sensitive entry flows (login/MFA);
2. representative register/form pages (Assets);
3. shared shell/navigation;
4. remaining GRC modules;
5. final Figma/product visual parity and accessibility pass.

Do not perform a risky big-bang rewrite of every page in one pull request.
