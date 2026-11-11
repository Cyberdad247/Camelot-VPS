# Lisa's Custom Keychains — Cloudbrain Brief

*Compiled 2026-09-30. The working knowledge base for Lisa's Custom Keychains: the business, its systems, and its people.*

---

## The Business

- **What**: Handmade personalized engraved keychains — memorials, weddings, pet remembrances, gifts. Emotional commerce: trust and tenderness, not urgency.
- **Storefront**: https://lisascustomkeychains.com (headless Next.js + Shopify, hosted on Vercel)
- **Etsy**: lisascustomkeychainz.etsy.com (legacy link; IG bio still points here — fix pending)
- **Instagram**: @lisascustomkeychains — 37 posts, 88 followers (as of 2026-09-24), personal account type, empty bio
- **Trust signals**: USA Made · 7-Day Turnaround
- **Domain**: bought at Namecheap, DNS via Cloudflare, hosted on Vercel

## Product Lines

- Custom engraved keychains (core)
- Signature sets
- Sports-themed pieces
- Earrings — homepage trimmed to the single Handcrafted Heart Bead Earring (matches hero feature); others remain live in Shopify, hidden from homepage only
- Bulk / corporate orders (10+ pieces) — Sir BoB collects these as quote requests

## Systems

### Storefront (Cyberdad247/LisaCustomKeychains.com)
- Next.js 16 app on Vercel, Shopify-backed headless
- **Sir BoB** — AI account-manager knight (Qwen3-4B brain on VPS via Cloudflare tunnel at bob.lisascustomkeychains.com)
  - Shopper mode: warm artisan executive, answers only from the verified catalog, defers unknowns to Lisa
  - Chamberlain mode (`/api/bob/owner-chat`): Queen Lisa's personal assistant — business advice, quote summaries, marketing and production ideas
  - Public endpoints: `/api/bob/chat`, `/api/bob/quote` (per-IP rate limited)
  - Owner-gated: `/api/bob/owner-chat`, `/api/bob/quotes` (quote inbox)
  - Quote flow: customer submits → stored in VPS `quotes.jsonl` → ntfy phone alert to operator

### Shopify Admin App (Cyberdad247/lisa-shopify-app + lisa-shopify-app-sandbox)
- Private embedded Shopify admin app — installed in the store, kept alive deliberately
- Sandbox has Client Ops dashboard: client profiles, frontend controls (hero, announcement bar, featured products), backend workflow checklists, delivery tracking
- North star: repeatable Shopify client operating system — config-first store maintenance

### Repos (post 2026-09-24 audit)
- `LisaCustomKeychains.com` — production storefront, active
- `lisa-shopify-app` / `lisa-shopify-app-sandbox` — embedded app, active (installed)
- `LisaCustomKeychains-v2` — archived
- `lisa-dev-dashboard` — archived
- 25 stale Dependabot PRs on the Shopify app repos — cleanup pending

## People

- **Lisa** — the woman behind the business. The user builds and runs her storefront, repos, and social growth.
- **The user** — builder and operator of the business's web presence; drives business decisions.

## Active Goal

**Lisa's Custom Keychains social expansion** — grow on social to drive gift orders. Three phases: (1) stabilize IG (bio, business profile, M/W/F cadence), (2) expand visibility (engraving timelapses, reels, Pinterest), (3) scale through holidays (scheduled content, DM lead bot). See the Marketing Notebook for the full playbook.

## Key Rules

- Never use the "Lisa x PlayStation collab" claim — that research refers to the pop star Lisa, not this business.
- No countdown timers or urgency tactics on memorial/remembrance pieces.
- Memorial content: empathetic, never exploitative; keep grief targeting organic (Meta ad policy).
- Social writes (posts, bio changes, DMs) and ad spend always need explicit approval per item.
# Lisa's Custom Keychains — Marketing Notebook

*Compiled 2026-09-30. Drawn from the NotebookLM "Strategic Social Media Launch Plan" notebook, the integrated social-media-knight playbook, and Sir BoB's chamberlain counsel.*

