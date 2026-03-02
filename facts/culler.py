import json
import os
import re
import sys
from collections import defaultdict, Counter
from typing import List, Dict, Any
import random
import time

# ---- Anthropic exceptions (so retries don't NameError) ----
try:
    from anthropic._exceptions import (
        OverloadedError, RateLimitError, ServiceUnavailableError,
        APITimeoutError, APIConnectionError, APIStatusError
    )
except Exception:
    # Fall back gracefully if package layout differs
    OverloadedError = RateLimitError = ServiceUnavailableError = \
        APITimeoutError = APIConnectionError = APIStatusError = Exception

# --- NEW: optional preselected DOY from CLI args or environment ---
def _get_preselected_doy():
    # Accept: 3_factCuller.py 279   OR   3_factCuller.py --doy=279
    for arg in sys.argv[1:]:
        if arg.isdigit():
            return int(arg)
        if arg.startswith("--doy="):
            v = arg.split("=", 1)[1]
            if v.isdigit():
                return int(v)
    v = os.environ.get("FACTBOOK_DOY")
    return int(v) if (v and v.isdigit()) else None

# ==== NEW: Anthropic ranking ====
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # we'll error nicely later

# Config
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SCORED_FACTS_DIR, CULLED_FACTS_DIR
SCORED_DIR  = str(SCORED_FACTS_DIR)   # pick from here
CULLED_DIR  = str(CULLED_FACTS_DIR)   # save here
os.makedirs(CULLED_DIR, exist_ok=True)

CATEGORY_CAP = 20
FINAL_TARGET = 60  # <= CHANGED: "any facts after rank 60 go"
TOPCAT_REASSIGN_THRESHOLD = 0.3

# Model config (override with env var if desired)
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-1-20250805")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Optional runtime control
SKIP_CLAUDE = os.getenv("SKIP_CLAUDE") == "1"
MAX_FACTS_FOR_RANKING = int(os.getenv("MAX_FACTS_FOR_RANKING", "120"))  # soft cap

# --- Sport detection for "Full Beast Mode" (simple, fast heuristics) ---
# You can tweak or extend these patterns anytime.
SPORT_PATTERNS = [
    ("football", r"\b(football|nfl|quarterback|touchdown|super bowl)\b"),
    ("soccer",   r"\b(soccer|footballer|premier league|la liga|champions league|fifa|uefa)\b"),
    ("basketball", r"\b(basketball|nba|three-pointer|slam dunk)\b"),
    ("baseball", r"\b(baseball|mlb|home run|world series)\b"),
    ("tennis",   r"\b(tennis|wimbledon|us open|french open|australian open|grand slam)\b"),
    ("golf",     r"\b(golf|pga|masters tournament|ryder cup|open championship)\b"),
    ("cricket",  r"\b(cricket|ipl|ashes|test match|odi|t20)\b"),
    ("rugby",    r"\b(rugby|six nations|try|world cup rugby)\b"),
    ("boxing",   r"\b(boxing|heavyweight|knockout|wbc|wba|ibf|wbo)\b"),
    ("mma",      r"\b(mma|ufc|octagon)\b"),
    ("hockey",   r"\b(hockey|nhl|stanley cup)\b"),
    ("athletics", r"\b(athletics|track and field|100m|200m|relay|marathon|bolt)\b"),
    ("swimming", r"\b(swimming|olympic pool|freestyle|butterfly|backstroke|breaststroke)\b"),
    ("cycling",  r"\b(cycling|tour de france|giro d'italia|vuelta a españa)\b"),
    ("motorsport", r"\b(formula\s?1|f1|grand prix|nascar|indycar|motogp)\b"),
]

import re as _re
_COMPILED_SPORT_PATTERNS = [(name, _re.compile(rx, _re.IGNORECASE)) for name, rx in SPORT_PATTERNS]

def detect_sport(fact: Dict[str, Any]) -> str:
    """
    Heuristic sport extractor for 'Full Beast Mode' items.
    Looks in 'original' (and 'title' if present). Returns sport key or 'other'.
    """
    text = (fact.get("original") or "") + " " + (fact.get("title") or "")
    for name, pat in _COMPILED_SPORT_PATTERNS:
        if pat.search(text):
            return name
    return "other"

