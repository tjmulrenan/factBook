const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');
const http = require('http');
const url = require('url');

const PORT = 3001;
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

function sanitizeJson(s) {
  return s.replace(/\\([^"\\\/bfnrtu])/g, (_, c) => c);
}

function parseJson(text) {
  // Strip markdown code fences
  const stripped = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const clean = sanitizeJson(stripped.trim());
  try { return JSON.parse(clean); } catch {}
  // Try object first, then array
  const objMatch = clean.match(/\{[\s\S]*\}/);
  if (objMatch) try { return JSON.parse(objMatch[0]); } catch {}
  const arrMatch = clean.match(/\[[\s\S]*\]/);
  if (arrMatch) try { return JSON.parse(arrMatch[0]); } catch {}
  throw new Error('Could not parse JSON. Raw: ' + text.slice(0, 300));
}

// ── Find 5 fact candidates ─────────────────────────────────────────────────
async function findFacts(date) {
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 4 }],
    messages: [{
      role: 'user',
      content: `Find 5 historical facts for a short-form Instagram reel about ${date}. The goal is scroll-stopping entertainment, not education.

USE WEB SEARCH to verify every fact before including it. Search for the specific event and confirm: (1) it happened on this exact date, (2) the specific details are accurate. Do not include any fact you cannot verify. Discard candidates where the colourful detail turns out to be embellished or unconfirmed.

DATE RULE — NON-NEGOTIABLE: Every fact must be something that specifically and verifiably happened ON this exact date. Not "around this time", not "during a period", not "approximately". Verified exact date only.

THE ONLY TEST THAT MATTERS: Would someone screenshot this and send it to a friend saying "you won't believe this"? If not, it doesn't qualify.

What actually works:
- ONE specific ridiculous detail that sounds made up but is real — a single valve, a poem rejection, two schoolboys with umbrellas. Specific beats broad every time.
- Famous person did something embarrassing, stupid, or absurd
- Massive consequence from a tiny, almost funny cause
- Coincidence so good it feels scripted
- A rule, word, product, or law we still use today that came from something completely ridiculous
- The gap between what powerful people claimed and what actually happened — painful irony, not political commentary
- Something where the underdog, the idiot, or the nobody accidentally wins

Avoid entirely:
- Well-known overused stories ("New Coke", "moon landing", "Rosa Parks bus") — novelty is everything
- Heavy or serious events with no absurd angle (wars, disasters, political speeches)
- Facts that require background knowledge to land — must hit in 3 seconds cold
- "Significant" but boring — textbook importance is irrelevant here
- Anything where the hook is "this was historically important"

The hook line must be a single sentence that could stand alone as a caption. If it needs context to be interesting, it's not good enough.

After searching and verifying, return ONLY a valid JSON array of exactly 5 objects, no markdown:
[
  {
    "title": "Punchy title, max 8 words — lead with the absurd detail not the event",
    "year": 1976,
    "location": "Specific place",
    "description": "2-3 sentences. The weird specific detail first, consequence second, punchline third. Write it like you're texting a friend something that just made you laugh out loud.",
    "whyItWorks": "1 sentence — what is the single detail that makes this sound made up.",
    "hookPotential": "The opening line of the reel — one sentence, cold, no context needed. Must work as a standalone caption.",
    "visualMoment": "The single most absurd or dramatic visual moment — what would stop someone mid-scroll."
  }
]

Only include facts you have verified via web search. Aim for variety across eras and topics.`
    }]
  });
  const textBlocks = response.content.filter(b => b.type === 'text');
  if (!textBlocks.length) throw new Error('No text block in findFacts response');
  return parseJson(textBlocks[textBlocks.length - 1].text);
}

