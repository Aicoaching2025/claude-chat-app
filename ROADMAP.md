# Roadmap: from gated demo to self-serve product

## Where this stands today

The current app is a **gated demo for a handful of trusted people**: one
`ANTHROPIC_API_KEY` on the server, one shared `APP_ACCESS_CODE` everyone
uses to get in, an in-memory per-IP rate limit, and no accounts, database,
or billing at all. Conversation history lives only in the browser tab and
is gone when it closes.

## Target: strangers sign up on their own account

The decision (as of this writing) is to build toward genuine self-serve
access — anyone can create an account and use the product, not just people
who were personally given a code. That's a materially bigger build than
what exists today. This file is the punch list for that transition.

### 1. Accounts

- Real signup / login / logout / password reset, replacing the single
  shared `APP_ACCESS_CODE` entirely.
- Prefer a hosted auth provider (Clerk, Auth0, Supabase Auth) over rolling
  password hashing and session/token management by hand — that's a lot of
  security-sensitive surface to own for not much product value.
- Each request needs to resolve to a specific user, not just "has the
  code" — that identity is the foundation everything else below depends on.

### 2. Database

- A real database (Postgres, most likely) is required once there are
  accounts at all. Minimum tables: users, plans/subscriptions, per-user
  usage counters.
- Decide whether to persist conversation history server-side (needed for
  "pick up where I left off across devices") or keep it client-only
  (simpler, but users lose history on browser clear / device switch).

### 3. Billing

- Stripe Checkout + Billing for subscriptions.
- A webhook endpoint that updates a user's plan/status when they
  subscribe, upgrade, downgrade, or cancel — this is what the usage-limit
  logic (below) reads from.
- Decide the plan shape up front: flat monthly fee with a usage cap,
  metered/pay-as-you-go, or a free tier plus paid tiers. This affects the
  usage-tracking design, so decide before building it, not after.

### 4. Per-account usage limits (replaces the IP rate limiter)

- The current rate limiter is in-memory, per-process, per-IP — it doesn't
  know who a user is and won't work once there's more than one backend
  instance (each instance would track its own counts).
- Needs to become: per-account request/token quotas, tied to the user's
  plan, enforced server-side on every request, backed by a shared store
  (Redis, or the Postgres database) so it's consistent across instances.
- Without this, a single abusive or heavy-usage account can cost more than
  it pays — this is the part that protects your margin, not just abuse.

### 5. Legal and compliance (do this before taking money, not after)

- Terms of Service and a Privacy Policy — users are sending messages
  through a third-party API (Anthropic); they should know that, and you
  need the liability boundaries written down before charging anyone.
- Read Anthropic's usage policy for commercial products built on the API
  (platform.claude.com — usage policies section) — there are requirements
  around user-facing disclosures and prohibited use cases that apply to
  you as the operator.
- Decide and document a data-retention stance: how long conversations are
  kept, whether they're logged, and what GDPR/CCPA exposure looks like if
  EU/California users sign up.

### 6. Production hardening

- Structured logging and error monitoring (e.g. Sentry) so failures surface
  before users have to report them.
- Move all shared state (rate limits, sessions) off in-process memory —
  covered by the Redis/Postgres work above, called out again here because
  it's easy to ship without noticing an instance-count assumption baked in.

## Suggested build order

1. Accounts + database (nothing else is meaningful without user identity)
2. Per-account usage limits (protect margin before opening signups wider)
3. Billing (monetize once usage is actually being tracked per account)
4. Legal/compliance (must land before any real signups are allowed, not
   just before "launch")
5. Production hardening (ongoing, but prioritize before meaningful traffic)

This order front-loads the parts that are expensive to retrofit (identity,
database schema) and pushes billing until there's something real to bill
for.
