# AI Agent Use Cases for Listing Hub

This specification defines the canonical interaction patterns, decision loops, and safety invariants for AI Agents operating with **Listing Hub**. All workflows strictly employ the Ubiquitous Language established in [CONTEXT.md](../CONTEXT.md).

---

## UC-1: Analyze Dropped Photos & Prepare Draft with Market Price Recommendation

### 1. Description & Intent
The Agent processes a batch of raw photographic assets provided by the seller, performs multimodal visual inspection, queries real-time market data across classified portals, and initializes an uncommitted `Draft` listing with clean copy, pre-selected category, and structured pricing options.

### 2. Primary Actors
- **Seller**: Private individual (Ondřej Hála) providing item photos and optional high-level notes.
- **AI Agent**: Autonomous assistant executing visual extraction, market analysis, and draft synthesis.

### 3. Domain Entities & Operations Involved
- **Entities**: `PhotoAsset`, `Listing`, `ListingStatus` (`Draft`), `SubdomainCategory`, `MarketRadarAnalysis`.
- **Value Objects**: `PricePoint`, `PriceRecommendation`, `ContactProfile`.
- **Operations**: `AnalyzePhotos`, `ProbeMarketRadar`, `DraftAd`.

### 4. Preconditions
- One or more `PhotoAsset` files exist in a local intake directory or clipboard stream.
- Valid multimodal AI API credentials and network access to classified portals are present.
- Default `ContactProfile` is configured (seller identity coordinates, preferred delivery terms).

### 5. Interaction Flow
1. **Photo Asset Ingestion**:
   - The Agent registers uploaded image files as `PhotoAsset` instances.
   - Checks image validity, normalizes EXIF orientations, and validates that file paths reside strictly within designated storage boundaries.
2. **Multimodal Visual Inspection (`AnalyzePhotos`)**:
   - The Agent submits the photo batch to multimodal vision inference.
   - Extracts: brand, exact model name, serial numbers, visible wear/condition, included accessories, and key specifications.
   - Evaluates framing and background clarity to assign the optimal cover photo index.
   - Generates 3 to 5 candidate titles strictly constrained to <= 50 characters (optimized for click-through rate without truncation).
   - Generates plaintext body copy formatted with uppercase headers (`STAV:`, `PARAMETRY:`, `PŘÍSLUŠENSTVÍ:`) and dash bullet points, strictly excluding markdown asterisks (`*`, `**`). Appends default delivery and handover preferences from `ContactProfile`.
3. **Market Valuation Sampling (`ProbeMarketRadar`)**:
   - The Agent constructs clean keyword queries from extracted brand and model data.
   - Samples active competitor listings across regional marketplace portals (Bazoš.cz, Sbazar.cz, Web).
   - Filters out extreme outliers and identical duplicates.
   - Calculates competitive statistical distribution (minimum, maximum, median).
   - Synthesizes a `PriceRecommendation` containing:
     - **Quick Sale**: Median minus 10% for fast liquidation.
     - **Fair Market**: Calculated median of active listings (default recommendation).
     - **Premium**: Median plus 10% for items in mint condition, with complete accessories, or under warranty.
4. **Category & Routing Resolution**:
   - The Agent determines the appropriate `SubdomainCategory` (e.g., `dum.bazos.cz`, `elektro.bazos.cz`, `stroje.bazos.cz`) based on keywords and item taxonomy to prevent portal page reloads.
5. **Draft Initialization (`DraftAd`)**:
   - The Agent persists the compiled payload into local database storage with `ListingStatus` set to `Draft`.
6. **Agent-to-User Presentation**:
   - The Agent presents a concise summary to the seller:
     - Recommended title variants (showing character counts).
     - Identified condition and detected accessories.
     - Tri-level pricing recommendations with source sample counts.
     - Proposed `SubdomainCategory`.

### 6. Postconditions & Invariants
- A new `Listing` record exists with status `Draft`.
- No network requests have been sent to publish or alter external marketplace state.
- Form copy contains zero unsupported formatting characters (no markdown bold/italic asterisks).
- All photo paths are verified within the secure local photo directory.

### 7. Edge Cases & Safety Gates
- **Illegible or Missing Model Label**: If the vision model cannot resolve the exact model, the Agent flags the title with a placeholder, prompts the seller for clarification, and falls back to category-level price ranges.
- **Zero Competitor Hits**: If classified search returns fewer than 2 items, the Agent supplements the radar with broader web searches and AI price modeling, explicitly notifying the seller of reduced confidence.
- **Path Traversal Guard**: Any photo path containing directory traversal tokens (`../`) is instantly rejected.

---

## UC-2: Autonomous Inventory Check & Price Top/Repost for Stale Listings

### 1. Description & Intent
The Agent conducts an automated audit of active listings to detect stagnation (high days on market, declining view velocity, or impending 60-day portal expiration), re-evaluates current market positioning, and initiates supervised price adjustments and reposting.

