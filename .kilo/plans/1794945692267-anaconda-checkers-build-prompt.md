# Build Prompt — "Anaconda Checkers: Clash & Conquer"

Copy everything under **PROMPT** into an implementation-capable agent (Kilo Code, Cursor, Claude, etc.). It is self-contained.

---

## PROMPT

Build a single-page, browser-based **checkers game** for **Anaconda Inc.**, themed around the company's brand, products, and public facts. The game's signature mechanic is a **mid-air clash** between checker pieces during captures, followed by a **brand-fact wager card** that determines whether the capture counts.

Deliver exactly **one self-contained file**: `checkers.html`.

---

### 1. HARD CONSTRAINT: single HTML file

This is a hard requirement, not a preference.

- ONE file only: `checkers.html`. No `style.css`, no `game.js`, no build step, no bundler, no npm, no server.
- All CSS inside a single `<style>` block in `<head>`. All JS inside a single `<script>` block at end of `<body>`. ES2020+ is fine (modern browsers only).
- **Zero runtime dependencies.** No CDN `<script>` tags, no Google Fonts CDN, no React/Vue/jQuery/GSAP. The **only** embedded binary is the Anaconda logo (§1b). It must work offline when opened via `file://`.
- **Fonts: fallback stack only** — do not download or embed font binaries. Use:
  - Headings: `font-family: "Poppins", "Helvetica Neue", Arial, sans-serif;`
  - Body: `font-family: "Inter", "Helvetica", Arial, sans-serif;`
  - Mono: `font-family: "JetBrains Mono", "SF Mono", Consolas, monospace;`
- **No external network calls of any kind at runtime** — no fetch, no analytics, no fonts, no remote images. The logo is fetched **once at build time** and embedded (see §1b).

### 1b. LOGO: pull it from the web, embed it, use it

The Anaconda logo **must** appear in the finished page. It is not optional and not a placeholder.

**Step 1 — download the official asset at build time.** Use the corporate logo from Anaconda's own site:

```
https://www.anaconda.com/wp-content/uploads/2024/11/2020_Anaconda_Logo_RGB_Corporate.png
```

Fallback URL if that 404s: `https://www.anaconda.com/wp-content/uploads/2024/11/Anaconda-Logo.png`
Both are the official mark served by anaconda.com and are confirmed live. Try them in order with `curl -sSL -o logo.png`, and verify the download is a real PNG before proceeding:

```bash
file logo.png                    # must report "PNG image data"
python3 -c "import struct,sys;d=open('logo.png','rb').read(24);print(struct.unpack('>II',d[16:24]))"   # width, height
```

If the bytes are HTML (an SPA/404 page) or the file is under ~2KB, treat it as a failed download and try the fallback URL. If both fail, STOP and report it — do **not** silently substitute a hand-drawn logo, and do not reference a remote URL in the HTML.

**Step 2 — embed it as a data URI.** Base64-encode and inline it into the single HTML file:

```bash
base64 -w0 logo.png > logo.b64
```

Then paste the contents into a constant near the top of the script:

```js
// Official Anaconda corporate logo, embedded at build time. Do not replace with a remote URL.
const LOGO_SRC = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...";
```

Do **not** reference it as `src="./logo.png"` or a URL — the page must be a single portable file. Keep `logo.png` out of the delivered file list.

**Step 3 — where the logo is used.** All of these render the real image (`<img class="brand-logo" alt="Anaconda">`) via one helper, `brandLogo(size, variant)`:

1. **Header / top bar** — primary placement, height ~28–32px, left of the title "Anaconda Checkers".
2. **Onboarding terminal screen** — above the typed `anaconda-project init` lines, at ~64px.
3. **Win/lose finale stamp** — the logo stamps onto the board center: `scale(1.6 → 1.0)`, slight rotation, white flash, ~450ms, then the result panel rises beneath it. This is the hero moment for the asset. Use the larger version here.
4. **Fact-card eyebrow** — a small logo (~18px) beside the `ANACONDA FACT CHECK` label.
5. **Rules modal and fact log drawer** — small logo in the header of each.
6. **Favicon** — the same data URI set via `<link rel="icon" href="...">` so the tab shows the brand mark. (This stays inside the single file.)

**Step 4 — presentation rules for the asset.**