// ── Swap one fact ──────────────────────────────────────────────────────────
async function swapFact(date, currentFacts, indexToSwap) {
  const exclude = currentFacts.map(f => `"${f.title}" (${f.year})`).join(', ');
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 3000,
    tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 3 }],
    messages: [{
      role: 'user',
      content: `Find ONE historical fact for a short-form Instagram reel about ${date}. Scroll-stopping entertainment only — not education.

USE WEB SEARCH to verify the fact before returning it. Confirm the exact date and that the specific details are accurate. Do not return a fact you cannot verify.

DATE RULE — NON-NEGOTIABLE: Must have specifically and verifiably happened ON this exact date.

Do NOT suggest any of these (already in use): ${exclude}

The only test: would someone screenshot this and send it to a friend saying "you won't believe this"?

What works: one specific ridiculous detail that sounds made up but is real, famous person doing something absurd or stupid, massive consequence from a tiny cause, painful irony between what was claimed and what happened, something where the underdog or the idiot accidentally wins.

Avoid: well-known overused stories, heavy events with no absurd angle, anything needing background knowledge to land, facts where the hook is "this was historically important".

After verifying, return ONLY a valid JSON object, no markdown:
{
  "title": "Punchy title, max 8 words — lead with the absurd detail",
  "year": 1976,
  "location": "Specific place",
  "description": "2-3 sentences. Weird specific detail first, consequence second, punchline third.",
  "whyItWorks": "1 sentence — the single detail that makes this sound made up.",
  "hookPotential": "Opening line of the reel — one sentence, cold, no context needed.",
  "visualMoment": "The most absurd or dramatic visual moment."
}

Must be verified, accurate, and different from the excluded facts.`
    }]
  });
  const textBlock = response.content.find(b => b.type === 'text');
  if (!textBlock) throw new Error('No text block in swapFact response');
  return parseJson(textBlock.text);
}

