const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');
const http = require('http');
const url = require('url');

const FACTS_FILE = path.join(__dirname, '..', 'data', 'facts', 'ranked', 'top_facts.json');
const PORT = 3000;

// Load facts once at startup
let facts;
try {
  facts = JSON.parse(fs.readFileSync(FACTS_FILE, 'utf8'));
  console.log(`Loaded ${facts.length} facts from top_facts.json`);
} catch (err) {
  console.error('Failed to load facts file:', err.message);
  process.exit(1);
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

function getDayKey(date) {
  return `${MONTH_NAMES[date.getMonth()]} ${date.getDate()}`;
}

// TEST MODE: April 1–5 only. Defaults to April 1 if today is outside that range.
const TEST_DAYS = ['April 1', 'April 2', 'April 3', 'April 4', 'April 5'];

function getActiveDayKey() {
  const today = new Date();
  const key = getDayKey(today);
  return TEST_DAYS.includes(key) ? key : 'April 1';
}

function findFact(dayKey) {
  return facts.find(f => f.day === dayKey) || null;
}

async function generateProductionPlan(dayKey, fact) {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY not set in .env file');
  }

  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const systemPrompt = `You are generating a script AND Kling video production plan for Daily Facts with TJ — an Instagram Reels channel.

TJ IS:
- Eccentric, funny, dry British guy, mid-twenties
- Has unexplained superpowers he uses completely casually — levitating, phasing through walls, shrinking, growing enormous, teleporting, riding things he shouldn't, hiding behind things too small
- Dry observational humour — unexpected witty asides, never forced. Jokes feel like genuine thoughts, not setups.
- Genuinely excited by facts. Talks like he's telling his mate something that just broke his brain.
- He is NOT slapstick. NOT over-the-top. The funniness comes from how naturally weird he is.
- For SERIOUS or DARK facts — no jokes whatsoever. Completely respectful. Still present and engaging. Tone matches the content always.

SCRIPT RULES:
- Write as many sections as the story naturally needs — minimum 4, maximum 8. Each section = one Kling clip.
- Target total video length: 45–58 seconds. Never under 40s, never over 60s.
- Each clip must be between 5–10 seconds. Never exceed 10s per clip.
- If a moment needs more time — add another clip rather than stretching one clip beyond 10s.
- Use ElevenLabs v3 audio tags: [upbeat] [rushed] [slows down] [deliberate] [pause] [emphasized] [dry] [starts laughing] [laughs] [laughs harder]
- Every word earns its place — no filler
- Short punchy sentences, vary the rhythm
- Every sentence ends with a full stop, even one-word lines
- Use ellipsis (...) for deliberate dramatic pause mid-thought
- Each section speakable in roughly the duration of its matching clip
- CLIP DURATION = ACTION TIME + DIALOGUE TIME + PAUSE TIME, capped at 10s minimum 5s:
  ACTION TIME: how long TJ's entrance takes before speaking (floating down/landing = 2s, phasing through wall = 1s, already in position = 0s)
  DIALOGUE TIME: word count in that clip's dialogue ÷ 2.5 (natural British speech pace)
  PAUSE TIME: add 0.5s per sentence for natural pauses between sentences
  REACTION TIME: if TJ reacts physically after speaking (raises eyebrow, shakes head, turns away) add 1–2s
  Round up to nearest second. Never below 5s. Cap at 10s.
  Never suggest 5s for a clip where TJ performs an entrance AND delivers more than one sentence.
  Always err longer — a slightly long clip beats a rushed one.
- TJ's dialogue in the script must match EXACTLY what is written in the Kling prompt

KLING PROMPT RULES:

SCENE CONTINUITY:
Scenes flow continuously — this is a short film not a slideshow. Each clip continues the same visual world. TJ moves through the world naturally between clips. Write each clip with awareness of where TJ was at the end of the previous clip. He does not teleport between scenes unless the story jumps to a dramatically different time or place, or when it is genuinely funnier to suddenly be somewhere ridiculous.

EVERY CLIP MUST HAVE A PURPOSE AND AN ARC:
A clip is not a vibe. It is not "TJ floating near something." Every clip must have a clear start state and a clear end state — something must change within it. TJ must arrive somewhere, do something, react to something, reveal something, or land a moment. If you cannot describe what changes between the first frame and the last frame of a clip, the clip has no purpose and must be rewritten.

Examples of clips with purpose:
- TJ phases through a garage wall → looks around → says his line → lands on a stool
- A wide reveal of the Colosseum → crowd noise builds → TJ drops into frame from above → looks up in awe
- TJ shrinks to the size of a circuit board → peers at it → it sparks → he recoils
Examples of clips with NO purpose (never write these):
- TJ floating near a building saying a line (where does he go? what happens?)
- TJ standing in a location describing it (description is not action)
- A wide shot that just sits there with nothing changing

TJ PRESENCE:
TJ does not need to be in every scene. Use creative judgement. Some scenes are better without him — a dramatic wide reveal, a scale shot. Other scenes are better with him — reacting, floating in the background, hiding behind something too small, phasing through a wall, shrinking to inspect something close up. Be specific and playful. He never just stands there.

TJ ENTRANCES — vary naturally based on what the scene needs:
- Phases through a wall or object
- Floats down from above
- Crawls out from behind something too small to hide behind
- Was already there, very small, then grows to normal size
- Flies in from off screen
- Creeps into the corner of the frame cautiously
- Teleports in with a small pop — only when dramatically or comically appropriate
- Already in the scene doing something he shouldn't be
- Not in the scene at all — let the visuals tell the story

VISUAL DIRECTION — THIS IS THE MOST IMPORTANT PART OF EVERY PROMPT:

SCENES MUST BE ALIVE. No static sprites. No characters standing in empty rooms. Every clip must feel like a real animated film frame — something is always happening, always moving, always interesting to look at.

WHAT MAKES A SCENE ALIVE:
- Weather: sun rays cutting through dust, candles flickering, rain on windows, steam from machinery
- Crowds: people going about their lives in the background — period-accurate clothing, gestures, activity
- Objects in motion: tools being used, papers flying, machines turning, animals present
- Light doing something: shadows moving, firelight, neon reflections, golden hour, flickering torches
- The environment breathing: curtains moving, smoke drifting, flags rippling, leaves in wind

VISUAL SPECIFICITY — NO GENERIC SETTINGS:
Name the real visual details. A 1977 Cupertino garage has circuit boards pinned to chipboard walls, a Heathkit oscilloscope, hand-drawn schematics taped above the workbench, empty coffee cups, bad lighting. Victorian London has particular fog texture, gaslight colours, cobblestone glistening wet. Ancient Rome has terracotta roof tiles, toga colours by social class, market stall chaos. Research the era. Put it in the prompt. This is what stops it looking like clip art.

DO NOT INVENT SPECIFIC FACTS:
Only describe things that would genuinely be there. If the story is about a garage startup, describe garages. If it's about a ship, describe that type of ship accurately. Do not add people or objects that contradict the historical record. The visual world is built from confirmed details plus reasonable period-accurate atmosphere — not imagination run wild.

TJ IS NEVER JUST STANDING THERE:
When TJ appears, he must be physically doing something interesting. Perched on something he shouldn't be on. Floating two inches off the ground without noticing. Shrinking to peer at a tiny object. Leaning into the frame from behind a pillar. Pulling something improbable from his pocket. Reacting with his whole body, not just his face. Even mid-dialogue — he's gesturing, moving, fidgeting with something anachronistic.

VISUAL COMEDY (light and funny facts only):
Layer in visual gags — reward viewers who look closely:
- A sign in the background says something absurd and relevant
- One person in the crowd is doing something completely wrong for the era
- Something is slightly the wrong scale — TJ's coffee cup is enormous, a historically important object is comically tiny
- A detail that only makes sense once you know the fact
Never explain the gag. Just put it there.

SERIOUS AND DARK FACTS:
No visual comedy. No gags. No TJ doing anything silly. Instead: cinematic weight. Dramatic lighting. Close-ups on hands, faces, significant objects. Wide shots that convey scale of loss or consequence. The visual atmosphere earns the gravity of the moment. Think Pixar handling a sad scene — still beautiful, still visually rich, but sombre.

MULTI-SHOT vs SINGLE SHOT:
Kling v3 can generate multiple camera angles in one clip (multi-shot mode). Use it when the extract frame workflow is NOT needed.
Set multiShot: true for:
- The LAST story clip (no extract frame needed — nothing comes after)
- Any clip where teleportTransition is true (continuity already broken)
- Any clip where tjInScene is false and the scene benefits from multiple angles (establishing shots, historical reveals, large-scale events)
Set multiShot: false for:
- Any clip that requires extract frame for the next clip's start frame (i.e. most clips with TJ in scene that are not the last clip)
Write multiShotReason as a brief explanation the user can read — e.g. "Last clip — no extract frame needed, multi-shot adds cinematic variety" or "Extract frame required for clip 3 — single shot maintains position continuity"

NATIVE AUDIO:
All dialogue — TJ and historical figures — is written directly in the Kling prompt in quotes.
Native Audio ON for virtually every clip. There is almost never a reason for silence.
TJ's dialogue must match his uploaded voice element exactly.
Historical figures CAN speak. Use real quotes where they exist. Invent dialogue for comedic effect — lean into it. Write it clearly attributed: 'Jobs turns to Wozniak and says: "This is either genius or the worst idea in human history."'

TJ FILLER LINES — FILLING SILENCE:
Any clip where TJ is present but not delivering core fact content — entrances, flying in, landing, walking through a scene — must still have him saying something. Never silence just because it's a transition moment.

These filler lines are NOT plot-relevant. They are weird glimpses into TJ's inner world:
- Random personal non-sequiturs: "Last night I dreamed a gummy bear came alive and just... stood there. Judging me."
- Stray facts that just occurred to him: "Did you know otters hold hands while they sleep? That's got nothing to do with this. Just thought I'd mention it."
- British-specific absurdity: "I could really go for a Jaffa Cake. Not a biscuit. Not a cake. Just a Jaffa Cake."
- Observations about where he is: arriving in ancient Rome and muttering "smells exactly like I thought it would. Worse, actually."
- Slightly unhinged enthusiasm: "Right. Right right right right right." — then he just stares for a second.
- Self-commentary: "I teleported into the wrong century twice this morning. It happens."

The tone is: genuine, weird, slightly unhinged, very British, never forced. These feel like actual thoughts that escaped. They are short — one or two sentences max. They make the viewer feel like they're watching someone real, not a script.

Use these in:
- Clip 1 arrival moment (before the fact begins — a single odd line as he lands/appears)
- Any clip with an extended entrance before dialogue
- Any establishing/wide shot clip — TJ narrates over it even if not physically in frame (voiceover)
- Any clip that would otherwise have dead air

The only clips that can have Native Audio OFF are pure atmospheric moments with no TJ — and even then, consider a voiceover.

STYLE — append to every single Kling prompt without exception:
'vibrant saturated cartoon illustration style, colourful, family friendly, cinematic lighting, same visual energy as a modern animated feature film, no photorealism, no live action'
For any clip featuring TJ also append: '@TJ character reference'

SERIOUS FACTS RULE:
If the fact involves tragedy, death, war, suffering, or significant human loss — no visual gags, no comedy TJ entrances, no jokes in script. TJ can be present but respectfully. Tone matches content.

ACCURACY:
Every claim must be factually accurate. No dramatic oversimplifications. Flag anything simplified or debated in the fact check.

VIDEO STRUCTURE — DO NOT DEVIATE:
The complete video always has this structure:
1. INTRO CLIP (10s, fixed, pre-generated): TJ delivers "What happened on [date]? Let's find out!" while flying through clouds. This is ALREADY DONE — do NOT write this line, this catchphrase, or any version of it in any section or klingClip.
2. TRANSITION CLIP (7s, generated per day): TJ flies through clouds toward the first location. Output this as transitionClip in the JSON.
3. STORY CLIPS (Clip 1–N): The story begins. Clip 1 is ALWAYS the arrival scene.

CLIP 1 — ARRIVAL SCENE:
Clip 1 begins with TJ arriving at the first location after flying in. He does NOT re-introduce himself. He does NOT say any version of "What happened on...". The story starts the moment he touches down, enters, or appears. Clip 1 should feel like the camera has followed TJ down from the sky and he hits the ground running — literally or otherwise.

STORY CLIP DURATION TARGET:
Intro (10s) + Transition (7s) = 17s fixed overhead. Story clips must total 28–41 seconds so the complete video reaches 45–58 seconds. Plan clip count and durations accordingly.

TRANSITION CLIP PROMPT:
Write transitionClip.prompt as a cinematic Kling prompt. Be specific and visually rich — name the place, the era, the light, the details below. This clip should feel like a genuine arrival, not a loading screen.

The clip MUST end with TJ physically at the destination — feet on the ground, hand on a door, dropped onto a surface, crouched outside a building. Whatever fits. The important thing is that the final frame is TJ arrived, not TJ still in the air. This final frame is extracted and used as the Start Frame for Story Clip 1, so it must place TJ exactly where Clip 1 begins.

Structure the prompt so the arrival is the climax — everything builds toward the landing. The journey (clouds, descent, destination appearing) is the setup. The landing is the payoff. Make sure Kling knows where this clip ends.

Camera follows from behind as TJ descends. End with standard style tag. Include @TJ character reference.

TJ mutters one short line mid-descent — a stray thought, dry observation, or random non-sequitur. Thinking aloud. Not addressing the viewer. Very British. Very TJ.

You must respond with a single valid JSON object. Do not include any text, markdown code fences, or anything outside the JSON.`;

  const userPrompt = `Today's date is ${dayKey}. Here is today's fact:

Title: ${fact.title}
Story: ${fact.story}

Generate a complete production plan as a JSON object. Use EXACTLY this structure but generate as many sections/clips as the story needs (minimum 4, maximum 8):

{
  "sections": [
    {
      "number": 1,
      "label": "Short descriptive label for this beat",
      "text": "Section text with v3 audio tags. Section 1 is the ARRIVAL SCENE — TJ has just landed or arrived at the first location. No catchphrase. No re-introduction. Story starts immediately on arrival.",
      "wordCount": 0,
      "duration": 0
    }
    /* ... repeat for each section, minimum 4, maximum 8. Last section ends with 'See you tomorrow for another daily fact!' */
  ],

  "transitionClip": {
    "prompt": "Kling prompt: TJ flying through clouds toward [specific destination]. Destination becoming visible below. No dialogue. Wind sounds. Ends with style tag.",
    "destination": "Brief label e.g. '1970s Silicon Valley' or 'Ancient Rome'"
  },

  "klingClips": [
    {
      "clipNumber": 1,
      "label": "Short specific label for this clip",
      "tjInScene": true,
      "tjEntrance": "Exactly how TJ enters — be creative and specific",
      "nativeAudio": true,
      "prompt": "Full Kling prompt. TJ dialogue in quotes. Ends with style tag and @TJ character reference.",
      "duration": 0,
      "durationNote": "Action: Xs + Dialogue: Ys + Pauses: Zs = Ws",
      "teleportTransition": false,
      "multiShot": false,
      "multiShotReason": "Single shot — extract frame needed for clip N continuity"
    }
    /* ... one clip per section, same count as sections array */
  ],

  "textOverlays": [
    "most impactful word, number or short phrase",
    "second most impactful",
    "third most impactful"
  ],

  "caption": "Punchy Instagram caption. Teases without spoiling. One relevant emoji. No hashtags. Under 150 characters.",

  "factCheck": [
    {
      "claim": "exact verifiable claim from the script",
      "status": "verified",
      "note": "brief confirmation note, source or caveat"
    }
  ]
}

IMPORTANT — calculate every 0 value:
- sections[*].wordCount = exact word count of that section's text (excluding v3 tags)
- sections[*].duration = ACTION_TIME + round(wordCount/2.5) + PAUSE_TIME(0.5s×sentences) + REACTION_TIME, minimum 5, maximum 10
- Story clips must total 28–41s (intro 10s + transition 7s = 17s fixed; total target 45–58s)
- klingClips must have the same number of entries as sections
- klingClips[*].duration = duration of its matching section
- klingClips[*].durationNote = human-readable breakdown, e.g. "Action: 2s + Dialogue: 4s + Pauses: 1s = 7s"
- klingClips[*].tjInScene = true only if TJ physically appears in the clip
- klingClips[*].nativeAudio = true only if the clip contains spoken dialogue
- klingClips[*].teleportTransition = true only if the scene jumps to a dramatically different time/place after this clip
- klingClips[*].multiShot = true if: clip is last, teleportTransition is true, or tjInScene is false for a wide/establishing shot
- klingClips[*].multiShotReason = brief plain-English reason the user can read
- klingClips[*].prompt must be fully written — dialogue in quotes, end with style tag, add @TJ character reference if TJ is in the scene
- transitionClip.prompt must be fully written — specific destination, no dialogue, ends with style tag
- transitionClip.destination = brief location label (e.g. "1970s Silicon Valley")
- The section[0].text is TJ's ARRIVAL dialogue, NOT the catchphrase. Start mid-story.`;

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }]
  });

  const text = response.content[0].text.trim();

  // Strip invalid JSON escape sequences (e.g. \' which Claude sometimes outputs)
  function sanitizeJson(s) {
    return s.replace(/\\([^"\\\/bfnrtu])/g, (_, c) => c);
  }

  // Try direct parse first, then extract JSON block
  try {
    return JSON.parse(sanitizeJson(text));
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('Could not parse JSON from API response. Raw: ' + text.slice(0, 300));
    return JSON.parse(sanitizeJson(match[0]));
  }
}


async function generateTransitionPromptAPI(fact, dayKey) {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY not set in .env file');
  }
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 300,
    messages: [{
      role: 'user',
      content: `Write a Kling video prompt for a 7-second transition clip. TJ — an eccentric dry British cartoon guy — is already flying through bright clouds (the intro clip ended with him in flight). He is flying toward the first location of today's fact.

Today's fact:
Title: ${fact.title}
Story: ${fact.story.slice(0, 400)}

Rules:
- Be visually specific and rich — name the place, era, time of day, what's visible below, the light and atmosphere
- The clip MUST end with TJ physically at the destination — feet on ground, hand on a surface, crouched on arrival. Not still flying. This final frame is extracted as the start frame for Story Clip 1, so it must place TJ exactly where Clip 1 begins.
- Structure the prompt so the arrival is the climax — journey is setup, landing is payoff. Make clear to Kling where the clip ends.
- Camera follows TJ from behind as he descends
- TJ mutters one short line mid-descent — a stray thought, dry observation, or random non-sequitur. Thinking aloud. Not addressing the viewer. Very British.
- Native Audio ON — wind + TJ's muttered line
- End exactly with: vibrant saturated cartoon illustration style, colourful, family friendly, cinematic lighting, same visual energy as a modern animated feature film, no photorealism, no live action @TJ character reference
- Write ONLY the Kling prompt, no other text, no preamble`
    }]
  });
  return response.content[0].text.trim();
}