### 2. Primary Actors
- **AI Agent**: Scheduled or on-demand auditor monitoring inventory health.
- **Seller**: Decision-maker authorizing price reductions and re-listing operations.

### 3. Domain Entities & Operations Involved
- **Entities**: `Listing`, `ListingStatus` (`Active`, `Expired`, `NeedsReview`), `MarketRadarAnalysis`.
- **Value Objects**: `PricePoint`, `PriceRecommendation`.
- **Operations**: `ProbeMarketRadar`, `RepostWithNewPrice`.

### 4. Preconditions
- Listings exist in local storage with `ListingStatus` = `Active`.
- Synchronization service has updated view counters and listing age metadata.

### 5. Interaction Flow
1. **Inventory Health Scan**:
   - The Agent evaluates all active listings against staleness criteria:
     - **Stale Listing**: Days on market > 14 with view velocity < 1 view/day, or days on market > 30.
     - **Expiring Listing**: Reaching 55+ days on portal (approaching the mandatory 60-day expiration cutoff).
2. **Market Re-Sampling (`ProbeMarketRadar`)**:
   - For identified candidates, the Agent runs an updated market radar check.
   - Compares current asking `PricePoint` against newly listed competitor prices to determine whether the listing has fallen behind market velocity.
3. **Adjustment Proposal**:
   - The Agent compiles an audit report for the seller:
     - Listing identifier, title, current price, and days active.
     - Current competitor median vs. current asking price.
     - Proposed action: Step-down price reduction (e.g., -5% to -10%) or repost bump at current price to reset top-of-search ranking.
4. **Seller Authorization Gate**:
   - The Agent requests explicit confirmation: *"Listing 'Makita DHP484' has been active for 32 days with 14 views. Competitor median dropped to 2,200 Kč. Repost at 2,190 Kč?"*
5. **Execution (`RepostWithNewPrice`)**:
   - Upon seller consent, the Agent executes the repost workflow:
     - Updates local `Listing` record with the new `PricePoint`.
     - Triggers automated portal workflow to delete or supersede the previous ad and publish the renewed offer.
     - Captures new portal item ID and resets creation timestamp.
     - Updates local Google Calendar / iCal expiration feed.

### 6. Postconditions & Invariants
- The listing's asking price is updated to the agreed `PricePoint`.
- The listing's age is reset to day 0 upon successful portal re-listing.
- Expiration calendar feeds reflect the renewed 60-day lifecycle.

### 7. Edge Cases & Safety Gates
- **Minimum Price Floor**: The seller can set a hard floor for each listing. The Agent will never propose or execute a `PricePoint` below the defined floor.
- **No Unsupervised Price Cuts**: The Agent must never autonomously repost or discount a listing without explicit affirmative confirmation from the seller.
- **Rapid Repost Protection**: A listing cannot be reposted if its last repost occurred less than 7 days prior, preventing portal spam flags.

---

## UC-3: Conversational Ad Posting with 2-Phase User Sign-Off

### 1. Description & Intent
The Agent takes an uncommitted `Draft` listing, verifies category routing and seller profile data, executes an automated browser worker to prefill all form fields, pauses safely at the review boundary for human inspection, and finalizes publication upon explicit confirmation.

### 2. Primary Actors
- **Seller**: Human reviewer verifying prefilled data on the live browser viewport.
- **AI Agent**: Supervised operator orchestrating browser prefilling, screencasting, and state transition.

### 3. Domain Entities & Operations Involved
- **Entities**: `Listing`, `ListingStatus` (`Draft` -> `NeedsReview` -> `Active`), `TwoPhaseSession`, `SubdomainCategory`, `PhotoAsset`.
- **Value Objects**: `PricePoint`, `ContactProfile`.
- **Operations**: `LaunchTwoPhasePosting`, `ConfirmSubmission`, `CancelAction`.

### 4. Preconditions
- The target `Listing` is in `Draft` status with validated title, description, price, and at least one `PhotoAsset`.
- `ContactProfile` contains phone number, ZIP code, location name, and listing management password.
- Target `SubdomainCategory` is explicitly confirmed.

### 5. Interaction Flow
1. **Pre-flight Validation**:
   - The Agent confirms all mandatory fields are present.
   - Validates that title length is <= 50 characters.
   - Verifies target `SubdomainCategory` (e.g. `dum.bazos.cz`) to prevent browser redirect form-wipes.
2. **Phase 1 — Supervised Prefill (`LaunchTwoPhasePosting`)**:
   - The Agent initializes a `TwoPhaseSession`.
   - Dispatches a background automation worker directly to the target domain URL.
   - Automatically populates: Rubrika, Subkategorie, Nadpis, Popis, Cena, Jméno, PSČ, Telefon, Heslo.
   - Sequentially uploads associated `PhotoAsset` files, ensuring the assigned cover photo is uploaded first.
   - The worker halts execution immediately before final form submission, entering the `NeedsReview` state.
3. **Live Handoff & Screencast**:
   - The Agent provides the seller with an interactive live browser view.
   - Displays a prominent status prompt: *"Form prefilled. Review details in browser view, click Submit on portal, then confirm here."*