// ── Generate full video package for one selected fact ─────────────────────
async function generateVideoPackage(fact, date) {
  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 12000,
    messages: [{
      role: 'user',
      content: `Generate a complete short-form reel package for this historical fact.

Fact: ${fact.year} — ${fact.title} (${fact.location})
Date: ${date}
${fact.description}
Hook potential: ${fact.hookPotential}
Key visual: ${fact.visualMoment}

TARGET AUDIENCE: 16–35. Fast scrollers. They respond to irony, surprise, sharp delivery, and a payoff they didn't see coming.

NARRATOR — TJ:
TJ is an animated British character who appears physically in every shot. He is NOT realistic — modern cartoon style, like a Disney or Pixar character but less polished. Warm skin tone, brown hair, big expressive eyes, slightly goofy proportions, and a small dark moustache — the moustache is a key part of his look and must appear in every shot. Funny, slightly awkward, a bit silly. Sharp wit underneath the bumbling exterior. Dry, self-aware, occasionally chaotic. Think Simpsons HUMOUR — adult wit that still works for younger audiences, occasionally absurd, never preachy. He finds history genuinely interesting but can't help himself getting into trouble or doing daft things to people nearby. Everything is fully animated — no photorealism anywhere.

TJ OUTFIT RULE:
Before writing any prompts, decide on TJ's outfit for this fact. The outfit should be funny and themed to the subject — and it can go as far as TJ becoming the thing itself. It doesn't have to be a wearable costume — it can be a full character transformation: a giant red apple with arms, legs, and TJ's face on it for an Apple fact; a literal robot body with TJ's eyes blinking through the visor for a tech fact; a dollar bill with TJ's face in the portrait oval for a finance fact; a giant football with TJ's face and limbs for an NFL fact. Or it can be a more traditional funny outfit — oversized lab coat and thick glasses, full mascot uniform, tiny crown and velvet cape. The rule is: it should be immediately readable as connected to the fact, visually distinctive, and slightly absurd. TJ's eyes and expression must always be visible — they are how you know it's him. The outfit stays identical for every single shot — it never changes after Shot 1.

Scene 1 Shot 1: TJ is in his default outfit (white "I ❤ FACTS" t-shirt, blue jeans, white trainers). He clocks the camera, does a quick snappy gesture of some kind — invent something fresh and fitting for this fact — and the outfit instantly transforms into the themed outfit. The change is fast and cartoonish. TJ glances down at himself, reacts briefly, and moves on. No examples given — the gesture should be unique each time and feel natural for the character and setting. If the transformation turns TJ into an object or creature, the transformed form must immediately show TJ's big expressive eyes, small dark moustache, and wide cartoon mouth on its surface — these appear the moment the transformation completes, not after. They are what make it recognisably TJ and must be visually prominent from the first frame of the new form.

The chosen outfit or object form must be described in exhaustive detail in EVERY shot — not just Shot 1. Kling treats each shot prompt independently and will hallucinate or drift the costume if it isn't fully restated each time. Every prompt must include: shape, size, colour, texture, surface details, limbs, gloves, shoes, and all props. If TJ is an object, every prompt must also include: the exact colours and markings on the object's surface, the position and appearance of TJ's big expressive eyes, small dark moustache, and wide expressive cartoon mouth on the object's face. Never abbreviate. Never assume Kling remembers from the previous shot.

TJ IN SHOTS: TJ is physically present in every shot. He walks through the scene, leans into the action, pokes at things, nudges people, or reacts visibly to what's happening around him. He is part of the scene — not a floating head, not a presenter-to-camera overlay. He belongs in the shot even though he clearly doesn't belong in the time period.

DIALOGUE VOICE: TJ is sharp, dry, and genuinely into history. He reacts with real surprise, disbelief, or reluctant respect — naturally funny because his reactions are honest. Fast-paced. Always moving forward. No dramatic pauses, no theatrical beats, no dwelling. Land the line and get out.

BRITISH SLANG RULE: TJ drops in the occasional British word or phrase — "brilliant", "blimey", "mate", "spiffing", "cheers", "cor", "absolutely mental" — but only once or twice per script, only when it genuinely fits and gets a laugh. Never forced. Never every line. If it doesn't earn it, leave it out.

Line energy: sharp, direct, warm. Real names and numbers. Short punchy reactions for impact moments. Never try-hard.

VIDEO STRUCTURE — EXACTLY 2 SCENES:
Scene 1: Kling multi-shot — 15 seconds total. Three shots, durations must sum to exactly 15. Vary the durations to serve the pacing — a quick 3s reaction shot, a longer 7s establishing shot, a punchy 5s beat. Don't default to 5+5+5. SETUP: Shot 1 opens cold with the hook (most outrageous thing stated baldly), then date, then costume comment. Shots 2-3 establish context — who, where, what's building.
Scene 2: Kling multi-shot — 15 seconds total. Three shots, durations must sum to exactly 15. Same variety rule. PAYOFF: the thing happens, fallout, punchline.
Total runtime: 30 seconds. Valid duration splits per scene: e.g. 3+5+7, 4+6+5, 6+4+5, 3+7+5, 7+4+4 — whatever serves the story. Never 5+5+5 unless there's a genuine reason.

VOICEOVER SELECTION PROCESS:
1. Internally generate 10 complete scripts — all 6 shots written as a unit each time, including the closing line. Each script must flow naturally as one continuous piece of narration.
   STRUCTURAL VARIETY IS MANDATORY: the 10 candidates must use at least 4 different story entry points. Some lead with the most absurd image. Some lead with the consequence and work backwards. Some lead with TJ's baffled reaction to the situation. Some lead with the smallest, most specific detail. Do not tell the same story in the same order 10 times — if scripts 3 and 4 have the same structure, scrap one and try a different angle. Identical structure = automatic disqualification regardless of wording.
2. Before scoring, do a spoken aloud pass on each script: read every line as if delivering it at pace. Kill any line that sounds written rather than spoken. Kill any line where you would naturally take a breath mid-sentence for drama rather than rhythm. If a line wouldn't come out of a real person's mouth naturally, rewrite it until it does.
3. Score each complete script on these 8 metrics, each out of 10. Be ruthless — a 7 means genuinely good, a 9 means exceptional, a 10 means almost never. Most scripts should score 5-7 on most metrics. Force a real spread across the 10 candidates — if they're all scoring 60-70 you're being too generous:
   - HOOK (10): 8+ = a stranger who knows nothing stops scrolling and has to watch. 6 = decent but predictable opener. 4 = starts with date or context-setting, no urgency.
   - PACING (10): 8+ = durations feel designed for the story, no shot is the wrong length. 6 = works but some shots feel padded or rushed. 4 = 5+5+5 or cramming.
   - TJ VOICE (10): 8+ = sounds like a specific funny person, not a narrator. Every line has personality. 6 = mostly fine, occasional generic phrase. 4 = could have been written by anyone, reads like copy.
   - PAYOFF (10): 8+ = the final line lands hard and feels earned, genuinely funny or surprising. 6 = decent closer. 4 = ends with a summary or a soft landing.
   - CLARITY (10): The actual fact lands cleanly — one watch, you get it.
   - ECONOMY (10): 8+ = nothing could be cut. 6 = one or two redundant words. 4 = padding, over-explaining, says the same thing twice.
   - SPOKEN FLOW (10): 8+ = every line sounds like it came out of a real mouth. 6 = mostly natural, one awkward phrase. 4 = written English, not spoken English.
   - ARC (10): 8+ = Scene 1 and Scene 2 feel like two acts, genuine build and release. 6 = structure exists but tension doesn't build. 4 = flat, same energy throughout.
4. Total each script out of 80. Return the TOP 3 scoring scripts only.
5. Include each script's total score and a one-line note on its strongest quality.
6. The highest-scoring script is the recommended version.

VOICEOVER RULES:
- Each shot gets its own voiceover line, delivered by TJ in his own voice.
- The voiceover narrates INTO the shot — TJ reacts to what's happening on screen, not around it.
- Words and visuals belong together. TJ is IN the scene commenting on what he sees.
- Scene 1 Shot 1 STRUCTURE — in this exact order: (1) the hook — the most outrageous or surprising thing about this fact, stated cold as a single punchy sentence with no context. This is what stops the scroll. (2) the date — "Month cardinal" only, dropped in casually after the hook, not announced. (3) the costume comment — TJ's dry observation about what it means to BE this thing, not just acknowledging it. The laugh comes from the specific logic of the object, not the fact of the transformation. Keep the whole shot within word budget. ABSOLUTE RULE: if Shot 1 starts with the date or the month, that script is disqualified. The hook must be the first words out of TJ's mouth. No exceptions.
- The year may appear ONCE, naturally, somewhere in Scene 1. Nowhere else.
- The full date (month + day) appears only in Shot 1. Never again.
- Scene 1 builds the situation — TJ reacts to what he's seeing, not narrates it. He's surprised by the information, not briefing an audience on it. "An ice jam just turned the whole river off" not "An ice jam on Lake Erie blocked the entire river."
- Scene 2 delivers the consequence and payoff. TJ reacts to the fallout. Close with something punchy, dry, or a bit daft in a satisfying way. The closing line is the most important line in the script — spend the most time on it.
- Word budget per shot: TJ speaks at roughly 3 words per second for plain sentences, drops to ~2 words per second when dense with proper nouns, numbers, or years. Scale to the shot duration — a 3s shot fits ~8 plain words, a 5s shot ~14, a 7s shot ~20. Do not cram, do not pad. The shot duration should be chosen to fit the natural length of the line, not the other way around.
- NUMBER PRONUNCIATION RULE: All years, figures, and numbers must be written out exactly as they should be spoken — no numerals. Years are spoken as two pairs: 1976 → "nineteen seventy-six", 1781 → "seventeen eighty-one", 2003 → "two thousand and three". Large round numbers: $800 → "eight hundred dollars", $300 billion → "three hundred billion dollars". Never leave a numeral in the voiceover text — always spell it out in full so TTS reads it correctly. DATE ORDINALS: write as "Month cardinal" — "March fourteen" not "March fourteenth" and never "March the fourteenth". Cardinal form ("fourteen", "twenty-two") is always cleaner for TTS than ordinal form.
- HARD WORD RULE: Kling TTS mispronounces long or unusual words. First choice: replace with a simpler synonym that means the same thing ("physicist" → "scientist", "mathematician" → "maths genius", "entrepreneur" → "businessman", "philosopher" → "thinker", "nuclear" → keep but flag). If no good synonym exists, spell the word phonetically in the script so TTS reads it correctly: "physicist" → "fizzicist", "February" → "Feb-roo-airy", "Worcestershire" → "Wooster-sheer". Never use a word you are not confident TTS will handle cleanly — rewrite around it.
- If a shot voiceover would clearly overrun its duration, split the thought across two shots.
- PACE IS EVERYTHING: every second is precious. The script should feel like it's running slightly faster than comfortable — urgent, propulsive, always moving. No breath-catching. No theatrical pauses. If a line could be shorter and still land, make it shorter.
- Short punchy sentences are fine. Forward momentum matters more than sentence variety.
- Dark or serious facts: TJ stays dry and straight. Wit is earned, never forced.

VOICE CALIBRATION — TJ sounds like THIS:
Good lines (nail the voice):
- "He spent six years inventing a machine that did exactly what a pen already did."
- "The whole thing cost forty million dollars. The replacement cost three quid."
- "She filed the complaint. They filed it in the bin. She filed it again. They promoted her."
- "Turns out the world's most successful soft drink was originally marketed as a cure for headaches. It wasn't."
- "Nobody told the pilot the war was over. He kept going for another twenty-nine years. Brilliant."

Bad lines (narrator voice — NEVER write these):
- "On this remarkable day in history, something extraordinary was about to unfold."
- "What followed would change the course of events forever."
- "In a twist that nobody saw coming, the situation took a dramatic turn."
- "This seemingly small moment would have massive consequences."
- "And so it was that on this day, history was made."

The difference: good lines say the specific weird thing directly. Bad lines gesture at something interesting without saying it.

VOICEOVER ANTI-PATTERNS — never write these:
- Full date after Shot 1: BANNED.
- Year after Scene 1: BANNED.
- "change everything", "changed the world", "changed history": BANNED. Too vague, too cliché.
- "little did they know", "no one could have predicted": BANNED. Overused.
- Em-dashes used as dramatic pauses: BANNED. "He walked in — and then — boom" is exactly wrong. No pause-dashes anywhere.
- Ellipses used as trailing pauses: BANNED. "And then..." is dead air. Cut it.
- Rhetorical questions to build suspense: BANNED. "But wait — what happened next?" No. Just say what happened.
- No overexplaining. One sharp specific detail beats three general ones.
- Use real names — people, companies, places. Never be coy. If the story is about Apple, say Apple. If it's about Napoleon, say Napoleon. Vagueness kills the punch.
- Do NOT drop British slang into every line — once or twice per script max. If it's there just to remind the audience TJ is British rather than to make the line funnier, cut it.

Do NOT generate Kling prompts in this step. Visuals are generated separately after the user selects their preferred script.

CHARACTER ELEMENTS RULE: Only include a character in the "characters" array if they are a real named historical figure who is directly and specifically tied to this fact — someone the story is actually about. Do NOT include: unnamed extras, generic locals, background people, crowd members, or any character invented to populate a scene. If the fact has no named historical figures (e.g. a natural event, an architectural story, a statistic), return an empty characters array. For the Niagara Falls fact, for example, there are no named individuals — return []. For the Einstein birth fact, Einstein as a baby is the subject — include him. Quality over quantity: one real named character is better than three invented extras.

ELEVENLABS TAGS: sparingly. Only [emphasized] [upbeat] [excited] [laughs]. Never slow delivery.

Return ONLY a valid JSON object, no markdown:
{
  "factSummary": {
    "title": "...",
    "year": 0,
    "location": "...",
    "whyItWorks": "..."
  },
  "scripts": [
    {
      "version": 1,
      "score": 74,
      "scoreNote": "One-line note on this script's strongest quality — why it ranked first",
      "shots": [
        { "sceneNumber": 1, "shotNumber": 1, "duration": 4, "voiceover": "Month and day + blend-in line" },
        { "sceneNumber": 1, "shotNumber": 2, "duration": 6, "voiceover": "Setup — year may appear here" },
        { "sceneNumber": 1, "shotNumber": 3, "duration": 5, "voiceover": "Setup continues" },
        { "sceneNumber": 2, "shotNumber": 1, "duration": 5, "voiceover": "Payoff begins" },
        { "sceneNumber": 2, "shotNumber": 2, "duration": 7, "voiceover": "Consequence lands" },
        { "sceneNumber": 2, "shotNumber": 3, "duration": 3, "voiceover": "Closing line — punchy, dry, satisfying" }
      ],
      "fullScript": "All 6 shots joined as one flowing narration."
    },
    {
      "version": 2,
      "score": 68,
      "scoreNote": "One-line note on this script's strongest quality",
      "shots": [
        { "sceneNumber": 1, "shotNumber": 1, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 1, "shotNumber": 2, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 1, "shotNumber": 3, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 1, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 2, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 3, "duration": 0, "voiceover": "..." }
      ],
      "fullScript": "All 6 shots joined."
    },
    {
      "version": 3,
      "score": 61,
      "scoreNote": "One-line note on this script's strongest quality",
      "shots": [
        { "sceneNumber": 1, "shotNumber": 1, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 1, "shotNumber": 2, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 1, "shotNumber": 3, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 1, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 2, "duration": 0, "voiceover": "..." },
        { "sceneNumber": 2, "shotNumber": 3, "duration": 0, "voiceover": "..." }
      ],
      "fullScript": "All 6 shots joined."
    }
  ],
  "characters": [
    {
      "name": "Real named historical figure only — no unnamed extras",
      "role": "One phrase — their specific role in this fact",
      "chatgptPrompt": "Full body cartoon character, centre frame, plain white background, facing camera, mouth closed neutral expression. [Detailed physical description: height/build, hair colour and style, eye colour, notable facial features, age, era-appropriate clothing described specifically]. Art style: match the reference image exactly — 2000s Saturday morning cartoon, thick clean black outlines on every edge, flat cel shading with single soft highlight per surface, bright saturated colours, no gradients, no photorealism, no 3D rendering. This character must look clearly distinct from TJ — different build, different hair, different face shape."
    }
  ],
  "editingNotes": {
    "idealRuntime": "30 seconds",
    "pacingNotes": "...",
    "musicVibe": "...",
    "capCutSuggestions": "..."
  }
}`
    }]
  });
  const raw = response.content[0]?.text;
  if (!raw) throw new Error('Empty response from model');
  console.log('Raw response (first 500):', raw.slice(0, 500));
  const parsed = parseJson(raw);
  if (!parsed.factSummary || !parsed.scripts) {
    console.error('Unexpected response structure:', JSON.stringify(parsed).slice(0, 500));
    throw new Error('Model returned unexpected structure — check server logs');
  }
  return parsed;
}