const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);
  const { pathname } = parsed;

  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'GET' && pathname === '/') {
    const html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);

  } else if (req.method === 'GET' && pathname === '/api/fact') {
    const today = new Date();
    const actualKey = getDayKey(today);
    // Allow ?day=April+1 override
    const requestedDay = parsed.query.day;
    const dayKey = requestedDay && findFact(requestedDay) ? requestedDay : getActiveDayKey();
    const fact = findFact(dayKey);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      dayKey,
      fact,
      actualDate: actualKey,
      testMode: !TEST_DAYS.includes(actualKey)
    }));

  } else if (req.method === 'GET' && pathname === '/api/facts') {
    // Return lightweight list for the picker (day + title + score only)
    const list = facts.map(f => ({ day: f.day, title: f.title, score: f.score }));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(list));

  } else if (req.method === 'POST' && pathname === '/api/fact/save') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const { day, title, story } = JSON.parse(body);
        if (!day || !title || !story) throw new Error('Missing day, title or story');
        const idx = facts.findIndex(f => f.day === day);
        if (idx === -1) throw new Error(`No fact found for day: ${day}`);
        facts[idx].title = title.trim();
        facts[idx].story = story.trim();
        fs.writeFileSync(FACTS_FILE, JSON.stringify(facts, null, 2), 'utf8');
        console.log(`Saved edited fact for: ${day}`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, fact: facts[idx] }));
      } catch (err) {
        console.error('Save error:', err.message);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });

  } else if (req.method === 'POST' && pathname === '/api/transition-prompt') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
      try {
        const { fact, dayKey } = JSON.parse(body);
        if (!fact) throw new Error('Missing fact');
        const prompt = await generateTransitionPromptAPI(fact, dayKey);
        console.log(`Generated transition prompt for: ${dayKey}`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ prompt }));
      } catch (err) {
        console.error('Transition prompt error:', err.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });

  } else if (req.method === 'POST' && pathname === '/api/generate') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
      try {
        const { dayKey, fact } = JSON.parse(body);
        console.log(`Generating plan for: ${dayKey}`);
        const result = await generateProductionPlan(dayKey, fact);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (err) {
        console.error('Generate error:', err.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });

  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(PORT, () => {
  console.log(`\nDaily Facts with TJ`);
  console.log(`Running at http://localhost:${PORT}`);
  console.log(`Test mode active: April 1-5 only\n`);
});
