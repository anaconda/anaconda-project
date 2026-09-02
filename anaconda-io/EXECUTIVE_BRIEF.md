# Anacondae — Executive Brief

**One-liner:** A multiplayer, browser-based snake game — built as an internal showcase of Anaconda's expanding AI platform — where players compete for territory and diamonds representing Anaconda's real acquisitions and upcoming product launches.

---

## 1. Why this exists

Anaconda has made a string of strategic acquisitions this year (Outerbounds, Kilo Code, Enkrypt AI) and is positioning itself as a **full-stack AI developer company** — build, orchestrate/deploy, and secure, all under one roof. That story is easy to state in a slide and hard to make people *feel*.

This game is a lightweight, fun artifact that makes the "full-stack rollup" narrative tangible: players literally build a growing "AI Factory" out of Anaconda's acquisitions and product launches while competing for territory, in a style modeled after familiar multiplayer arcade games (slither.io + paper.io).

Primary use cases:
- **Internal culture/rally piece** — a fun way to socialize the acquisition story at an all-hands, Slack channel, or hackathon demo.
- **External-facing novelty** — a shareable, on-brand Easter egg for a launch announcement or event booth.
- **Dogfooding narrative** — a genuine (if small) proof point that Anaconda's own tools can build, and potentially ship, a real product end-to-end.

This is **not** a production product and carries no revenue or customer-facing commitment as of this writing.

---

## 2. What it is (gameplay)

- **World:** a large circular arena (not a rectangle) — bigger than the screen, camera follows your snake, and the boundary is lethal if you touch it.
- **Core loop:** grow by eating diamonds; avoid other snakes' bodies and your own tail (touching either kills you instantly); territory you claim by looping back into land you already own (paper.io-style) — get cut off outside your own territory and you're vulnerable.
- **Controls:** arrow keys to steer, Up/Space to boost (boost is a pure speed dash — it costs length, it cannot be used to grow for free).
- **The brand hook — "The Acquisition Trifecta":**
  - Three rare, extra-valuable diamonds bear the **real logos and real brand colors** of Outerbounds, Kilo, and Enkrypt (fetched from their live marketing sites, not invented placeholders).
  - Collecting one adds a themed building to your permanent **AI Factory** — starting from a small "Anaconda workshop," each acquisition diamond bolts on a new building with that company's mark.
  - Complete all three and you earn a **permanent Crown** — a personal achievement that, once earned, is never taken away by dying. (Design finalized; implementation of full cross-life persistence was in progress at the time of writing — see Status below.)
  - Only *after* earning the Crown do a second tier of diamonds become meaningful: **Ana CLI GA, Main-X GA, Anaconda MCP GA** — representing this September's real product launches. Each one collected adds another building to your Factory, making it visibly "bigger and stronger" — a running visual scoreboard of how much of the platform a player has "acquired."
- **Session-wide Hall of Fame** tracks who's earned the Crown.

---

## 3. Brand fidelity

Everything brand-related was pulled from real, current sources rather than guessed:
- Real SVG marks for Outerbounds, Kilo, and Enkrypt, extracted from their live marketing sites.
- Real brand colors (e.g., Kilo's actual CTA yellow `#F8F674`, not a generic placeholder).
- "Anacondae" naming and visual style (green/gold, diamond-scale motif) applied consistently across the UI.

---

## 4. Current status (honest snapshot)

**Working and verified today:**
- Full multiplayer game loop: movement, growth, death rules (body, self, boundary), bots to keep the world lively.
- Real acquisition-brand diamonds with real logos/colors.
- Territory capture (claim, flood-fill, contested ground) — core mechanic implemented and tested.
- Trifecta collection triggers a Crown + arena-wide celebration + Hall of Fame entry.

**In progress at time of writing (designed, not yet fully shipped):**
- Making the Crown and acquisition progress **fully persistent across deaths/respawns** (currently the Crown is closer to "per life" than the intended "permanent, no one can take it away").
- The tiered **AI Factory building visual** (workshop → +3 acquisition buildings → +3 product buildings) — the diamonds and Crown exist; the physical factory structure in the world is the next build step.
- The 3 post-Crown **product-launch diamonds** (Ana CLI, Main-X, Anaconda MCP) gated to only benefit Crowned players.
- Smoother territory rendering and a couple of related territory-fairness fixes (trail vulnerability, visible in-progress claim lines) requested during playtesting.

**Not yet solved — infrastructure:**
- **No permanent hosting.** The game currently only runs inside an ephemeral cloud sandbox, exposed via temporary, no-guarantee tunnel links for demo purposes. Every link shared so far has been short-lived by design and has already gone down multiple times when the sandbox recycled itself.
- **No git repository exists yet.** An attempt to push this to the requester's personal GitHub was blocked by a scope-less access token in this sandbox; this has not yet been resolved.
- **No decision made** on a real hosting home (a Kubernetes/EKS-style deploy fits Anaconda's own infrastructure pattern best, given the game's persistent WebSocket server; lightweight PaaS options like Render/Fly.io work for a quick, low-cost demo instance).

---

## 5. Technical shape (for engineering context)

- **Stack:** Node.js + Express + Socket.io (authoritative real-time server), vanilla Canvas + JS client — no framework, no build step, easy to read and hand off.
- **Why not fully "dogfooded" on Anaconda's own stack:** Outerbounds' workflow/orchestration layer is built for ML batch pipelines, not a poor fit for a stateful WebSocket game server; Outerbounds' separate "Deployments/Apps" feature is a better fit but requires real cloud account setup this sandbox doesn't have. `ana` CLI installation and login were also not completed in this session.

---

## 6. Recommended next steps

1. **Decide the game's actual purpose** (internal demo only vs. something shown externally) — that decision determines how much more polish/hosting investment is worth it.
2. **Stand up a real, permanent repository** under proper Anaconda or personal GitHub ownership — currently the only copy of this code lives in a disposable sandbox.
3. **Pick a real hosting target** and deploy once, rather than continuing to regenerate temporary tunnel links.
4. **Finish the in-progress design** (persistent Crown, AI Factory visuals, gated product diamonds) — scoped and ready to build, just not complete at time of writing.

---

*Prepared by Kilo (AI coding agent) as a status summary of work completed and in progress in this session. All claims about "what works" reflect direct testing performed in this session, not assumptions.*