// ── Generate visuals for a chosen script ───────────────────────────────────
async function generateVisuals(shots, fact, date) {
  const scriptText = shots.map(s => `S${s.sceneNumber}·${s.shotNumber} (${s.duration}s): ${s.voiceover}`).join('\n');
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    messages: [{
      role: 'user',
      content: `Generate Kling visual prompts for each shot in this short-form reel script.

Fact: ${fact.year} — ${fact.title} (${fact.location})
Date: ${date}

Script:
${scriptText}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ELEMENTS — HOW THIS WORKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All characters and scenes have been pre-built as Kling Elements. Elements carry full visual appearance — DO NOT re-describe what an element already shows (hair, build, outfit, face, art style). Describe only: action, motion, position in frame, camera, and audio.

Elements in use:
- @TJ — the animated cartoon host. Already defined visually. Never re-describe his appearance.
- Named historical figures only — only use @ElementName syntax for characters explicitly passed in the fact's characters array. These have real Kling elements built. No other characters get @ references.

UNNAMED PEOPLE: If a shot genuinely needs an incidental background person (a local, a soldier, a bystander), describe them inline in one sentence of plain text — never use @ElementName syntax for them. They must look clearly different from TJ: different build, different hair colour, different clothing, no moustache, no cartoon-exaggerated proportions. Prefer removing unnamed people entirely if the shot works without them — TJ + environment is almost always enough.

Target prompt length: 40–80 words per shot. Longer is worse — elements handle the visuals.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TJ — OUTFIT & TRANSFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before writing any prompts, decide on TJ's themed costume or object transformation for this fact. This will become a Kling element (@TJCostume) — so describe it ONCE in the tjOutfit field of the JSON. Do NOT repeat this description in the shot prompts — just reference @TJCostume.

The costume must be funny and specific to the fact. TJ can become an object (a giant apple, a football, a dollar bill) — if so, the object must have TJ's face (eyes, moustache, expressive mouth) clearly on its surface.

SCENE 1 SHOT 1 — TRANSFORMATION:
@TJ spots the camera, jumps and spins mid-air in an exaggerated cartoon spin with motion blur and sparkles, lands as @TJCostume. Quick and snappy.

OBJECT BEHAVIOUR RULE: When @TJCostume is an object or creature, every shot must describe @TJ doing something physically consistent with what that object actually is and how it naturally behaves or exists in the world. His actions, movement, and reactions should all come from the logic of that object's nature — not from generic human gestures. Think about what that object does, how it moves, what it reacts to, what its limitations are, and let that drive every action description. Invent fresh behaviour for each shot — never repeat the same action twice across the six shots.

LIP SYNC RULE: In every speaking shot, @TJ (or @TJCostume) must be front-facing, face unobstructed, dominant in frame. State: "@TJ faces camera directly, mouth visible." Kling locks lip sync to the most prominent forward-facing face.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE DESCRIPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
No scene elements. Describe the location inline in each shot using 3-5 words only: era + room type + 1-2 key props. The art style is anchored by @TJ — do not describe the art style in the prompt, just the place. Keep it tight: "eighteen-seventies German bedroom, wooden cradle" not a full inventory.

BACKGROUND GAG: In one mid-script shot include a small incidental visual gag related to @TJCostume — subtle, nobody reacts, one shot only. Invent fresh each time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE 1 SHOT 3 — GROUP SHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All characters + @TJ visible, stable poses, static camera. This frame is used as the starting image for Scene 2. End prompt with: "NOTE: @TJ is the animated cartoon character in [position] — he is the only speaker in subsequent shots."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIALOGUE & AUDIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dialogue block ALWAYS comes first in the prompt. TJ's line always first.

TJ's voice (use every time):
@TJ says in the voice of a young adult male, bright and slightly squeaky, cheerful British accent, quick-fire delivery: "[voiceover line]"

TJ drops a natural British word or phrase once or twice per script — only when it genuinely earns a laugh. Never forced.

Historical characters: derive voice from who they are — age, nationality, era, personality. Every character in a scene must sound distinct. If silent: "[Name]: mouth closed, silent, no lip movement." Every character's speaking status must be explicit — never implicit.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HARD RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ZERO NUMERALS anywhere in any prompt — Kling TTS reads the full prompt aloud. Use words: "eighteen-seventies" not "1879", "March fourteen" not "March 14".
- No unnamed extras, no crowd, no bystanders. If a shot has no named historical figures, TJ is alone — no invented background people.
- NEVER use @ElementName syntax for unnamed or incidental characters. @ references are for real Kling elements only.
- No captions, no on-screen text.
- No photorealism, no 3D rendering.
- Max 2500 characters per prompt — with elements, you should easily stay under 500.

PROMPT STRUCTURE per shot:
1. Dialogue (first — TJ first, all others marked speaking or silent)
2. @TJ / @TJCostume — position + action only (not appearance)
3. @CharacterName — position + action only (not appearance)
4. @SceneName — element reference replaces all setting description
5. Camera: one phrase. Lighting: one phrase.
6. Avoid: crowd, extras, text, captions, photorealism.

Return ONLY a valid JSON object, no markdown:
{
  "tjOutfit": "Full description of TJ's themed costume/object form — this is the element definition, written once here only",
  "tjCostumeElementName": "@TJCostume short name e.g. @TJPie",
  "shots": [
    { "sceneNumber": 1, "shotNumber": 1, "klingPrompt": "..." },
    { "sceneNumber": 1, "shotNumber": 2, "klingPrompt": "..." },
    { "sceneNumber": 1, "shotNumber": 3, "klingPrompt": "..." },
    { "sceneNumber": 2, "shotNumber": 1, "klingPrompt": "..." },
    { "sceneNumber": 2, "shotNumber": 2, "klingPrompt": "..." },
    { "sceneNumber": 2, "shotNumber": 3, "klingPrompt": "..." }
  ]
}`
    }]
  });
  return parseJson(response.content[0].text);
}

