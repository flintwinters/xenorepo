# Calculator — Product Specification

## User problem and product intent

A person needs a small, dependable calculator for ordinary arithmetic without reaching for a
keyboard or carrying state between visits. The product succeeds when button input makes a complete
calculation obvious, mistakes are easy to clear, and exceptional arithmetic never breaks the
interface. Calculator is deliberately stateless: it stores no calculations, preferences, or
history.

## Feature inventory

- Button-only entry for digits, a decimal point, addition, subtraction, multiplication, and division.
- Immediate chained arithmetic, equals, sign inversion, percentage conversion, and all-clear.
- A legible display that distinguishes the entered value, pending operation, result, and error state.
- Conventional leading-zero and decimal handling with bounded display length.
- Explicit division-by-zero recovery and finite-number enforcement.
- A compact four-column keypad that remains usable at wide and narrow viewport sizes.

## Walking skeleton

The first shippable slice opens at zero. A user can enter decimal values with the on-screen buttons,
choose an operation, enter the next value, and see the result with equals. Selecting another
operation evaluates the pending operation before continuing, so multi-step arithmetic stays visible
and predictable. Plus/minus changes the displayed operand, percent divides it by one hundred, and
AC returns every state to zero. Division by zero shows `Error`; AC or the next digit starts a clean
calculation.

All calculation state lives in the active Preact component and disappears on reload. The FastAPI
service only serves the self-contained compiled application. MonoForm is not suitable because the
product has no records, transport, or CRUD workflow.

## Real-world pilot and acceptance

Use the running app, without a keyboard, to total two prices, apply a percentage as a decimal, run a
chained calculation, correct an entry with AC, and recover from division by zero. Confirm that a
reload returns to zero and that all controls and the complete display remain visible and comfortably
clickable on both wide and narrow screens.

Automated acceptance covers digit and decimal entry, all four binary operations, chained evaluation,
sign and percent transforms, leading-zero normalization, all-clear, division-by-zero recovery,
reload reset, absence of persistence, strict modular TypeScript compilation, self-contained FastAPI
delivery, and deterministic wide/narrow visual checks.

## Deferred scope

Keyboard entry, calculation history, memory registers, persistence, scientific functions,
parentheses, arbitrary precision, localization, currency conversion, and server-side calculation are
intentionally deferred. Calculator arithmetic remains app-owned until another app proves a shared
domain boundary.