4. **Authentication / Verification Gate (SMS Guard)**:
   - If the portal presents an SMS phone verification challenge:
     - The worker detects verification input fields (`klic`, `kodd`, `cr`).
     - Agent notifies the seller: *"Bazoš requires SMS verification. Enter the SMS code in the live browser view."*
     - The worker remains paused without triggering timeouts or repeated requests.
5. **Phase 2 — Final Human Sign-off (`ConfirmSubmission`)**:
   - The seller inspects prefilled fields, submits the form in the live viewport, and clicks **Confirm Submission** in the interface.
   - The Agent verifies form departure, confirms absence of error messages, and locates the newly created portal ad link.
   - Extracts the permanent external listing ID and canonical URL (`/inzerat/<id>/`).
   - Transitions `ListingStatus` from `NeedsReview` to `Active`.
   - Persists the live URL, portal ID, and timestamp in local storage.
6. **Cancellation Option (`CancelAction`)**:
   - If the seller notices an error or decides not to proceed, the seller triggers **Cancel Action**.
   - The Agent immediately closes the browser worker, clears temporary browser state, and restores `ListingStatus` to `Draft`.

### 6. Postconditions & Invariants
- A published listing is never marked `Active` without verified confirmation of the external portal URL.
- The automation worker never submits the final form autonomously in Phase 1; submission remains strictly human-governed (Human-in-the-Loop).
- If cancelled, no ghost records are marked active and the draft remains editable.

### 7. Edge Cases & Safety Gates
- **SMS Rate Limiting**: If an SMS code is not received or fails validation, the worker halts without retrying to prevent portal phone blocking.
- **Form Wipe Detection**: If the portal unexpectedly redirects or resets inputs, the Agent catches the condition, aborts the session, and alerts the seller without corrupting local data.

---

## UC-4: Multi-Item Batch Status Inquiry and Profit Reporting

### 1. Description & Intent
The Agent aggregates inventory state across all managed listings, provides an executive overview of active listings, flags items requiring intervention, and calculates financial realized profit metrics from closed transactions.

### 2. Primary Actors
- **Seller**: Inquiring about current inventory status, sales performance, and operational backlog.
- **AI Agent**: Analytical reporter querying local storage and calculating metrics.

### 3. Domain Entities & Operations Involved
- **Entities**: `Listing`, `ListingStatus` (`Draft`, `Active`, `NeedsReview`, `Sold`, `Expired`).
- **Value Objects**: `PricePoint`.
- **Operations**: `PurgeListing` (optional hygiene during review).

### 4. Preconditions
- Persistent storage contains listing history with associated portal states and financial records.

### 5. Interaction Flow
1. **Query & Metric Collection**:
   - The Agent reads all `Listing` aggregates from persistence along with their associated portal states.
   - Segregates listings by `ListingStatus`:
     - **Drafts**: Items ready to be listed.
     - **Active**: Online items with cumulative view counts, portal links, and days elapsed.
     - **NeedsReview**: Blocked or prefilled items awaiting sign-off.
     - **Sold**: Concluded sales with recorded sale prices and dates.
     - **Expired**: Listings past portal lifetime needing decision.
2. **Financial Aggregation**:
   - Sums realized `PricePoint` values for all items in `Sold` status within the requested timeframe (e.g., month-to-date, year-to-date, or all-time).
   - Computes:
     - Total realized revenue (CZK).
     - Average sales velocity (days from `Draft` creation to `Sold`).
     - Most viewed active listings vs. dormant listings.
3. **Operational Alert Generation**:
   - Flags actionable alerts:
     - Listings expiring within 3 days.
     - Listings stuck in `NeedsReview` or awaiting SMS verification.
     - Stale active listings (> 30 days without price change).
4. **Structured Response Synthesis**:
   - Formats a clear, Markdown-table dashboard:
     - **Active Inventory Overview** (Title, Category, Price, Views, Days Active, Expiration Warning).
     - **Backlog & Drafts** (Items photographed, awaiting pricing or review).
     - **Realized Sales & Profit Ledger** (Sold item, sale date, realized price).
5. **Follow-up Action Offering**:
   - The Agent offers targeted follow-up actions:
     - *"Would you like me to initiate reposting with price adjustments for the 2 stale items?"*
     - *"Would you like to purge sold listing records and delete their local photos to free disk space?"*

### 6. Postconditions & Invariants
- Financial metrics reflect strict arithmetic sum of recorded `PricePoint` values.
- Read-only inquiry does not alter any listing state or external portal status.

### 7. Edge Cases & Safety Gates
- **Corrupted or Partial Records**: If an item in `Sold` status lacks an explicit realized price, the Agent falls back to the original asking price and annotates the figure with an estimated marker `(~)` for transparency.
- **Safe Purge Verification (`PurgeListing`)**: If the seller requests deletion of sold listings during the review, the Agent confirms whether local photo directories should also be deleted, enforcing path validation to protect system directories.