ALL_CATEGORIES = [
    "History's Mic Drop Moments",
    "World Shakers & Icon Makers",
    "Big Brain Energy",
    "Beyond Earth",
    "Creature Feature",
    "Vibes, Beats & Brushes",
    "Full Beast Mode",
    "Mother Nature's Meltdowns",
    "The What Zone",
    "Uncategorized",
]

# ---- pick-by-number helpers ----
NUMERIC_PREFIX_RE = re.compile(r"^\s*(\d+)_.*_scored\.json$", re.IGNORECASE)

def list_scored_files_by_prefix(directory):
    items = []
    for f in os.listdir(directory):
        m = NUMERIC_PREFIX_RE.match(f)
        if m:
            items.append((int(m.group(1)), f))
    items.sort(key=lambda t: (t[0], t[1].lower()))
    if not items:
        print("No numeric *_scored.json files found.")
        return []

    print("Valid *_scored.json files (choose by the NUMBER shown at the start of the filename):")
    for day_num, fname in items:
        print(f"{day_num}: {fname}")
    return items

def choose_file_by_daynum(items, preselected=None):
    valid_numbers = {day_num: fname for day_num, fname in items}

    # --- NEW: auto-pick if provided by arg/env ---
    if isinstance(preselected, int) and preselected in valid_numbers:
        print(f"\n(Auto-selected DOY) {preselected} → {valid_numbers[preselected]}")
        return valid_numbers[preselected]

    while True:
        raw = input("\nEnter the day number (e.g., 251): ").strip()
        if not raw.isdigit():
            print("Please enter a numeric day number (e.g., 251).")
            continue
        n = int(raw)
        if n in valid_numbers:
            return valid_numbers[n]
        print(f"No file starting with '{n}_' was found. Try again.")

# ---- existing helpers (mostly unchanged) ----
def serialize_selected(selected, overrides):
    out = []
    for f in selected:
        out.append({
            "id": f.get("id"),
            "year": f.get("year"),
            "original": f.get("original"),
            "score": f.get("score"),
            "is_kid_friendly": f.get("is_kid_friendly"),
            "category": primary_top_category(f, overrides),
            "rank": f.get("rank"),  # <= NEW
        })
    return out

def print_summaries(facts):
    scores = [f["score"] for f in facts if isinstance(f, dict) and "score" in f]
    c_90_100 = sum(1 for s in scores if 90 <= s <= 100)
    c_70_89  = sum(1 for s in scores if 70 <= s <= 89)
    c_40_69  = sum(1 for s in scores if 40 <= s <= 69)
    c_1_39   = sum(1 for s in scores if 1  <= s <= 39)

    kid_true  = sum(1 for f in facts if f.get("is_kid_friendly") is True)
    kid_false = sum(1 for f in facts if f.get("is_kid_friendly") is False)

    print("\n📊 Score Summary:")
    print(f"🎉 90–100: {c_90_100}")
    print(f"✅ 70–89: {c_70_89}")
    print(f"🤔 40–69: {c_40_69}")
    print(f"🚫 1–39:  {c_1_39}")

    print("\n🧒 Kid-Friendliness Summary:")
    print(f"👍 Kid-Friendly (true): {kid_true}")
    print(f"👎 Not Kid-Friendly (false): {kid_false}\n")

def primary_top_category_auto(fact):
    cats = fact.get("categories") or []
    if not cats:
        return "Uncategorized"
    max_score = max((c.get("score") or 0.0) for c in cats)
    top_names = [c.get("category") for c in cats
                 if (c.get("score") or 0.0) == max_score and c.get("category")]
    if not top_names:
        return "Uncategorized"
    return sorted(top_names, key=lambda s: s.lower())[0]

def primary_top_category(fact, overrides):
    fid = fact.get("id")
    if fid in overrides:
        return overrides[fid]
    return primary_top_category_auto(fact)

def top_category_score(fact):
    cats = fact.get("categories") or []
    if not cats:
        return 0.0
    return max((c.get("score") or 0.0) for c in cats)

