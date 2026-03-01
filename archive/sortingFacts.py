import json
import os
import sys

# ---- CATEGORY KEYWORDS ----
CATEGORIES = {
    Space Exploration [nasa, space, moon, astronaut, mercury, mars, apollo, probe, cosmos],
    Sporting Achievements [football, basketball, tennis, olympics, world cup, ski, baseball, cricket],
    Scientific Discoveries [scientist, discovery, experiment, physicist, biologist, chemist, invention],
    Political History [president, prime minister, government, election, parliament, treaty, coup, senator],
    Technological Advances [internet, dot-com, tech, software, machine, device, robot, ai, app, program],
    Artistic Movements [composer, painter, author, artist, actor, director, sculptor, musician, poet],
    Famous Portraits [born, footballer, musician, actor, writer, scientist, president],
    Global Conflicts [war, military, rebellion, coup, bombing, uprising, battle, espionage],
    Cultural Celebrations [holiday, festival, celebration, tradition, custom, anniversary]
}

# ---- FUNCTION TO CATEGORIZE FACTS ----
def categorize_facts(facts_data)
    categorized = {category [] for category in CATEGORIES}
    uncategorized = []

    all_facts = facts_data.get(Wikipedia, {}).get(Events, []) + facts_data.get(Fun Facts, [])

    for fact in all_facts
        fact_lower = fact.lower()
        matched = False

        for category, keywords in CATEGORIES.items()
            if any(keyword in fact_lower for keyword in keywords)
                categorized[category].append(fact)
                matched = True
                break

        if not matched
            uncategorized.append(fact)

    categorized[Uncategorized] = uncategorized
    return categorized

# ---- MAIN FUNCTION ----
def main(input_file)
    if not os.path.exists(input_file)
        print(f❌ File not found {input_file})
        return

    with open(input_file, r, encoding=utf-8) as f
        facts_data = json.load(f)

    sorted_facts = categorize_facts(facts_data)

    # Generate output filename
    base = os.path.basename(input_file).replace(.json, )
    output_file = f{base}_sorted.json

    with open(output_file, w, encoding=utf-8) as f
        json.dump(sorted_facts, f, indent=4, ensure_ascii=False)

    print(f✅ Facts sorted and saved to {output_file})

# ---- RUN SCRIPT ----
if __name__ == __main__
    if len(sys.argv)  2
        print(Usage python sortingFacts.py [Month]_[Day].json)
    else
        main(sys.argv[1])