---

## Source Notebooks

- **NotebookLM**: "🔑 Lisa's Custom Keychains: Strategic Social Media Launch Plan" (Mar 30, 2026) — 23 sources: 7 product photos, 2 PDFs (strategic blueprint, recommendations), site pages, FB post, Public Square Farmers Market material. Audio overview: "Scaling Lisa's Custom Keychains with emotional commerce" (24:30).
- **Core thesis**: emotional commerce — memorials, weddings, and gifts convert on trust and tenderness. The engraving process itself is the content.

---

## Phase 1 — Stabilize (Days 1–7)

- **Bio**: "Personalized engraved keychains ❤️ Memorials · Weddings · Gifts — Shop below 👇" → link to lisacustomkeychains.com (or a Beacons/Linktree hub: Home, Weddings, Pet Memorials, Custom Orders)
- **Account**: convert to professional/business for insights + contact buttons
- **Cadence**: Mon / Wed / Fri — rotate product spotlight → story/reel → testimonial
- **Cross-post**: adapt FB posts natively for IG, don't mirror verbatim
- **Baseline**: record followers, reach, profile visits on day 1 — everything later compares against this

## Phase 2 — Visibility (Weeks 2–4)

- **Pick winners with data**: pull IG insights first, then repurpose the actual top memorial post into a carousel + Pinterest pin. Never guess.
- **Copy anchors**: "Hold their memory close." Gentle, non-exploitative tone on memorial/pet-loss pieces.
- **Micro-content**: 15-sec engraving timelapses as Stories; stitch into TikTok teasers. Batch-shoot a week's worth in one session — daily filming isn't sustainable solo.
- **Hashtags**: rotating 10-tag template by occasion; always #CustomKeychain #PersonalizedGifts #PetMemorialGift #HandmadeUSA

## Phase 3 — Scale Through Holidays (Oct–Dec 2026)

Q4 is peak personalized-gift season — the real north star.

- **Omnichannel**: IG + TikTok (process videos) + Pinterest (inspiration boards) + YouTube (engraving tutorials)
- **Trust signal** everywhere: "Lisa's Custom Keychains – USA Made – 7-Day Turnaround"
- **Tracking**: UTM params on every outbound link (`utm_source`, `utm_medium`, `utm_campaign`)
- **Scheduling**: start free with Meta Business Suite; pay for Buffer/Hootsuite only if free limits bite
- **DM lead bot** (e.g. ManyChat): auto-reply on intent keywords ("Wedding favors? Here's our quick quote link"), collect emails for repeat-gift campaigns

---

## Sir BoB's Chamberlain Counsel (2026-09-30)

*Marketing — turning the admin app into a growth engine:*

1. **Seasonal campaign calendar in the app** — pre-write Halloween/Black Friday/Christmas hero + announcement copy now; one-click activation via the existing frontend controls.
2. **Featured product ↔ Instagram pairing** — when the Monday timelapse posts, the storefront's featured slot already shows that piece. Deliberate, every week.
3. **Wholesale pipeline** — Sir BoB's bulk quote requests need a home: build a wholesale panel in the admin app for corporate gifting season.
4. **Review flywheel** — order webhook asks for a review post-delivery; approved reviews feed a storefront testimonials section. Social proof, compounding.

*Production — making the app produce more:*

1. Finish the task ledger in order: client profile form + Prisma persistence → storefront config export (single source of truth) → Vercel deployment checks.
2. **Bulk product creator** — graduate the smoke test: a Christmas drop of 20 keychains as one CSV upload, descriptions templated.
3. **Low-stock alerts** — webhook before a bestseller sells out mid-campaign.
4. **Clear the 25 stale Dependabot PRs** — a sandbox that can't build cleanly can't ship when it matters.

---

## Operating Boundaries

- Every phase gates on the previous phase's data — no scaling what wasn't measured.
- Drafts and plans are free; publishing, bio changes, DMs, and ad spend need explicit approval per item.
- Memorial products: no urgency tactics, ever.
