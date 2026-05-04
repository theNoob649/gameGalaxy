"""Game Galaxy - Flask backend.

Serves the game catalog and the static game assets. All saves live in the
visitor's browser via localStorage; there is no database and no accounts.
"""

import os

from flask import Flask, abort, render_template


app = Flask(__name__)


GAMES = [
    {
        "slug": "memory-match",
        "title": "Memory Match",
        "category": "Casual",
        "blurb": "Flip cards two at a time. Match every pair to win.",
        "color": "#ff6b9d",
    },
    {
        "slug": "tic-tac-toe",
        "title": "Tic Tac Toe",
        "category": "Strategy",
        "blurb": "Three in a row. Play a friend or beat the computer.",
        "color": "#4ecdc4",
    },
    {
        "slug": "snake",
        "title": "Snake",
        "category": "Arcade",
        "blurb": "Eat, grow, and don't hit yourself.",
        "color": "#a8e6cf",
    },
    {
        "slug": "twenty-forty-eight",
        "title": "2048",
        "category": "Puzzle",
        "blurb": "Slide and merge tiles to reach 2048.",
        "color": "#ffd166",
    },
    {
        "slug": "minesweeper",
        "title": "Minesweeper",
        "category": "Puzzle",
        "blurb": "Reveal the grid without clicking a mine.",
        "color": "#7dd3fc",
    },
    {
        "slug": "flap",
        "title": "Flap!",
        "category": "Reflex",
        "blurb": "Tap to fly. Don't hit the pipes.",
        "color": "#fcd34d",
    },
    {
        "slug": "runner",
        "title": "Sky Runner",
        "category": "Reflex",
        "blurb": "Run forever. Jump the obstacles.",
        "color": "#c084fc",
    },
    {
        "slug": "word-guess",
        "title": "Word Guess",
        "category": "Word",
        "blurb": "Guess today's 5-letter word in 6 tries.",
        "color": "#fb7185",
    },
    {
        "slug": "coal-clicker",
        "title": "Coal Clicker",
        "category": "Idle",
        "blurb": "Click coal. Buy upgrades. Watch the numbers go up forever.",
        "color": "#f97316",
    },
    {
        "slug": "lockpick",
        "title": "Lockpick",
        "category": "Timing",
        "blurb": "Time the spinning pin. Crack lock after lock.",
        "color": "#fbbf24",
    },
    {
        "slug": "color-switch",
        "title": "Color Switch",
        "category": "Reflex",
        "blurb": "Bounce upward. Match the ball's color through every obstacle.",
        "color": "#a78bfa",
    },
    {
        "slug": "stack-tower",
        "title": "Stack Tower",
        "category": "Reflex",
        "blurb": "Stack falling blocks. Land perfectly to keep going.",
        "color": "#60a5fa",
    },
    {
        "slug": "draw-guess",
        "title": "Drawing & Guess",
        "category": "Creative",
        "blurb": "Get a prompt. Draw it. Save it. No judging — just fun.",
        "color": "#34d399",
    },
    {
        "slug": "trivia",
        "title": "Trivia",
        "category": "Knowledge",
        "blurb": "Open Trivia DB questions across a dozen categories.",
        "color": "#fb923c",
    },
    {
        "slug": "whack-a-mole",
        "title": "Whack-a-Mole",
        "category": "Reflex",
        "blurb": "Hit the moles, miss the bombs. Gold ones are worth +5.",
        "color": "#a3e635",
    },
    {
        "slug": "color-echo",
        "title": "Color Echo",
        "category": "Memory",
        "blurb": "Watch the sequence of colored tones. Repeat it perfectly.",
        "color": "#22d3ee",
    },
    {
        "slug": "typing-race",
        "title": "Typing Race",
        "category": "Skill",
        "blurb": "Type the falling words before they hit the bottom.",
        "color": "#0ea5e9",
    },
    {
        "slug": "gem-swap",
        "title": "Gem Swap",
        "category": "Match Puzzle",
        "blurb": "Swap adjacent gems. Match 3+ to clear. Chain reactions multiply.",
        "color": "#ec4899",
    },
    {
        "slug": "bubble-shooter",
        "title": "Bubble Shooter",
        "category": "Match Puzzle",
        "blurb": "Aim, fire, connect. Pop 3+ bubbles of the same color.",
        "color": "#8b5cf6",
    },
    {
        "slug": "tower-defense",
        "title": "Tower Defense",
        "category": "Strategy",
        "blurb": "Place towers along the path. Survive 20 waves.",
        "color": "#dc2626",
    },
]

GAMES_BY_SLUG = {g["slug"]: g for g in GAMES}


@app.context_processor
def inject_globals():
    return {"games": GAMES}


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/play/<slug>")
def play(slug):
    game = GAMES_BY_SLUG.get(slug)
    if not game:
        abort(404)
    return render_template("game.html", game=game)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
