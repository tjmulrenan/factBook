# Kling Elements — Research & Workflow Guide

## How Elements Work

- You upload 1–4 reference images per element in the Kling library
- Each element gets a short name, referenced in prompts as `@ElementName`
- Up to **4 elements per prompt** — mixing character + scene elements is fine
- Elements replace appearance description in prompts — do NOT re-describe in text
- Prompt focus with elements: action + camera only, 30–60 words sweet spot
- Elements persist in your library and are reusable across all future generations
- Re-describing appearance from an element causes conflicts and degrades consistency

---

## Character Elements

### How many reference images?
- **1 image** = works for one-off characters
- **3–4 images** = recommended for recurring characters (different angles/expressions)
- Kling officially recommends: front view, 3/4 view, face close-up, expression variation

### TJ's references (save all 4 to @TJ element)
| File | Purpose |
|---|---|
| front.png | Primary style anchor |
| hand.png | Speaking/gesturing — best for lip sync |
| front-side.png | 3/4 angle shots |
| shock.png | Reaction shots |

### Historical characters
- 1 image is enough for one-off appearances
- Generate via ChatGPT (app now outputs a prompt per character automatically)
- Name elements short and clear: `@Einstein`, `@Victoria`, `@Pemberton`

### TJ costume/transformation elements
- Worth creating for recurring transformations (e.g. `@TJPie`, `@TJApple`)
- Each distinct outfit/form needs its own element — elements are tied to the visual in the image
- For one-off transformations, describe in prompt text — not worth making an element for single use

---

## Scene Elements

- Kling supports scene/location elements (not just characters)
- Upload a ChatGPT-generated image of the location as an element
- Name descriptively: `@GermanBedroom`, `@AppleGarage1976`, `@VictorianParlour`
- Use the generic scene prompt below to generate these in ChatGPT

### Generic Scene Prompt for ChatGPT
```
A [era/time period] [location type — interior/exterior]. [2-3 key architectural
or environmental details]. [Lighting description — warm candlelight / bright
afternoon sun / dramatic gaslight etc.]. Art style: 2000s Saturday morning
cartoon — thick clean black outlines on every edge, flat cel shading with a
single soft highlight per surface, bright saturated colours, no gradients,
no photorealism, no 3D rendering. No characters. Wide establishing shot
showing the full space with depth.
```

**Example:**
```
A 1879 German bedroom interior. Dark wood furniture, a simple wooden cradle
centre-frame, lace-curtained window with soft golden light. Warm candlelight.
Art style: 2000s Saturday morning cartoon — thick clean black outlines on
every edge, flat cel shading with a single soft highlight per surface, bright
saturated colours, no gradients, no photorealism, no 3D rendering. No
characters. Wide establishing shot showing the full space with depth.
```

---

## What Changes in Prompts When Using Elements

### REMOVE (elements handle this):
- All physical descriptions of characters (hair, build, outfit, eyes, moustache)
- All scene/setting descriptions (if scene element used)
- Art style paragraph (element images define the style)
- Duplicate TJ warnings (element defines the one correct appearance)
- Character position anchors beyond simple left/right/centre

### KEEP:
- `@ElementName` references for every element in the shot
- Action and motion description
- Who is speaking and their voice description
- Camera direction (one phrase)
- Position in frame (left, centre, right)
- Avoid line (photorealism, text, extras)
- Explicit silence labels for non-speaking characters

### Example prompt WITHOUT elements (current, ~2000 chars):
```
Only @TJ speaks. @TJ says in the voice of...: "line here."
Einstein: mouth closed, silent.
Setting: A cosy eighteen-seventies German bedroom — dark wood furniture,
a lace-curtained window, a wooden cradle centre-frame...
@TJ stands left-frame — a giant glossy cartoon pi symbol, roughly
human-height, deep indigo-blue... [200 more words of description]
```

### Example prompt WITH elements (~50 words):
```
Only @TJ speaks. @TJ says in the voice of a young adult male, bright and
slightly squeaky, British accent: "Eighteen seventy-nine — a baby is born
in Ulm, Germany."
@Einstein: mouth closed, silent, no lip movement.
@TJ left-frame leaning toward the cradle, one arm gesturing.
@GermanBedroom. Camera: slow push in. Avoid: text, extras, photorealism.
```

---

## Lip Sync — Important Limitation

Elements do NOT help Kling pick which character to lip sync to. Kling's lip sync tool:
- Picks the most prominent/close-up face automatically
- You cannot direct it to a specific named element
- Workaround: ensure TJ has dominant screen presence and is closest to camera in speaking shots

Voice descriptions are still needed in prompts for native audio — elements contain no audio information.

---

## Element Limits

- Max 4 elements per prompt
- Mixing more than 4 = elements start being ignored
- If a scene has 2 characters + 1 scene element = 3 elements used, 1 slot spare
- Prompt overload (4 elements + long text prompt) causes failures — keep text short

---

## What Is Too Much

| Element type | Worth it? |
|---|---|
| TJ (all 4 reference images) | Yes — always |
| Historical character (1 image) | Yes — if they appear in 2+ shots |
| TJ recurring costume (@TJPie etc.) | Yes — if used more than once |
| TJ one-off costume | No — describe in text |
| Scene/location | Yes — if it appears in 2+ shots |
| One-off scene | No — describe briefly in text |

---

## Naming Convention
```
@TJ              — main character, always
@TJPie           — transformed TJ (pi symbol)
@Einstein        — historical character
@Victoria        — historical character
@GermanBedroom   — scene element
@AppleGarage     — scene element
```

---

*Research conducted March 2026. Sources: Kling official docs, fal.ai Kling O1 guide, Pollo AI guide, WaveSpeedAI, DataCamp Kling 3.0 guide.*
