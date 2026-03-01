import random

CATEGORY_JOKES = {
    "Space Exploration": [
        "Why did the sun go to school? To get a little brighter!",
        "What do you call a tick on the moon? A luna-tick!",
        "Why did the cow want to become an astronaut? So it could walk on the moooon!",
        "How do you throw a space party? You planet!",
        "What did the alien say to the cat? Take me to your litter!"
    ],
    "Sporting Achievements": [
        "Why did the golfer bring two pants? In case he got a hole in one!",
        "What’s a runner’s favorite subject? Jog-raphy!",
        "Why are basketball players messy eaters? Because they always dribble!",
        "Why did the soccer player bring string to the game? To tie the score!",
        "What’s a frog’s favorite sport? Jump rope!"
    ],
    "Scientific Discoveries": [
        "What did the science book say to the math book? You've got problems!",
        "Why did the chemist keep his Nobel Prize medal in the freezer? Because he wanted a cool reaction!",
        "Why did the scientist take out the bell? Because it had no 'reaction'!",
        "What do you call an educated tube? A graduated cylinder!",
        "Why did the physics teacher break up with the biology teacher? There was no chemistry!"
    ],
    "Famous Portraits": [
        "Why did the painting go to art school? It wanted to brush up on its skills!",
        "What do artists do when they get cold? They put on another layer!",
        "Why couldn’t the sculpture tell a joke? It was too stone-faced!",
        "What’s a portrait’s favorite game? Freeze frame!",
        "Why was the picture sent to jail? It was framed!"
    ],
    "Political History": [
        "Why did the president bring a pencil to the party? To draw up some new ideas!",
        "What kind of tea do politicians drink? Proper-tea!",
        "Why did the king go to the dentist? To get his crown checked!",
        "How does a pirate vote? Aye for aye!",
        "Why did the mayor bring string to the meeting? To tie up loose ends!"
    ],
    "Global Conflicts": [
        "Why did the army recruit the music band? Because they had great marching skills!",
        "Why don’t generals use email? Too many attachments!",
        "What do you call a peaceful knight? Sir Render!",
        "Why was the cannon always calm? It was used to blowing off steam!",
        "What did one trench say to the other? Long time no siege!"
    ],
    "Artistic Movements": [
        "Why did the artist break up with the pencil? It just wasn’t sketching out!",
        "Why are painters great at relationships? They know how to draw people in!",
        "What do you call a painting that tells jokes? A pun-ting!",
        "What’s an artist’s favorite candy? Skittle-scapes!",
        "Why did the brush go to therapy? It had too many strokes of emotion!"
    ],
    "Technological Advances": [
        "Why was the computer cold? It left its Windows open!",
        "What’s a robot’s favorite snack? Computer chips!",
        "Why did the smartphone go to school? To improve its texting skills!",
        "Why was the computer tired when it got home? It had too many tabs open!",
        "Why did the tech nerd eat lightbulbs? He wanted a bright idea!"
    ],
    "Cultural Celebrations": [
        "Why did the skeleton not go to the party? He had no body to go with!",
        "Why was the broom late for the celebration? It swept in at the last minute!",
        "How do ghosts celebrate? They throw a boo-nanza!",
        "Why don’t balloons ever get invited back? They always let things pop off!",
        "What kind of music is always in style at celebrations? Pop!"
    ],
    "Environmental Moments": [
        "What did one tree say to the other on Earth Day? Leaf me alone!",
        "Why did the recycling bin get promoted? It was on a roll!",
        "What’s a squirrel’s favorite way to help the planet? Nutworking!",
        "Why don’t mountains ever argue? They just peak calmly!",
        "Why did the flower bring a phone? It wanted to call its buds!"
    ],
    "General": [
        "Why did the chicken join a band? Because it had the drumsticks!",
        "Why don't eggs tell jokes? They might crack up!",
        "Why did the banana go to the doctor? It wasn’t peeling well!",
        "What’s orange and sounds like a parrot? A carrot!",
        "Why did the teddy bear skip dessert? It was stuffed!"
    ]
}

def get_random_joke(category):
    jokes = CATEGORY_JOKES.get(category, CATEGORY_JOKES["General"])
    return random.choice(jokes)