def count_top_categories_tied(facts):
    counts = Counter()
    for f in facts:
        cats = f.get("categories") or []
        if not cats:
            counts["Uncategorized"] += 1
            continue
        max_score = max((c.get("score") or 0.0) for c in cats)
        tied = [c.get("category") for c in cats if (c.get("score") or 0.0) == max_score and c.get("category")]
        if tied:
            for name in tied:
                counts[name] += 1
        else:
            counts["Uncategorized"] += 1
    return counts

def truncate(text, n=120):
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"

def interactive_reassign_low_confidence(sorted_facts):
    overrides = {}
    candidates = [f for f in sorted_facts if top_category_score(f) < TOPCAT_REASSIGN_THRESHOLD]
    if not candidates:
        return overrides

    print(f"\n✍️ Reassign low-confidence categories (best < {TOPCAT_REASSIGN_THRESHOLD}): {len(candidates)} facts")

    for f in candidates:
        fid = f.get("id")
        original = f.get("original") or ""
        best_auto = primary_top_category_auto(f)
        best_score = top_category_score(f)

        fact_cats = f.get("categories") or []
        fact_cats_sorted = sorted(
            [c for c in fact_cats if c.get("category")],
            key=lambda c: (-(c.get("score") or 0.0), c.get("category").lower())
        )
        ordered_names = [c["category"] for c in fact_cats_sorted]
        for name in sorted(ALL_CATEGORIES, key=str.lower):
            if name not in ordered_names:
                ordered_names.append(name)

        print("\n------------------------------------------------------------")
        print(f"ID {fid} | Score {f.get('score')} | Best cat: {best_auto} ({best_score:.2f})")
        print(f"Text: {truncate(original)}")
        print("Choose new category (or 0 to keep current):")
        for i, name in enumerate(ordered_names, 1):
            sc = next((c.get("score") for c in fact_cats_sorted if c.get("category") == name), None)
            score_str = f" — catScore {sc:.2f}" if isinstance(sc, (int, float)) else ""
            print(f"  {i}. {name}{score_str}")
        choice = input(f"Your choice [0..{len(ordered_names)}]: ").strip()

        if choice == "" or choice == "0":
            continue
        try:
            idx = int(choice)
            if 1 <= idx <= len(ordered_names):
                overrides[fid] = ordered_names[idx - 1]
        except ValueError:
            pass

    return overrides

def primary_counts_with_overrides(facts, overrides):
    return Counter(primary_top_category(f, overrides) for f in facts)

