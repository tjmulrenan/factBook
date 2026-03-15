# Reel Builder — Daily Facts with TJ

A Node.js web app for producing 30-second Instagram reels about historical facts. Finds and verifies facts, generates scored scripts, produces Kling AI shot prompts, and auto fact-checks every line.

Runs at `http://localhost:3001`.

---

## Setup

**Prerequisites:** Node.js 18+, an Anthropic API key in the root `.env`.

```bash
cd webapp-reel
npm install
node server.js
```

Open `http://localhost:3001`.

---

## One-Time Setup — TJ Elements in Kling

Do this once before your first reel. TJ's appearance is defined by a Kling element so you never have to describe him in prompts.

**Reference images to keep** (stored in your TJ references folder):

| File | Purpose |
|---|---|
| `front.png` | Primary style anchor |
| `hand.png` | Speaking / gesturing shots — best for lip sync |
| `front-side.png` | 3/4 angle shots |
| `shock.png` | Reaction shots |

**Steps:**
1. Go to Kling → Elements → Create new element
2. Name it `@TJ`
3. Upload all four images above
4. Save — this element is now reusable across every future reel

**Base scene reference (optional but recommended):**

Generate this prompt once in ChatGPT (upload `front.png` alongside it) and save the result as `base_scene.png`. Use this image as a style reference when generating scene images:

```
A warm cartoon living room interior. A tan sofa with two cream cushions,
a wooden side table with a lamp, a window with warm afternoon light,
a plain beige rug on a wooden floor. No characters. Warm amber and cream
colour palette — restrained, not rainbow. Art style: 2000s Saturday morning
cartoon — thick clean black outlines on every edge of every object, flat
cel shading with a single soft highlight per surface, no gradients,
no blending, slightly exaggerated proportions on all furniture.
No photorealism. No painterly textures. No 3D rendering. Wide establishing
shot showing the full room with depth.
```

---

## Per-Fact Workflow

### Step 1 — Find Facts (in the app)

1. Pick a date using the date picker
2. Click **Find Facts** — searches the web, verifies 5 historical facts for that date
3. Each card shows the title, year, hook line, and why it works
4. Click **Swap** on any fact you don't like — replaces it with a fresh verified one
5. Click **Select** on the best fact

---

### Step 2 — Generate Reel Package (in the app)

Click **Generate Reel Package**. The app internally generates 10 complete script candidates, scores each on 8 metrics, and returns the top 3.

**Scoring metrics (each out of 10, total out of 80):**

| Metric | What it measures |
|---|---|
| Hook | Does Shot 1 stop the scroll cold? |
| Pacing | Durations feel right, story breathes |
| TJ Voice | Sounds like a character, not a narrator |
| Payoff | Final line lands hard |
| Clarity | Fact communicated cleanly in one watch |
| Economy | Every word earns its place |
| Spoken Flow | Sounds natural aloud |
| Arc | Genuine build from Scene 1 to Scene 2 |

The highest-scoring script is marked **★ TOP** and recommended. Versions 2 and 3 are alternatives.

**Fact check runs automatically** in the background after generation. Any wrong, uncertain, or embellished lines are flagged and auto-fixed. The status line shows how many issues were corrected.

**Character references** — if the fact involves a named historical figure, a ChatGPT prompt is shown. Generate the image and upload it to Kling as an element (e.g. `@Einstein`) before shooting.

---

### Step 3 — Review & Edit Script (in the app)

- Click between Version 1, 2, 3 tabs to compare
- Each tab shows the score out of 80 and a one-line note on its strongest quality
- Click **Edit** on any line to change it inline — saves back to the script automatically
- The full script updates live as you edit

---

### Step 4 — Generate Visuals (in the app)

Select your preferred script version, then click **Generate Visuals**.

The app produces:
- **TJ costume element** — a full description of TJ's themed outfit/transformation for this fact, plus the element name (e.g. `@TJPie`)
- **6 Kling shot prompts** — one per shot, 40–80 words each, element-based

---

### Step 5 — Generate TJ Costume Image (in ChatGPT)

1. Open ChatGPT with image generation
2. Upload `front.png` (your TJ reference)
3. Paste the costume prompt shown in the app
4. Save the result as `tj_costume.png` (or a descriptive name)
5. Go to Kling → Elements → Create new element
6. Name it exactly as shown in the app (e.g. `@TJPie`)
7. Upload the generated image

**If the fact has named historical characters:**
- Same process — upload `front.png` + paste the character prompt
- Save and upload to Kling with the name shown (e.g. `@Einstein`)

---

### Step 6 — Generate Video in Kling

**Scene 1:**
1. Open Kling → Image to Video
2. Shot 1: upload a starting image (any suitable image or a ChatGPT-generated scene), paste the Shot 1 prompt, add elements `@TJ` + `@TJCostume`
3. Generate
4. Shots 2 & 3: same workflow with their respective prompts

**Scene 2:**
1. Extract the **last frame** of Scene 1 Shot 3 (the group/establishing shot)
2. Use that frame as the starting image for Scene 2 Shot 1 in Kling
3. This locks all character appearances from Scene 1 into Scene 2
4. Generate Shots 1–3 of Scene 2 using their prompts

**Lip sync note:** Kling locks lip sync to the most prominent forward-facing face. TJ should be dominant and facing camera in every speaking shot — the prompts already specify this.

---

### Step 7 — Assemble in CapCut

1. Import all 6 clips in order
2. Add music (the app suggests a music vibe in the editing notes)
3. Sync audio (ElevenLabs voiceover or Kling native TTS)
4. Export

---

## How the Scripts Work

**Shot 1 structure:** hook → date → costume comment. The most outrageous thing about the fact comes first (stops the scroll), then the date drops in casually, then TJ makes a dry comment about his transformation.

**Scene 1** (15s, 3 shots): setup — establishes the situation through TJ's eyes, builds tension.

**Scene 2** (15s, 3 shots): payoff — the thing happens, fallout, closing line.

**TJ's voice:** dry, sharp, British, always reacting — not narrating. He's surprised by the information, not briefing an audience.

---

## Structure

```
webapp-reel/
├── server.js                   # Node HTTP server — all API endpoints
├── public/
│   └── index.html              # Single-page UI
├── package.json
└── KLING_ELEMENTS_GUIDE.md     # Detailed Kling Elements reference
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/facts` | POST | Find 5 verified facts for a date |
| `/api/swap` | POST | Replace one fact with a fresh alternative |
| `/api/generate-video` | POST | Generate 10 scripts, score, return top 3 |
| `/api/generate-visuals` | POST | Generate Kling prompts for chosen script |
| `/api/check-script` | POST | Fact-check script lines via web search |

---

## Models Used

| Task | Model |
|---|---|
| Script generation (10 candidates + scoring) | `claude-opus-4-6` |
| Fact finding, visuals, fact-checking | `claude-sonnet-4-6` |