// ── Fact-check a script ────────────────────────────────────────────────────
async function checkScript(fact, scripts) {
  const allLines = scripts[0].shots.map(s => `S${s.sceneNumber}·${s.shotNumber}: ${s.voiceover}`).join('\n');
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 3000,
    tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 3 }],
    messages: [{
      role: 'user',
      content: `Fact-check the following voiceover script for a short video about this historical fact.

Fact: ${fact.year} — ${fact.title} (${fact.location})
${fact.description}

Script lines:
${allLines}

USE WEB SEARCH to verify specific claims — dates, numbers, names, quotes, statistics. For each line, check whether any specific claim is wrong, embellished, unverifiable, or subtly misleading. Only flag genuine issues — do not flag creative phrasing or dramatic emphasis that doesn't change the meaning.

For every flagged line, write a replacement that fixes the issue while keeping TJ's voice — sharp, dry, British, entertaining. Fix rules:
- If the claim is verifiably WRONG: replace with the correct fact
- If the claim is UNCERTAIN or UNVERIFIABLE: reframe with hedging language that makes it feel intentional rather than evasive — "reportedly", "locals said", "the story goes", "people claimed" etc. The line should still land well, just not state unconfirmed things as hard fact
- If the claim is EMBELLISHED beyond what's proven: soften the specific detail while keeping the energy of the line
- Keep the replacement the same length and same position in the story — it must still work as that shot's voiceover
- Keep all number pronunciation rules: no numerals, dates as "Month cardinal"

Return ONLY a valid JSON array, no markdown:
[
  {
    "sceneNumber": 1,
    "shotNumber": 1,
    "flag": "Specific issue — what is wrong or uncertain",
    "severity": "wrong" | "uncertain" | "embellished",
    "suggestion": "The full replacement voiceover line in TJ's voice"
  }
]

If a line has no issues, do not include it. If all lines are accurate, return an empty array [].`
    }]
  });
  const textBlocks = response.content.filter(b => b.type === 'text');
  if (!textBlocks.length) return [];
  try { return parseJson(textBlocks[textBlocks.length - 1].text); } catch { return []; }
}