- The logo is a horizontal lockup (mark + "ANACONDA" wordmark) on a **light/white or transparent background**. Never place it directly on `--board-dark`; put it on a small white/mint `--paper` pill or panel chip with 10px padding and a 999px/12px radius, or place it where the background is light.
- Max width constraints per placement: header `140px`, finale `min(280px, 45% of board width)`, others `120px`. Always preserve aspect ratio (`height: auto; width: auto; max-*` — never stretch).
- Never recolor, re-crop, distort, rotate (except the finale's one-time stamp), or apply filters to the logo. No drop shadows on the mark itself; a shadow on its containing chip is fine.
- Provide `alt="Anaconda"`; if the image fails to load at runtime, fall back to the text wordmark `Anaconda` in Poppins 600 green via `onerror` — this is a resilience net, not a design path.

**Legal note to include as an HTML comment at the top of the file:** the logo is the trademark of Anaconda Inc., used here for an internal/demo game; replace or obtain permission before public distribution.
- All state in memory. Persist ONLY lightweight prefs in `localStorage` under a namespaced key (`ac.checkers.v1.*`): sound on/off, facts-seen IDs, best streak. Everything must degrade gracefully if `localStorage` throws (private mode) — wrap in try/catch and fall back to in-memory.
- Must be responsive: playable at 360px wide through 1920px. Board must never overflow viewport height on desktop (use `min(90vh, 90vw)` style sizing).
- Must be keyboard accessible and respect `prefers-reduced-motion`.

### 2. Brand system (use these exact values)

Colors (taken from Anaconda's own docs stylesheet):

```
--anaconda-green:      #43b049   /* primary brand green */
--anaconda-bright:     #0ccb4a   /* highlight / hover / success */
--anaconda-orange:     #ee9040   /* caution accent */
--anaconda-red:        #dc3545   /* danger / wrong answer */
--board-dark:          #1f3d24   /* deep green dark square */
--board-light:         #e8f3e9   /* pale mint light square */
--ink:                 #0d1a10
--paper:               #f7faf7
--panel:               #ffffff
--muted:               #6b7a6e
--slate:               #5c6b63   /* opponent pieces / "Community" side */
```

Rules:
- Player pieces: `--anaconda-green` with a subtle radial highlight (top-left light).
- Opponent pieces: `--slate` with the same treatment (visually parallel, clearly different).
- Kings get a gold/amber ring (`#f2c14e`) and a crown glyph.
- Dark/light square colors above. Never pure black/white squares.
- Rounded corners: 10–14px on panels, 999px on pieces. Soft shadows, never harsh.
- Headings use Poppins stack at weight 600. Body Inter at 400. Numbers/coords use mono.
- Support `prefers-color-scheme: dark`: dark background (`#0b120d`), panels `#141c16`, keep greens identical, text near-white. Implement via CSS custom properties swapped in a `[data-theme="dark"]` block, and a manual theme toggle too.

Anaconda public facts you may use in copy and in the question library (all verified from anaconda.com):

- **Founded 2012** by **Peter Wang** and **Travis Oliphant**.
- **50M+ users** of Anaconda Distribution / Miniconda worldwide.
- **600+ packages** included in Anaconda Distribution.
- **conda** is Anaconda's open-source package and environment manager (installs software, resolves dependencies, isolates environments).
- **Miniconda** = conda + Python + deps only, minimal `base` environment.
- **Anaconda Distribution** = conda + Python + Navigator + hundreds of DS/ML packages pre-installed.
- **Anaconda Navigator** = desktop GUI to manage environments, packages, projects.
- **Anaconda.org** = public package/environment/model hosting.
- **Jupyter Notebook and JupyterLab** ship with the Distribution.
- **Kilo** = Anaconda's agentic coding platform, VS Code / JetBrains / CLI extensions, **5M+ developers**, **500+ models**, open source, no vendor lock-in, free to start.
- **Enkrypt AI** = Anaconda's AI security product: red teaming, guardrails, compliance mapped to **NIST**, **EU AI Act**, **OWASP**, **HIPAA**. Free tier, Launch from **$149/mo**.
- **Outerbounds** brought **Metaflow**, created at **Netflix**, for production orchestration. 2026: three acquisitions in six months (Outerbounds, Kilo Code, Enkrypt AI).
- **Anaconda Platform** = packages + models + workspaces + orchestration, deployable as managed cloud, self-hosted cloud, or on-prem.
- **Notebooks** = cloud-based JupyterLab, free tier with **5GB** storage.
- **Anaconda Core** pricing: Free, Starter **$15/user/mo**, Business **$50/user/mo**.
- Anaconda pioneered **Python for data science**.
- Organizations with **200+ employees/contractors** need a paid Business license unless eligible for academic/non-profit exemption.
- Tagline usable: **"Build, secure, and operate AI on your own terms."**
- Brand promise: **"a trusted foundation so teams spend their time building, not fixing environments or chasing dependency conflicts."**

Copy tone: warm, confident, lightly playful. No emoji spam. Never invent statistics beyond the list above.

### 3. Game rules (standard American checkers)

Implement **8×8 American checkers (English draughts)**:

- 12 pieces per side. Player = green, at bottom, moves up. Opponent = slate, at top, moves down.
- Pieces move one diagonal step forward onto a dark square.
- Captures: jump over an adjacent enemy piece to the empty dark square immediately beyond. **Mandatory**: if any capture exists, the player must take it (highlight only capture moves; block non-capture moves).
- Multiple jumps chain in one turn if further captures are available from the landing square. Finish the chain before ending the turn.
- Reaching the far row promotes to **King**, which can move and capture **both directions**, one step at a time (**no flying kings**).
- **Win** when the opponent has no pieces or no legal moves. **Draw** after 40 consecutive moves (half-moves) with no capture and no promotion.
- Board coordinates: columns `a`–`h` left→right, rows `1`–`8` bottom→top (from the player's perspective). Show coordinate labels along the board edges in mono type.

Rules engine requirements:
- Pure functions: `legalMoves(state, color)`, `applyMove(state, move)`, `isGameOver(state)`. Keep the engine independent of rendering.
- State shape: `{ board: Array(64), turn: 'player'|'ai', mustContinueFrom: squareIndex|null, ... }`. Board values: `null`, `{color:'player'|'ai', king:boolean, id:string, battleXp:number}`.
- Deterministic: no `Math.random()` inside rules logic. Randomness is allowed only for choosing the fact card and for AI tie-breaking, seeded or not — but never inside move legality.

**AI opponent:** depth-4 minimax with alpha-beta pruning, material weighting (piece = 100, king = 175), plus small positional bonus for advancement and back-row retention. AI thinking delay 400–900ms with a subtle "thinking" indicator. AI does not answer fact cards — it resolves its captures automatically (see §5).

### 4. THE MID-AIR CLASH (most detailed requirement — build this first)

This is the signature visual. A capture is never instantaneous. It is a staged, choreographed sequence with clear phases and timing. Build it as an explicit state machine, not as ad-hoc `setTimeout` chains sprinkled through the code.

**Sequence timeline** (total ~1500ms, scaled by a single `CLASH_SPEED` multiplier so it can be tuned and disabled):

1. **Lock (0–100ms).** Capturing piece scales to 1.06 with a soft green glow ring; the victim piece gets a red/orange outline pulse once. A faint dashed arc is drawn from the attacker's square to the landing square, arcing high over the victim square (SVG quadratic curve, `stroke-dasharray`). The arc stays visible for the whole clash as a "flight path".

2. **Launch (100–360ms).** Attacker animates along the arc from its origin square, rising to an apex roughly **1.6× square size above the board plane** (visualized with a CSS `translateY` of ~-`0.6 * squareSize` plus `scale(1.18)` and a growing `filter: drop-shadow` — the shadow stays on the board and shrinks, selling elevation). Use `cubic-bezier(.22,.9,.24,1)` for an ease-out launch. A trailing after-image (2 ghost copies at 40%/20% opacity) follows for motion blur.

3. **Impact-freeze / the clash (360–900ms).** The attacker stops directly **above the victim square**, at apex height, and the two pieces enter a "combat hold":
   - Both pieces rotate to face each other slightly (`rotate(-8deg)` / `rotate(8deg)`).
   - The victim piece **levitates** from its square up to meet the attacker at ~60% of the attacker's height, with an upward `translateY` and slight `rotate`.
   - Between them: a **clash flash** — a radial burst (SVG/CSS) in white→`--anaconda-bright`, plus 6–10 spark particles thrown outward with randomized angles/velocities, plus a **screen shake** on the board container (`translate` jitter, max 4px, ~180ms) and a brief board-wide brightness bump.
   - **Power readout:** above each piece, a floating pill shows a number = `100 + 25 * battleXp` (battleXp = number of successful captures that piece has made). The numbers tick up with a mono font and a 120ms count animation, then a "VS" badge fades in between them. Attacker's pill is green, victim's is slate/red.
   - Both pieces **bob** in a slow 2-cycle `translateY` oscillation during the hold, reading as hovering.
   - Impact sound: short filtered noise burst + low sine thud (~80Hz), synthesized with WebAudio (see §8). No audio files.

4. **Resolution (900–1150ms).** Rules-fixed outcome: **the attacker always wins** (legality is never changed by battleXp — power is presentational, but it makes the win feel earned).
   - Winner: brief glow flash `--anaconda-bright`, then animates down along the remaining arc to the landing square, landing with a squash-and-settle (`scaleY .88 → 1.06 → 1`) and a dust puff (4 faint particles sliding outward).
   - Loser: **shatters** — the disc is replaced by 7–9 triangular/polygonal fragments (CSS `clip-path` on divs, or small SVG paths) that inherit the piece's gradient, then fall with gravity and rotation, fading out over ~400ms. Also fade the loser's board square shadow.
   - If the attacker is being **kinged** on this landing square, chain directly into the promotion animation (§6) after the settle.

5. **Chain / return (1150–1500ms).** If a further capture is available, the arc for the next hop starts from the landing square and the sequence repeats from step 1 (with reduced initial delay ~80ms so chains feel brisk and escalating). Otherwise the piece returns to a resting idle state.

**Clash must also handle:**
- **Multi-jump**: each hop is its own clash. Offset each subsequent clash's shake slightly stronger, and raise the "combo" counter in the HUD (`x2`, `x3`).
- **Reduced motion**: if `prefers-reduced-motion: reduce`, collapse the entire clash to a single 200ms cross-fade with a static "VS" badge and no shake/particles/levitation. Game must remain fully playable.
- **Interruption safety**: the input lock must be enforced — no clicks, no keyboard moves, no AI turns until the clash state machine returns to `idle`. Model this with an explicit `phase` enum and a single `advance()` step, or with cancellable `requestAnimationFrame` timing. Do not allow state mutation mid-animation.
- **Correctness under animation**: rules state must be committed at **resolution** time (step 4), not at lock time, so a cancelled/failed clash can restore cleanly (see §5, wrong answer).
- Rendering approach: a stable DOM board (64 squares) + absolutely-positioned piece elements moved via `transform` so animations never relayout the grid. Prefer `transform`/`opacity` only; avoid animating `top/left/width`.

### 5. THE FACT WAGER (captures only)

Where the clash ends at step 3 (the impact-freeze), a **fact card** appears and decides the outcome.

**Flow:**
1. Clash runs through launch → impact-freeze → the "VS" badge appears.
2. **Every capture by the human player** pauses the fight and slides in a **brand-fact card** from the bottom (on mobile) or from the right (desktop), over a scrim at 35% opacity. Board remains visible and dimmed so the clash is still on screen.
3. Card content:
   - Small eyebrow: `ANACONDA FACT CHECK`
   - A statement, e.g. *"Anaconda was founded in 2012."*
   - A one-line context hint in `--muted` (optional, e.g. *"By Peter Wang and Travis Oliphant."*)
   - Two buttons: **True** and **False**, large tap targets (min 44px), keyboard-focusable, also answerable with `T`/`F` or `←`/`→`.
   - A subtle timer ring or progress line, **10 seconds** to answer. Timeout counts as wrong.
4. **Correct** → the attacker finishes the fight: resolution plays (victim shatters, winner lands), capture counts, `battleXp` +1 on the winner, card fades out with a green check and a "+1 CAPTURE" stamp. Perfect-answer streak increments.
5. **Wrong or timeout** → the fight is **lost**: the card flashes `--anaconda-red`, the correct answer is revealed with a one-line "Actually…" explanation (every question must carry its own `explain` string), the attacker's piece animates **back down the arc to its origin square**, the victim **floats back down** to its square untouched, and the turn **passes**. No capture occurs.
6. **Mandatory-capture safety (critical).** Because a failed wager cancels the move, the mandatory-capture rule must be waived for exactly that turn to avoid a soft-lock: track a per-side `captureWaived` flag for one turn only, clear it at the start of that side's next move, and skip the wager for that move. Never leave a player with no legal input.
7. **AI captures do not use cards.** The opponent resolves its captures automatically (always succeeds) and instead shows a small toast: *"Anaconda fact: …"* with a one-line true statement, non-blocking, auto-dismissing. This keeps pacing fast and still teaches.
8. **Never repeat a question within one game.** Track seen IDs in memory, and across games in `localStorage` (with an "allow repeats once exhausted" fallback).

**Question library.** Ship at least **24 questions** in a `FACTS` array, each shaped:
```js
{ id:"f01", statement:"…", answer:true|false, explain:"…" }
```
Approximately **60% true / 40% false** so guessing is punished slightly. Statements must be short (under 90 characters), light, and answerable by anyone in under 5 seconds — no trivia requiring deep conda knowledge, no ambiguous phrasing, no numbers that changed recently unless stated as of the site today. Use these, and phrase false ones as plausible-but-clearly-wrong to a careful reader:

TRUE: Anaconda was founded in 2012. / Anaconda was co-founded by Peter Wang and Travis Oliphant. / conda is an open-source package and environment manager. / conda keeps projects isolated so updating one doesn't break another. / Miniconda installs only conda, Python, and their dependencies. / Anaconda Distribution includes Jupyter Notebook and JupyterLab. / Anaconda Navigator is a desktop GUI for managing environments and packages. / Anaconda.org hosts packages, environments, and models. / Anaconda Distribution ships with 600+ packages. / More than 50 million people use Anaconda. / Kilo is Anaconda's agentic coding platform. / Kilo supports 500+ AI models. / Kilo works inside VS Code, JetBrains IDEs, and the CLI. / Enkrypt AI provides guardrails and AI red teaming. / Anaconda's tagline is "Build, secure, and operate AI on your own terms."

FALSE (with the truth in `explain`): Anaconda was founded in 2009. (It was 2012.) / Miniconda includes hundreds of pre-installed data science packages. (It's minimal — conda + Python only.) / conda is a closed-source commercial installer. (It is open source.) / Kilo is a database product. (It's an agentic coding platform.) / Anaconda Notebooks are desktop-only. (They run in the cloud, in the browser.) / Travis Oliphant founded Anaconda alone. (With Peter Wang.) / Enkrypt AI is Anaconda's hardware product. (It's AI security and guardrails.) / Anaconda Distribution contains fewer than 10 packages. (600+.) / Anaconda requires Windows to run. (macOS, Linux, Windows.)

Add a few more of your own from the verified facts list in §2 to reach 24+, keeping the same light difficulty. Every question needs a non-empty `explain` shown on a miss.

### 6. Support systems (build after the clash and the wager work)

**Promotion ("shedding the skin").** When a piece reaches the back row: the flat disc cracks along a hairline, the outer ring splits and slides off (two halves translating apart and fading), revealing a brighter inner disc with a gold ring and crown glyph, plus a short green sparkle burst and a rising "kingship" chime. In the HUD, a one-line toast: `⏶ promoted to King`. Kings also get a permanent subtle shimmer (`background-position` drift, disabled under reduced motion).

**Battle experience / aura.** Every piece tracks `battleXp` (captures won). At 1+ captures, add a thin inner ring whose opacity scales with xp (cap at 3 rings). At 3+ captures, add a faint pulse animation. This is purely cosmetic and never alters rules — display it in the clash "power pill" as `100 + 25*xp`.

**HUD.**
- Left: player panel — label `You`, green piece count, small avatar chip, active-turn highlight.
- Right: opponent panel — label `Community`, slate piece count, "thinking…" dots when AI is calculating.
- Center: move counter, `x2`/`x3` combo badge during chains, and a `Best streak` stat.
- Top bar: logo (via `brandLogo()`), title **"Anaconda Checkers"**, subtitle *"Reproducible on every machine."* Buttons: sound toggle, theme toggle, rules, new game.

**Fact log / notebook.** A collapsible right-side drawer styled like Jupyter cells:
`In [n]: capture c3→e5` then `Out[n]: ⚑ fact correct — 7 vs 5`.
Collapsed by default on mobile, open on ≥1200px. Populated from move history, so the whole game is auditable. Include a `Copy as code` button that copies a plain-text move log to the clipboard (with `navigator.clipboard` fallback to a textarea + `execCommand`).

**Win/lose finale.** When the game ends: board dims with a vignette, the clash of the final capture (if applicable) plays in slow motion (`CLASH_SPEED = 0.4`), then the logo **stamps** onto the board center: scale `1.6 → 1.0` with a slight rotation and a flash, followed by the result panel — `You win` / `Community wins` / `Draw`, final material counts, facts correct out of total, best streak, and buttons `Play again` / `Share result`. Share copies an ASCII result to the clipboard (piece counts + a green/slate score bar) — no external share APIs.

**Onboarding.** First load shows a terminal-style typed intro over the board:
```
$ anaconda-project init checkers
$ anaconda-project run checkers
› trusted foundation loaded. 600+ packages, 0 conflicts.
```
then the board fades in. Skip on click or `Esc`. Remembered in `localStorage`. Keep it under 2.5s total.

**Rules modal.** Short, readable, mirrors §3 — mandatory captures, no flying kings, promotion, the fact-wager rule, and the one-turn capture waiver. Also states that fact cards only appear on your captures.

**Move history / undo.** Undo the player's last completed turn (including restoring a waived-capture flag and un-counting the fact stats). Do not allow undo during a clash or wager.

### 7. Interaction & accessibility

- Click/tap a piece to select → legal destinations show as pulsing rings (green for moves, orange-red `--anaconda-orange` for captures). Click a destination to move. Click the same piece again to deselect.
- Keyboard: arrow keys move a cursor around the board (visible outline), `Enter`/`Space` selects/moves, `Esc` cancels/deselects, `U` undo, `R` new game.
- ARIA: board is a `role="grid"` with `role="gridcell"` children carrying `aria-label`s like `"d2, green checker"`. Announce moves and clash results in an `aria-live="polite"` region (`"Capture: green takes slate at e5. Fact check: correct."`). The fact card is a `role="dialog" aria-modal="true"` with focus trapped on its buttons, returning focus on close. Focus rings visible and styled in `--anaconda-bright`.
- Color-blind safety: pieces differ by shape too — green side gets a **rounded square** silhouette option? No: keep circular but give the slate side a **double-rim ring** texture and add optional `⬤ / ◎` patterns toggle in settings so the two sides never rely on hue alone. Kings distinguished by crown glyph, not just color.
- All interactive elements ≥44px on touch. No hover-only affordances.

### 8. Sound (synthesized only, no files)

Use a lazily-created `AudioContext`, only after the first user gesture. Provide small helpers: `click`, `step`, `whoosh`, `impact`, `shatter`, `chime`, `fail`, `win`. Volume modest (peak gain ≤ 0.25), master toggle persisted. All wrapped in try/catch; on any failure the game continues silently. Respect a `soundMuted` flag checked before every call.

### 9. Quality bar & self-checks

Before you consider the task done, verify all of these:

1. Opening `checkers.html` via `file://` plays a full game with no console errors and no network requests (check DevTools Network is empty besides the document).
2. The file contains exactly one `<style>` and one `<script>` block and **no** `src=`/`href=` pointing to any remote host.
3. Clash animation runs for every hop of a multi-jump, without desyncing board state or leaving stray DOM nodes behind.
4. A wrong fact answer restores the board exactly to the pre-move state, passes the turn, and cannot produce a no-legal-move soft-lock (test: force a wrong answer while a capture is mandatory, then verify the next turn is playable).
5. Winning, losing, drawing, undo, new game, theme toggle, and mobile layout all work.
6. `prefers-reduced-motion` path fully playable and clash is not broken.
7. No question repeats within a game, and the "allow repeats once exhausted" fallback triggers without errors.
8. The official Anaconda logo renders from the embedded data URI in the header, onboarding, fact card, finale stamp, and favicon — with no network request, and never stretched or recolored.
9. Report what you validated and anything you could not verify.

### 10. Output

Deliver the complete `checkers.html`. At the end, give a short summary of the clash timing model, the fact-question count, and any deliberate deviations from this prompt.

---

## Notes for whoever runs this prompt

- The logo is **required**. Download it from the URL in §1b at build time, embed it as a base64 data URI, and verify it renders. Do not sketch a substitute, and do not point the `<img>` at a remote URL.
- The data URI roughly adds 30–120KB to the file depending on the source PNG. That is acceptable for a single-file deliverable. If the source is over ~1MB, downscale to ~600px wide with Pillow before encoding (`Image.open("logo.png").resize(...).save("logo.png", optimize=True)`) — still a build-time step, still embedded.
- If the download fails entirely, report the failure and ask for the file. Do not ship a placeholder and do not silently swap in a hand-drawn mark.
- If the user wants a 10×10 international draughts variant later, the rules engine needs flying kings and men capturing backwards; the clash and wager systems are rule-agnostic and carry over unchanged.
- If they want the fact gate *before* the move instead of at the clash, move the card trigger to the `lock` phase and reuse the same waiver logic.