def interactive_reassign_post_selection(sorted_all, final_selected, overrides):
    """
    Auto-fix only categories that have exactly 1 primary, without changing WHICH 60 facts
    are selected. We lock the membership to the current final_selected IDs and only
    update their primary categories via overrides.

    Dynamic protection: as soon as any category reaches >= 2 primaries during the process,
    it becomes protected and will never be reduced below 2 later in the run.
    """
    MIN_PROTECT = 2
    ov = dict(overrides)
    tried = set()  # (fact_id, dest_cat) attempts we already tried
    max_passes = 50

    # ---- Lock the membership to the current 60 facts ----
    selected_ids = [f.get("id") for f in final_selected]
    by_id = {f.get("id"): f for f in sorted_all}  # to fetch full objects by id

    # Build the locked list in the same order as final_selected
    def _locked_list():
        return [by_id[fid] for fid in selected_ids if fid in by_id]

    # Compute primary counts under current overrides for the locked set
    def _locked_counts():
        locked = _locked_list()
        return Counter(primary_top_category(f, ov) for f in locked)

    # Per-fact alternative categories in preference order (by cat score desc, then name)
    def _ordered_alternatives(fact, current_cat):
        cats = fact.get("categories") or []
        ordered = sorted(
            [c for c in cats if c.get("category")],
            key=lambda c: (-(c.get("score") or 0.0), c.get("category").lower())
        )
        return [c["category"] for c in ordered if c["category"] != current_cat]

    # === Initial protections: anything already at >= 2 is protected
    baseline_counts = _locked_counts()
    protected_cats = {cat for cat, n in baseline_counts.items() if n >= MIN_PROTECT}

    print("\n================ REASSIGN (LOCKED 60) ================")
    print("🔒 Initially protected (≥2 at snapshot):")
    if protected_cats:
        for c in sorted(protected_cats):
            print(f"  • {c}: {baseline_counts.get(c, 0)}")
    else:
        print("  • (none)")

    print("\n📌 Snapshot primary counts:")
    for name, count in sorted(baseline_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        print(f"  • {name}: {count}")

    for pass_idx in range(1, max_passes + 1):
        counts = _locked_counts()
        print(f"\n—— Pass {pass_idx} — Current locked primary counts ——")
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            prot = " 🔒" if name in protected_cats else ""
            print(f"  • {name}: {count}{prot}")

        # only singletons are allowed to change
        singles = [cat for cat, n in counts.items() if n == 1]
        if not singles:
            print("\n✅ No singletons remain. Reassignment done.")
            return ov

        moved_any = False
        locked_now = _locked_list()

        for cur_cat in singles:
            # cur_cat will never be in protected_cats because protected means >=2
            items = [f for f in locked_now if primary_top_category(f, ov) == cur_cat]
            if not items:
                print(f"⚠️  No item found for singleton '{cur_cat}' (unexpected).")
                continue
            fact = items[0]
            fid = fact.get("id")

            # alternatives in per-fact preference order
            alts = _ordered_alternatives(fact, cur_cat)
            print(f"\n🔎 Singleton: '{cur_cat}' — ID {fid}")
            print("   Alternatives by per-fact catScore (best→worst):")
            cat_scores = {c.get("category"): (c.get("score") or 0.0) for c in (fact.get("categories") or [])}
            for nm in alts:
                print(f"     - {nm} (score {cat_scores.get(nm, 0.0):.2f})")

            if not alts:
                print("   ↪️  No alternatives available. Leaving as-is.")
                continue

            # prefer destinations already present (>0), largest first; then empties
            existing = [
                d for d in alts
                if counts.get(d, 0) > 0 and counts.get(d, 0) < CATEGORY_CAP and (fid, d) not in tried
            ]
            existing.sort(key=lambda d: counts.get(d, 0), reverse=True)
            empties  = [
                d for d in alts
                if counts.get(d, 0) == 0 and counts.get(d, 0) < CATEGORY_CAP and (fid, d) not in tried
            ]
            candidates = existing + empties

            if not candidates:
                print("   ↪️  No viable destinations (hit cap or already tried). Leaving as-is.")
                for d in alts:
                    tried.add((fid, d))
                continue

            chosen = None
            for dest in candidates:
                # Tentatively move this fact's primary to dest
                ov[fid] = dest
                after = _locked_counts()

                # Constraint A: source singleton must stop being 1 (becomes 0 or ≥2)
                source_fixed = (after.get(cur_cat, 0) != 1)

                # Constraint B: we must not reduce any currently protected category below 2
                # (note: protected_cats is dynamic and can grow during the loop)
                reduces_protected = any(after.get(pc, 0) < MIN_PROTECT for pc in protected_cats)

                print(
                    f"   • Try '{cur_cat}' → '{dest}': "
                    f"after[{cur_cat}]={after.get(cur_cat,0)}; "
                    f"after[{dest}]={after.get(dest,0)}; "
                    f"protected_ok={not reduces_protected}"
                )

                if source_fixed and not reduces_protected:
                    # Commit the move
                    print(f"   ✅ CHOSEN: ID {fid} '{cur_cat}' → '{dest}'")
                    moved_any = True
                    chosen = dest

                    # 🔒 Dynamic protection: any category that now has >= 2 becomes protected
                    newly_protected = {c for c, n in after.items() if n >= MIN_PROTECT} - protected_cats
                    if newly_protected:
                        for np in sorted(newly_protected):
                            print(f"   🔒 Now protecting '{np}' (reached {after.get(np,0)})")
                        protected_cats |= newly_protected
                    break
                else:
                    # Roll back and mark tried
                    ov.pop(fid, None)
                    tried.add((fid, dest))
                    why = []
                    if not source_fixed:
                        why.append("source still singleton")
                    if reduces_protected:
                        why.append("would reduce a protected category < 2")
                    print(f"   ⛔ SKIP '{dest}' — {', '.join(why)}")

            if not chosen:
                print("   ↪️  No destination passed constraints. Leaving as singleton for now.")
                for d in alts:
                    tried.add((fid, d))

        if not moved_any:
            print("\n🛑 No safe moves possible this pass. Stopping.")
            return ov

    print("\n🛑 Hit max passes without resolving all singletons. Returning best-effort overrides.")
    return ov

def rebuild_with_overrides(sorted_all_ranked, overrides):
    """
    Build FINAL_TARGET in global rank order while enforcing:
      • Per-category cap: max CATEGORY_CAP per primary category
      • Full Beast Mode per-sport cap: max 3 per detected sport
      • If a 4th (or more) of the same sport appears and has a higher 'score'
        than one of the selected 3, replace the lowest-scoring one (swap-in).
    This guarantees we keep walking the ranked pool until we reach FINAL_TARGET (60),
    unless there just aren't enough kid-friendly facts available.
    """
    selected = []                      # keep in rank order
    selected_ids = set()
    cat_counts = Counter()
    fmb_sport_counts = Counter()
    # keep indices of selected items per sport for quick replacement checks
    fmb_sport_indices: Dict[str, List[int]] = {}

    def primary_cat(f):
        return primary_top_category(f, overrides)

    for idx, fact in enumerate(sorted_all_ranked):
        if len(selected) >= FINAL_TARGET:
            break
        fid = fact.get("id")
        if fid in selected_ids:
            continue

        cat = primary_cat(fact)

        # Per-category cap check
        if cat_counts[cat] >= CATEGORY_CAP:
            # skip but continue scanning; we'll backfill from other categories
            continue

        # Full Beast Mode: enforce per-sport <= 3 with "replace lowest score" logic
        if cat == "Full Beast Mode":
            sport = detect_sport(fact)
            cur_score = fact.get("score", 0) or 0

            if fmb_sport_counts[sport] < 3:
                # Accept directly
                selected_ids.add(fid)
                selected.append(fact)
                cat_counts[cat] += 1
                fmb_sport_counts[sport] += 1
                fmb_sport_indices.setdefault(sport, []).append(len(selected) - 1)
                continue
            else:
                # Already have 3 of this sport; see if this one is better than the worst of those 3
                sport_sel_indices = fmb_sport_indices.get(sport, [])
                if not sport_sel_indices:
                    # Shouldn't happen, but guard anyway
                    continue

                # Find the lowest-scoring among selected items for this sport
                worst_idx = None
                worst_score = float("inf")
                for si in sport_sel_indices:
                    s_item = selected[si]
                    s_score = s_item.get("score", 0) or 0
                    if s_score < worst_score:
                        worst_score = s_score
                        worst_idx = si

                if worst_idx is not None and cur_score > worst_score:
                    # Replace the worst with the current fact
                    old_item = selected[worst_idx]
                    old_id = old_item.get("id")

                    # Swap in place to preserve overall positional order
                    selected[worst_idx] = fact
                    selected_ids.remove(old_id)
                    selected_ids.add(fid)

                    # Update the per-sport index list for this sport (position stays same)
                    # (No change to cat_counts or fmb_sport_counts totals)
                    # Nothing else to do; we also keep scanning for more to reach 60
                    continue
                else:
                    # Not better than the existing top-3 -> skip
                    continue

        # Non-Full-Beast-Mode: accept if category has capacity
        selected_ids.add(fid)
        selected.append(fact)
        cat_counts[cat] += 1

    # If we somehow didn't reach 60 (e.g., not enough inputs), we just return what we have.
    # Remove any transient fields you don't want to persist.
    for fct in selected:
        fct.pop("max_word_limit", None)

    # --- Reporting similar to your old logs ---
    print("\n🔧 Per-category counts (after selection, cap = 20):")
    for name, count in sorted(cat_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        print(f"• {name}: {count}")
    if len(selected) < FINAL_TARGET:
        print(f"\n(BELOW THRESHOLD) Only {len(selected)} facts available after applying caps and rules.")
    else:
        print(f"\n✅ Filled {FINAL_TARGET} items under caps and sport rules.")

    return selected

# ==== NEW: Claude ranking ====
RANK_SYSTEM_PROMPT = (
    "You are ranking historical/on-this-day facts for a children's factbook (ages 8–12). "
    "All given facts are already screened as kid-friendly. Rank them from MOST exciting/engaging "
    "(rank 1) to LEAST (higher rank numbers). Give extra credit for: clear wow-factor, "
    "modern relevance to a 12-year-old, fun twist or discovery, inspiring people/inventions. "
    "Downweight: flat/boring items, first TV/radio/award debuts unless something uniquely special happened, "
    "concerts/songs without broader impact, or obscure references. Output STRICT JSON: "
    "{\"ranking\":[{\"id\":<id>,\"rank\":<int>}, ...]} with contiguous ranks starting at 1."
)

def build_rank_user_prompt(facts: List[Dict[str, Any]]) -> str:
    # Keep the prompt compact: id, year, original, score (score is just metadata)
    lines = ["Rank these facts (most exciting for ages 8–12 first). Facts:"]
    for f in facts:
        fid = f.get("id")
        yr = f.get("year")
        orig = (f.get("original") or "").replace("\n", " ").strip()
        sc = f.get("score")
        lines.append(f"- id:{fid} | year:{yr} | score:{sc} | text:{orig}")
    lines.append("\nReturn JSON only as: {\"ranking\":[{\"id\":ID,\"rank\":RANK}, ...]}")
    return "\n".join(lines)

def rank_with_claude(facts: List[Dict[str, Any]]) -> Dict[Any, int]:
    """
    Calls Anthropic Messages API to get a ranking, with retries on overload/ratelimit.
    Returns a dict {id: rank}. Falls back to score-based order if all retries fail.
    """
    if Anthropic is None:
        raise RuntimeError("anthropic package not installed. pip install anthropic")
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment.")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    user_prompt = build_rank_user_prompt(facts)

    # Exponential backoff (0s immediate try + 1,2,4,8,16s)
    delays = [0, 1, 2, 4, 8, 16]
    last_err = None

    for attempt, delay in enumerate(delays, 1):
        if delay:
            print(f"⏳ Anthropic busy (attempt {attempt}/{len(delays)}). Retrying in {delay}s...")
            time.sleep(delay + random.uniform(0, 0.3))

        try:
            resp = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=2048,
                system=RANK_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0
            )
            # Extract text
            text = ""
            for block in resp.content:
                if getattr(block, "type", "") == "text":
                    text += block.text

            # Parse JSON
            data = json.loads(text)
            ranking_list = data.get("ranking", [])
            out = {item["id"]: int(item["rank"]) for item in ranking_list}

            # Basic sanity: if ranks are missing, fall back below
            if sorted(out.values()) != list(range(1, len(facts) + 1)):
                raise ValueError("Non-contiguous ranks from model")

            return out

        except (OverloadedError, RateLimitError, ServiceUnavailableError,
                APITimeoutError, APIConnectionError) as e:
            last_err = e
            continue
        except APIStatusError as e:
            # Retry only on transient HTTP codes
            code = getattr(e, "status_code", None)
            if code in (408, 409, 429, 500, 502, 503, 504, 529):
                last_err = e
                continue
            raise
        except Exception as e:
            # Non-transient parse/other error: break to fallback
            last_err = e
            break

    print(f"⚠️ Claude unavailable or response invalid ({type(last_err).__name__}): {last_err}. Falling back to score order.")
    fallback = sorted(
        [(f.get("id"), f.get("score", 0)) for f in facts],
        key=lambda t: -t[1]
    )
    return {fid: i + 1 for i, (fid, _) in enumerate(fallback)}
# ====================== MAIN ======================
def main():
    items = list_scored_files_by_prefix(SCORED_DIR)
    if not items:
        return

    pre = _get_preselected_doy()  # <-- NEW
    chosen = choose_file_by_daynum(items, preselected=pre)  # <-- pass it in
    in_path = os.path.join(SCORED_DIR, chosen)
    base = chosen[:-len("_scored.json")]
    out_name = f"{base}_culled.json"
    out_path = os.path.join(CULLED_DIR, out_name)

    with open(in_path, "r", encoding="utf-8") as f:
        facts = json.load(f)

    print("Initial totals:")
    print_summaries(facts)

    # === NEW: hard filter out non-kid-friendly ===
    kid_friendly = [fact for fact in facts if fact.get("is_kid_friendly") is True]
    print("\nAfter removing NOT kid-friendly facts:")
    print_summaries(kid_friendly)

    if not kid_friendly:
        print("No kid-friendly facts to rank. Exiting.")
        return

    # Optionally trim the set we send to the model to keep prompts sane
    facts_for_model = kid_friendly
    if len(facts_for_model) > MAX_FACTS_FOR_RANKING:
        # keep the highest-scoring N as candidates (deterministic)
        facts_for_model = sorted(
            facts_for_model, key=lambda x: -(x.get("score") or 0)
        )[:MAX_FACTS_FOR_RANKING]
        print(f"✂️ Capped facts for ranking to top {MAX_FACTS_FOR_RANKING} by score "
            f"(from {len(kid_friendly)} kid-friendly).")

    # === Rank with Claude or bypass ===
    if SKIP_CLAUDE:
        print("⏭️ SKIP_CLAUDE=1 — ranking by score only.")
        ranked_ids = [f.get("id") for f in sorted(
            facts_for_model, key=lambda x: -(x.get("score") or 0)
        )]
        id_to_rank = {fid: i + 1 for i, fid in enumerate(ranked_ids)}
    else:
        print("🔎 Ranking remaining facts with Claude…")
        id_to_rank = rank_with_claude(facts_for_model)

    # Attach rank (items not sent to the model get a large rank so they backfill)
    for f in kid_friendly:
        f["rank"] = id_to_rank.get(f.get("id"), 10**9)


    # Keep the whole pool so we can backfill from rank 61, 62, 63, ...
    ranked_all = sorted(
        kid_friendly,
        key=lambda x: (x.get("rank", 10**9), x.get("id", float("inf")))
    )

    # === Your existing category reassignment workflow, now based on rank order ===
    overrides = interactive_reassign_low_confidence(ranked_all)
    final_selected = rebuild_with_overrides(ranked_all, overrides)

    payload = serialize_selected(final_selected, overrides)
    with open(out_path, "w", encoding="utf-8") as f_out:
        json.dump(payload, f_out, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved: {out_name}  ({len(payload)} facts)")

    leaders = count_top_categories_tied(final_selected)
    if leaders:
        print("\n🏷️ Category leaders (top-category count in final selection):")
        for name, count in sorted(leaders.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"• {name}: {count}")
    primary_counts = Counter(primary_top_category(f, overrides) for f in final_selected)
    if primary_counts:
        print("\n🗂️ Primary category counts (final selection):")
        for name, count in sorted(primary_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"• {name}: {count}")

    overrides = interactive_reassign_post_selection(ranked_all, final_selected, overrides)

    print("\n🔄 Rebuilding selection with your reassignments...")
    final_selected = rebuild_with_overrides(ranked_all, overrides)
    payload = serialize_selected(final_selected, overrides)
    with open(out_path, "w", encoding="utf-8") as f_out:
        json.dump(payload, f_out, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved (after reassignment): {out_name}  ({len(payload)} facts)")

    leaders = count_top_categories_tied(final_selected)
    if leaders:
        print("\n🏷️ Category leaders (top-category count in final selection):")
        for name, count in sorted(leaders.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"• {name}: {count}")
    primary_counts = Counter(primary_top_category(f, overrides) for f in final_selected)
    if primary_counts:
        print("\n🗂️ Primary category counts (final selection):")
        for name, count in sorted(primary_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"• {name}: {count}")

if __name__ == "__main__":
    main()