// ── HTTP Server ────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);
  const { pathname } = parsed;
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'GET' && pathname === '/') {
    const html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(html);
  }

  if (req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      const send = (status, data) => {
        res.writeHead(status, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
      };
      try {
        const payload = JSON.parse(body);

        if (pathname === '/api/facts') {
          if (!payload.date) throw new Error('Missing date');
          console.log(`Finding facts for: ${payload.date}`);
          send(200, await findFacts(payload.date));

        } else if (pathname === '/api/swap') {
          const { date, facts, index } = payload;
          if (!date || !facts || index == null) throw new Error('Missing fields');
          console.log(`Swapping fact ${index + 1} for: ${date}`);
          send(200, await swapFact(date, facts, index));

        } else if (pathname === '/api/generate-video') {
          const { fact, date } = payload;
          if (!fact || !date) throw new Error('Missing fact or date');
          console.log(`Generating video package for: ${fact.title}`);
          send(200, await generateVideoPackage(fact, date));

        } else if (pathname === '/api/generate-visuals') {
          const { shots, fact, date } = payload;
          if (!shots || !fact || !date) throw new Error('Missing shots, fact or date');
          console.log(`Generating visuals for: ${fact.title}`);
          send(200, await generateVisuals(shots, fact, date));

        } else if (pathname === '/api/check-script') {
          const { fact, scripts } = payload;
          if (!fact || !scripts) throw new Error('Missing fact or scripts');
          console.log(`Fact-checking script for: ${fact.title}`);
          send(200, await checkScript(fact, scripts));

        } else {
          send(404, { error: 'Not found' });
        }
      } catch (err) {
        console.error(err.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`\nDaily Facts — Reel Builder`);
  console.log(`Running at http://localhost:${PORT}\n`);
});
