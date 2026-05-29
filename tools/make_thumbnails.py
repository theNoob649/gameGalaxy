"""Generate gameplay thumbnails by scripting each game in a headless browser.

Usage:
    python tools/make_thumbnails.py snake
    python tools/make_thumbnails.py --all

For each slug, the script:
  1. Opens the iframe URL (the game by itself, no Flask wrapper)
  2. Runs that game's playbook function (a few actions to get visual content)
  3. Screenshots the gameplay area
  4. Saves to static/games/<slug>/thumb.png

The Flask app must be running on http://127.0.0.1:5000 before invoking.
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "static" / "games"
BASE_URL = "http://127.0.0.1:5000"


# --- per-game playbooks ---

async def play_snake(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        snake.length = 0;
        snake.push(
          {x: 4, y: 12}, {x: 5, y: 12}, {x: 6, y: 12},
          {x: 6, y: 11}, {x: 6, y: 10}, {x: 7, y: 10},
          {x: 8, y: 10}, {x: 9, y: 10}, {x: 10, y: 10},
          {x: 11, y: 10}, {x: 12, y: 10}, {x: 12, y: 9},
          {x: 12, y: 8}, {x: 13, y: 8}, {x: 14, y: 8}
        );
        food = {x: 16, y: 6};
    }""")
    await page.evaluate("alive = false; draw();")


async def play_2048(page):
    await page.evaluate("""() => {
      // wipe and inject a varied board
      for (const t of tiles) t.el.remove();
      tiles = [];
      const layout = [
        [2, 4, 8, 16],
        [4, 0, 32, 64],
        [8, 16, 128, 2],
        [0, 256, 4, 8],
      ];
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) {
        if (layout[r][c]) spawnTile(r, c, layout[r][c]);
      }
      score = 384;
      scoreEl.textContent = score;
    }""")
    await asyncio.sleep(0.25)


async def play_memory_match(page):
    # Start a 4×4 game so the grid is on screen, then flip a few cards
    await page.click("#newGame")
    await asyncio.sleep(0.2)
    cells = await page.query_selector_all(".mm-card")
    # flip 4 cards: 2 of which are matched, 2 left "facing"
    if len(cells) >= 4:
        await cells[0].click()
        await asyncio.sleep(0.05)
        # find the matching one
        await page.evaluate("""() => {
          // expose the deck so we can pick a match for card 0
          const sym = cards[0].sym;
          for (let i = 1; i < cards.length; i++) {
            if (cards[i].sym === sym) { window.__match = i; return; }
          }
        }""")
        match_idx = await page.evaluate("window.__match")
        if match_idx is not None:
            await cells[match_idx].click()
            await asyncio.sleep(0.7)
        await cells[2].click()
        await asyncio.sleep(0.05)
        # flip a third unrelated one for the snapshot
        if len(cells) > 5:
            await cells[5].click()
        await asyncio.sleep(0.3)


async def play_tic_tac_toe(page):
    # board re-renders on every move so we re-query before each click
    await page.click('button[data-mode="ai-medium"]')
    await asyncio.sleep(0.1)
    for idx in [4, 0, 8]:
        cells = await page.query_selector_all(".ttt-cell")
        if len(cells) == 9:
            await cells[idx].click()
        await asyncio.sleep(0.45)


async def play_minesweeper(page):
    await page.click('button[data-d="easy"]')
    await asyncio.sleep(0.05)
    cells = await page.query_selector_all(".ms-cell")
    if cells:
        # click middle of the board to flood-fill open numbers/blanks
        await cells[40].click()
        await asyncio.sleep(0.2)
    # flag a couple corners for visual interest
    await page.evaluate("""() => {
        const tries = [0, 8, 72, 80];
        for (const i of tries) {
            if (!cells[Math.floor(i/cols)] || !cells[Math.floor(i/cols)][i%cols]) continue;
            const cell = cells[Math.floor(i/cols)][i%cols];
            if (!cell.rev) { cell.flag = true; flagged++; }
        }
        render();
    }""")


async def play_flap(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        bird.y = H * 0.45;
        bird.vy = 0;
        pipes.length = 0;
        pipes.push({ x: 90,  top: 130, passed: false });
        pipes.push({ x: 230, top: 240, passed: false });
        pipes.push({ x: 360, top: 80,  passed: false });
        score = 5;
        scoreEl.textContent = score;
        alive = false;
    }""")
    await page.evaluate("draw();")


async def play_runner(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        runner.y = GROUND - runner.h - 30;  // mid-jump
        runner.vy = -3;
        runner.onGround = false;
        obstacles.length = 0;
        obstacles.push({ x: 220, y: GROUND - 30, w: 30, h: 30 });
        obstacles.push({ x: 360, y: GROUND - 50, w: 22, h: 50 });
        coins.length = 0;
        coins.push({ x: 280, y: GROUND - 70, r: 8 });
        coins.push({ x: 460, y: GROUND - 90, r: 8 });
        dist = 412;
        coinsCount = 7;
        distEl.textContent = Math.floor(dist);
        coinsEl.textContent = coinsCount;
        alive = false;
    }""")
    await page.evaluate("draw();")


async def play_word_guess(page):
    # Inject a partially-played puzzle without persisting.
    await page.evaluate("""() => {
        state.guesses = ["arose", "lined", "phase"];
        renderGrid();
    }""")
    await asyncio.sleep(0.1)


async def play_coal_clicker(page):
    # Click the coal lump a bunch and "buy" some upgrades by injecting state.
    await page.evaluate("""() => {
        state.coal = 12450;
        state.totalCoalEver = 88300;
        state.totalClicks = 220;
        state.upgrades = { wood: 8, iron: 3, miner: 5, cart: 2 };
        state.prestigePoints = 4;
        render();
    }""")
    await asyncio.sleep(0.3)


async def play_lockpick(page):
    # Simulate having advanced into a lock with one pin already done.
    await page.evaluate("""() => {
        saved.currentLevel = 7;
        saved.bestLevel = 12;
        saved.currentStreak = 9;
        saved.bestStreak = 12;
        newLock();
        pinIndex = 1;  // one pin already locked in
        renderPins();
        levelEl.textContent = saved.currentLevel;
        bestEl.textContent = saved.bestLevel;
        streakEl.textContent = saved.currentStreak;
    }""")
    await asyncio.sleep(0.1)


async def play_color_switch(page):
    # Use the pre-populated obstacles, just freeze before screenshot
    await page.evaluate("""() => {
        // shift so multiple obstacles are visible
        ball.y = H - 80;
        scrollY = -120;
        for (let i = 0; i < obstacles.length; i++) obstacles[i].angle = i * 0.6;
        score = 14;
        scoreEl.textContent = score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_stack_tower(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        stack.length = 0;
        const baseW = 220, x0 = (W - baseW) / 2;
        let w = baseW, x = x0;
        for (let i = 0; i < 22; i++) {
          stack.push({ x: x + (Math.sin(i*0.6) * 6), w: Math.max(40, w - i*2) });
        }
        moving = { x: 80, w: stack[stack.length-1].w, dir: 1, speed: 4 };
        cameraTargetY = Math.max(0, stack.length * BLOCK_H - H/2);
        camY = cameraTargetY;
        heightEl.textContent = stack.length - 1;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_draw_guess(page):
    # Click "New prompt" and draw a few strokes on the canvas
    await page.click('button[data-tier="easy"]')
    await asyncio.sleep(0.05)
    await page.click("#next")
    await asyncio.sleep(0.1)
    # draw a sample sun on the canvas via evaluate
    await page.evaluate("""() => {
        // sun in the corner
        ctx.strokeStyle = "#fbbf24"; ctx.lineWidth = 5; ctx.lineCap = "round";
        ctx.beginPath(); ctx.arc(150, 110, 40, 0, Math.PI * 2); ctx.stroke();
        for (let a = 0; a < 8; a++) {
          const ang = a * Math.PI / 4;
          ctx.beginPath();
          ctx.moveTo(150 + Math.cos(ang) * 50, 110 + Math.sin(ang) * 50);
          ctx.lineTo(150 + Math.cos(ang) * 70, 110 + Math.sin(ang) * 70);
          ctx.stroke();
        }
        // tree
        ctx.strokeStyle = "#65a30d"; ctx.lineWidth = 6;
        ctx.beginPath(); ctx.moveTo(420, 280); ctx.lineTo(420, 200); ctx.stroke();
        ctx.fillStyle = "#16a34a";
        ctx.beginPath(); ctx.arc(420, 170, 50, 0, Math.PI * 2); ctx.fill();
        // ground
        ctx.strokeStyle = "#a3a3a3"; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(40, 320); ctx.lineTo(560, 320); ctx.stroke();
    }""")
    await asyncio.sleep(0.1)


async def play_trivia(page):
    # Display a fake question card by writing directly to DOM
    await page.evaluate("""() => {
        document.getElementById("qmeta").textContent = "Question 3 of 10 · medium";
        document.getElementById("cattag").textContent = "Science";
        document.getElementById("q").textContent = "What is the chemical symbol for gold?";
        const ch = document.getElementById("choices");
        ch.innerHTML = "";
        for (const t of ["Au", "Ag", "Gd", "Go"]) {
          const b = document.createElement("button");
          b.className = "tr-choice";
          if (t === "Au") b.classList.add("correct");
          b.textContent = t;
          ch.appendChild(b);
        }
        document.getElementById("score").textContent = 7;
        document.getElementById("streak").textContent = 5;
        document.getElementById("bestStreak").textContent = 12;
        document.getElementById("msg").textContent = "Correct!";
    }""")
    await asyncio.sleep(0.2)


async def play_whack_a_mole(page):
    # Force a couple moles up + a gold one
    await page.evaluate("""() => {
        const ups = [1, 5, 7];
        for (const i of ups) {
            holes[i].state = "up";
            holes[i].mole.classList.add("up");
        }
        holes[5].kind = "gold"; holes[5].mole.classList.add("gold");
        score = 27;
        scoreEl.textContent = score;
    }""")
    await asyncio.sleep(0.1)


async def play_color_echo(page):
    # Light up two pads at once for a visually distinct frame
    await page.evaluate("""() => {
        document.querySelectorAll(".ce-pad").forEach((el, i) => {
            if (i === 0 || i === 2) el.classList.add("lit");
        });
        document.getElementById("round").textContent = 9;
        document.getElementById("best").textContent = 14;
        document.getElementById("center").innerHTML = "Watch<small>round 9</small>";
    }""")
    await asyncio.sleep(0.1)


async def play_typing_race(page):
    # Spawn a few falling words at varying y values
    await page.click('button[data-mode="endless"]')
    await page.click('button[data-dif="medium"]')
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        for (const w of words) w.el.remove();
        words = [];
        const samples = [
          { text: "rocket",  y: 60,  x: 80 },
          { text: "library", y: 140, x: 240 },
          { text: "harvest", y: 220, x: 130 },
          { text: "balance", y: 300, x: 380 },
        ];
        for (const s of samples) {
          const el = document.createElement("div");
          el.className = "tr-word";
          el.innerHTML = `<span class="matched"></span><span class="pending">${s.text}</span>`;
          el.style.left = s.x + "px";
          el.style.top  = s.y + "px";
          stage.appendChild(el);
          words.push({ text: s.text, x: s.x, y: s.y, vy: 0, el, typed: 0 });
        }
        score = 12;
        scoreEl.textContent = score;
        wpmEl.textContent = 48;
        accEl.textContent = "92%";
        active = false;
    }""")
    await asyncio.sleep(0.1)


async def play_gem_swap(page):
    # The board is rendered on canvas; the initial board has been resolved already.
    # Click play to refresh the board with a clean state.
    await page.click("#play")
    await asyncio.sleep(0.6)
    # by now any startup matches have cascaded; capture
    await page.evaluate("score = 320; scoreEl.textContent = score;")


async def play_bubble_shooter(page):
    # The starting state has 8 rows of bubbles. Fire one shot for visual interest.
    await page.evaluate("""() => {
        // pre-aimed shoot up-left for a visible projectile mid-flight
        shoot(120, 60);
    }""")
    await asyncio.sleep(0.15)


async def play_tower_defense(page):
    # Inject a populated battlefield: towers at varying levels + enemies en route + bullets.
    await page.evaluate("""() => {
        // Place a few towers at buildable cells
        function add(kind, c, r, lvl) {
            const t = TOWERS[kind];
            const tw = {
                kind, cellC: c, cellR: r,
                x: c * CELL + CELL/2, y: r * CELL + CELL/2,
                level: lvl, cooldown: 0,
                ...t.levels[lvl],
            };
            towers.push(tw);
            buildable[r][c] = false;
        }
        towers.length = 0;
        add("basic",  3, 6, 2);
        add("sniper", 6, 0, 1);
        add("cannon", 9, 4, 2);
        add("rapid",  12, 1, 0);
        add("slow",   8, 5, 1);
        // enemies along the path at different progress points
        function spawn(kind, idx) {
            const def = ENEMIES[kind];
            enemies.push({
              kind, ...def, maxHp: def.hp, hp: def.hp * 0.7,
              pathIdx: idx, slowUntil: 0, slowFactor: 1,
            });
        }
        enemies.length = 0;
        spawn("grunt", 60);
        spawn("grunt", 120);
        spawn("fast",  200);
        spawn("tank",  280);
        spawn("purple", 360);
        spawn("swarm", 420);
        // a couple bullets in flight
        bullets.length = 0;
        bullets.push({
            x: towers[0].x + 30, y: towers[0].y - 10,
            tx: 0, ty: 0, target: enemies[1], dmg: 12, splash: 0,
            color: TOWERS.basic.color, speed: 460, size: 4, type: "bolt",
            origin: { x: towers[0].x, y: towers[0].y }, tail: [],
        });
        bullets.push({
            x: towers[1].x, y: towers[1].y + 80,
            tx: 0, ty: 0, target: enemies[3], dmg: 50, splash: 0,
            color: TOWERS.sniper.color, speed: 1100, size: 2, type: "laser",
            origin: { x: towers[1].x, y: towers[1].y }, tail: [],
        });
        money = 240; wave = 8;
        moneyEl.textContent = money; waveEl.textContent = wave;
        kills = 27; killsEl.textContent = kills;
        livesEl.textContent = 18;
        paused = true;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_reaction_duel(page):
    await page.evaluate("""() => {
        document.getElementById("arena").className = "rd-arena go";
        document.getElementById("p1").textContent = 2;
        document.getElementById("p2").textContent = 1;
        document.getElementById("msg").textContent = "GO!";
    }""")
    await asyncio.sleep(0.1)


async def play_rock_paper_scissors(page):
    await page.evaluate("""() => {
        document.getElementById("pick1").classList.add("ready");
        document.getElementById("pick1").textContent = "🪨";
        document.getElementById("pick2").classList.add("ready");
        document.getElementById("pick2").textContent = "✂️";
        document.getElementById("status1").textContent = "ready ✓";
        document.getElementById("status2").textContent = "ready ✓";
        document.getElementById("p1").textContent = 2;
        document.getElementById("p2").textContent = 1;
    }""")
    await asyncio.sleep(0.1)


async def play_pong(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        p1y = 140; p2y = 200;
        ball = { x: W/2 + 60, y: H/2 - 30, vx: 240, vy: 180 };
        p1Score = 3; p2Score = 2;
        document.getElementById("p1").textContent = p1Score;
        document.getElementById("p2").textContent = p2Score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_connect_four(page):
    # board re-renders on every drop, so re-query each time
    seq = [3, 3, 4, 4, 2, 5, 5, 1, 6]
    for c in seq:
        cells = await page.query_selector_all(".c4-cell")
        if len(cells) >= 42:
            await cells[c].click()
        await asyncio.sleep(0.12)


async def play_sumo_smash(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        players[0].x = CX - 30; players[0].y = CY - 40; players[0].vx = 80; players[0].vy = -50;
        players[1].x = CX + 60; players[1].y = CY + 30; players[1].vx = -90; players[1].vy = 30;
        p1Score = 2; p2Score = 1;
        document.getElementById("p1").textContent = p1Score;
        document.getElementById("p2").textContent = p2Score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_tank_battle(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        tanks[0].x = 140; tanks[0].y = 200; tanks[0].angle = 0.3;
        tanks[1].x = 540; tanks[1].y = 280; tanks[1].angle = Math.PI - 0.4;
        bullets.length = 0;
        bullets.push({
            x: 220, y: 220, vx: 360, vy: 60, owner: 1, age: 0.2,
        });
        bullets.push({
            x: 460, y: 270, vx: -360, vy: -40, owner: 2, age: 0.15,
        });
        p1Score = 3; p2Score = 2;
        document.getElementById("p1").textContent = p1Score;
        document.getElementById("p2").textContent = p2Score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_checkers(page):
    # board re-renders on each move; re-query each time
    moves = [
        # P1 piece at 5,0 → 4,1
        (40, 33),
        # P2 piece at 2,1 → 3,0
        (17, 24),
        # P1 piece at 5,2 → 4,3
        (42, 35),
    ]
    for src, dst in moves:
        cells = await page.query_selector_all(".ch-cell")
        if len(cells) == 64:
            await cells[src].click()
            await asyncio.sleep(0.1)
            cells = await page.query_selector_all(".ch-cell")
            await cells[dst].click()
        await asyncio.sleep(0.2)


async def play_battleship(page):
    # Click through the "Pass to P1" intro overlay
    btn = await page.query_selector("#ovBtn")
    if btn:
        await btn.click()
        await asyncio.sleep(0.3)
    # placements re-render the board between clicks
    placements = [12, 35, 62, 71, 88]
    for idx in placements:
        grid = await page.query_selector_all(".bs-cell")
        if len(grid) >= 100:
            try:
                await grid[idx].click()
            except Exception:
                pass
        await asyncio.sleep(0.25)


async def play_tetris(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        // build a stack of colored cells that looks mid-game
        const palette = ["#22d3ee","#facc15","#a78bfa","#34d399","#f87171","#fb923c","#60a5fa"];
        function fill(r, c) { board[r][c] = palette[(r + c) % palette.length]; }
        const layout = [
          [0,0,0,0,1,1,0,0,0,0],
          [0,0,0,1,1,1,1,0,0,0],
          [0,0,1,1,0,1,1,1,0,0],
          [0,1,1,0,0,0,1,1,1,1],
          [1,1,1,1,0,1,1,1,1,1],
          [1,1,1,1,1,1,1,1,1,0],
          [1,1,1,1,1,1,1,1,1,1],
        ];
        for (let i = 0; i < layout.length; i++) for (let c = 0; c < 10; c++) {
          if (layout[i][c]) fill(ROWS - layout.length + i, c);
        }
        // a falling piece up top
        current = newPiece();
        current.kind = "T";
        current.color = "#a78bfa";
        current.blocks = [[1,0],[0,1],[1,1],[2,1]];
        current.x = 4; current.y = 2;
        score = 1240; lines = 12; level = 3;
        scoreEl.textContent = score; linesEl.textContent = lines; levelEl.textContent = level;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_pacman(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        // remove a chunk of dots in the lower half so the maze looks mid-eaten
        dots = dots.filter((d) => d.r < 10 || ((d.r + d.c) % 2 === 0));
        pac.x = 12 * TILE + 6;
        pac.y = 17 * TILE + 8;
        pac.dir = { x: 1, y: 0 };
        // position ghosts near pac
        if (ghosts[0]) { ghosts[0].x = 14 * TILE; ghosts[0].y = 17 * TILE; }
        if (ghosts[1]) { ghosts[1].x = 13 * TILE; ghosts[1].y = 14 * TILE; ghosts[1].frightened = true; }
        if (ghosts[2]) { ghosts[2].x = 17 * TILE; ghosts[2].y = 19 * TILE; }
        if (ghosts[3]) { ghosts[3].x = 10 * TILE; ghosts[3].y = 19 * TILE; }
        score = 1240;
        scoreEl.textContent = score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_asteroids(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        ship.x = W / 2; ship.y = H / 2 + 60; ship.angle = -Math.PI / 2;
        rocks.length = 0;
        rocks.push(makeRock(120, 90, 3));
        rocks.push(makeRock(480, 110, 2));
        rocks.push(makeRock(340, 180, 3));
        rocks.push(makeRock(80, 380, 2));
        rocks.push(makeRock(520, 360, 1));
        bullets.length = 0;
        bullets.push({ x: ship.x, y: ship.y - 30, vx: 0, vy: -420, life: 1 });
        bullets.push({ x: ship.x - 30, y: ship.y - 60, vx: 0, vy: -420, life: 1 });
        score = 480; wave = 3; invuln = 0;
        scoreEl.textContent = score; waveEl.textContent = wave;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_space_invaders(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        // remove some aliens to show a partially-cleared formation
        aliens = aliens.filter((a, i) => i % 3 !== 0 || a.y > 70);
        ship.x = W / 2;
        bullets.length = 0;
        bullets.push({ x: ship.x, y: ship.y - 60, vy: -480 });
        bullets.push({ x: ship.x - 80, y: ship.y - 120, vy: -480 });
        alienBullets.length = 0;
        alienBullets.push({ x: 180, y: 250, vy: 220 });
        score = 320; wave = 2;
        scoreEl.textContent = score; waveEl.textContent = wave;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_breakout(page):
    await page.click("#play")
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        // knock out some bricks from the bottom rows
        bricks = bricks.filter((b, i) => !((b.y > 110 && (i % 3 === 0)) || (b.y > 130 && i % 2 === 0)));
        paddleX = (W - PADDLE_W) / 2;
        ball = { x: paddleX + PADDLE_W / 2 - 40, y: H - 160, vx: -160, vy: -260, r: 7 };
        launched = true;
        score = 320; level = 1;
        scoreEl.textContent = score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.15)


async def play_frogger(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        frog.row = 8;  // sitting on a log lane
        frog.col = 5;
        score = 270;
        scoreEl.textContent = score;
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_blackjack(page):
    await page.click("#deal");
    await asyncio.sleep(0.4);
    # Optionally hit once for visual interest
    try:
        await page.click("#hit")
    except Exception:
        pass
    await asyncio.sleep(0.4)


async def play_plinko(page):
    await page.evaluate("""() => {
        // drop a few chips at varying positions to populate the field
        for (let i = 0; i < 6; i++) {
          balls.push({
            x: 100 + Math.random() * 300,
            y: 30 + i * 60,
            vx: (Math.random() - 0.5) * 40,
            vy: 0,
            color: `hsl(${i * 60}, 80%, 65%)`,
          });
        }
    }""")
    await asyncio.sleep(0.7)


async def play_stick_hero(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        // mid-fall stick reaching to next platform
        current = { x: 60, w: 90 };
        next = { x: 240, w: 70 };
        stick = { len: 200, angle: Math.PI / 3, falling: true };
        hero.x = current.x + current.w - 14;
        hero.y = GROUND_Y;
        phase = "falling";
        score = 8;
        scoreEl.textContent = score;
        draw();
    }""")
    await asyncio.sleep(0.05)


async def play_hangman(page):
    await page.click('button[data-dif="medium"]')
    await asyncio.sleep(0.05)
    await page.evaluate("""() => {
        // pretend the user is mid-game with some letters tried
        answer = "rocket";
        revealed = new Set(["r","o","e"]);
        tried = new Set(["r","o","e","a","s","z"]);
        misses = 3;
        render();
    }""")
    await asyncio.sleep(0.1)


async def play_word_search(page):
    await page.click("#newGame")
    await asyncio.sleep(0.3)
    # mark a couple words found by simulating drag-find via state injection
    await page.evaluate("""() => {
        // mark the first two placed words as found and color the grid cells
        const founds = words.slice(0, 2);
        for (const w of founds) {
          foundWords.add(w);
          // find the word in the grid (any direction) and color cells
          outer: for (let r = 0; r < SIZE; r++) for (let c = 0; c < SIZE; c++) {
            for (const [dr, dc] of DIRS) {
              let ok = true;
              const cells = [];
              for (let i = 0; i < w.length; i++) {
                const nr = r + dr * i, nc = c + dc * i;
                if (nr < 0 || nr >= SIZE || nc < 0 || nc >= SIZE) { ok = false; break; }
                if (grid[nr][nc] !== w[i]) { ok = false; break; }
                cells.push([nr, nc]);
              }
              if (ok) {
                for (const [nr, nc] of cells) cellEl(nr, nc).classList.add("found");
                break outer;
              }
            }
          }
        }
        foundEl.textContent = foundWords.size;
        renderWords();
    }""")
    await asyncio.sleep(0.15)


async def play_asteroid_runner(page):
    await page.click("#play")
    await asyncio.sleep(0.1)
    await page.evaluate("""() => {
        rocks.length = 0;
        rocks.push({ x: 500, y: 120, vx: -200, vy: 10, r: 38, spin: 0.5, rot: 0.4, hp: 2 });
        rocks.push({ x: 620, y: 260, vx: -200, vy: -20, r: 28, spin: -0.3, rot: 1.1, hp: 1 });
        rocks.push({ x: 320, y: 360, vx: -200, vy: 30, r: 22, spin: 0.6, rot: 2.0, hp: 1 });
        rocks.push({ x: 720, y: 80,  vx: -200, vy: 40, r: 32, spin: 0.1, rot: 0.0, hp: 1 });
        bullets.length = 0;
        bullets.push({ x: 220, y: 230, vx: 800, life: 1 });
        bullets.push({ x: 320, y: 230, vx: 800, life: 1 });
        ship.x = 140; ship.y = 230;
        dist = 312; shotCount = 18; scrollSpeed = 360;
        distEl.textContent = Math.floor(dist);
        shotEl.textContent = shotCount;
        speedEl.textContent = "1.6x";
        alive = false;
        draw();
    }""")
    await asyncio.sleep(0.1)


async def play_higher_lower(page):
    # Reveal left as a face card, leave the right card face-down
    await page.evaluate("""() => {
        current = { rank: '10', suit: '♥' };
        renderCard(leftEl, current, false);
        streak = 4;
        streakEl.textContent = streak;
        statusEl.textContent = 'Higher or lower?';
    }""")
    await asyncio.sleep(0.1)


async def play_mastermind(page):
    await page.evaluate("""() => {
        // populate a few guesses with feedback for a mid-game look
        guesses = [
            { colors: [0, 1, 2, 3], feedback: { hits: 1, near: 1 } },
            { colors: [2, 0, 4, 1], feedback: { hits: 2, near: 0 } },
            { colors: [2, 4, 1, 5], feedback: { hits: 1, near: 2 } },
        ];
        current[0] = 4; current[1] = 0; current[2] = 1; current[3] = null;
        selectedColor = 5;
        renderPalette();
        renderBoard();
        updateHud();
    }""")
    await asyncio.sleep(0.1)


async def play_roulette(page):
    # Place a few chips on different bet types so the felt looks alive.
    for key in ["red", "doz:2", "n:17", "n:23"]:
        el = await page.query_selector(f'[data-key="{key}"]')
        if el:
            await el.click()
            await asyncio.sleep(0.05)
    # set a slight wheel rotation for visual interest
    await page.evaluate("wheelAngle = 0.7; drawWheel();")
    await asyncio.sleep(0.2)


async def play_slot_machine(page):
    # Set the reels to a near-jackpot triple by stuffing the strips directly
    await page.evaluate("""() => {
        const syms = ["7", "7", "🔔"];
        for (let i = 0; i < 3; i++) {
            const el = document.getElementById("r" + i);
            const showSym = syms[i];
            el.innerHTML = `
                <div class="sm-sym">${symbolHtml('🍒')}</div>
                <div class="sm-sym">${symbolHtml(showSym)}</div>
                <div class="sm-sym">${symbolHtml('🍋')}</div>`;
            el.style.transform = "translateY(0)";
        }
        bigWinEl.textContent = "Spin to win!";
    }""")
    await asyncio.sleep(0.1)


# Map slug -> (selector_to_screenshot, action_fn)
PLAYBOOKS = {
    "snake":               { "selector": "#cv",            "action": play_snake },
    "twenty-forty-eight":  { "selector": "#board",         "action": play_2048 },
    "memory-match":        { "selector": "#grid",          "action": play_memory_match },
    "tic-tac-toe":         { "selector": "#board",         "action": play_tic_tac_toe },
    "minesweeper":         { "selector": "#board",         "action": play_minesweeper },
    "flap":                { "selector": "#cv",            "action": play_flap },
    "word-guess":          { "selector": "#grid",          "action": play_word_guess },
    "coal-clicker":        { "selector": ".cc-layout",     "action": play_coal_clicker },
    "lockpick":            { "selector": "#cv",            "action": play_lockpick },
    "color-switch":        { "selector": "#cv",            "action": play_color_switch },
    "stack-tower":         { "selector": "#cv",            "action": play_stack_tower },
    "draw-guess":          { "selector": "#dr",            "action": play_draw_guess },
    "trivia":              { "selector": ".tr-card",       "action": play_trivia },
    "whack-a-mole":        { "selector": "#grid",          "action": play_whack_a_mole },
    "color-echo":          { "selector": ".ce-board",      "action": play_color_echo },
    "typing-race":         { "selector": ".tr-stage",      "action": play_typing_race },
    "gem-swap":            { "selector": "#cv",            "action": play_gem_swap },
    "bubble-shooter":      { "selector": "#cv",            "action": play_bubble_shooter },
    "tower-defense":       { "selector": "#cv",            "action": play_tower_defense },
    "reaction-duel":       { "selector": "#arena",         "action": play_reaction_duel },
    "rock-paper-scissors": { "selector": ".rps-stage",     "action": play_rock_paper_scissors },
    "pong":                { "selector": "#cv",            "action": play_pong },
    "connect-four":        { "selector": "#board",         "action": play_connect_four },
    "sumo-smash":          { "selector": "#cv",            "action": play_sumo_smash },
    "tank-battle":         { "selector": "#cv",            "action": play_tank_battle },
    "checkers":            { "selector": "#board",         "action": play_checkers },
    "battleship":          { "selector": ".bs-wrap",       "action": play_battleship },
    # newer additions
    "tetris":              { "selector": "#cv",            "action": play_tetris },
    "pacman":              { "selector": "#cv",            "action": play_pacman },
    "asteroids":           { "selector": "#cv",            "action": play_asteroids },
    "space-invaders":      { "selector": "#cv",            "action": play_space_invaders },
    "breakout":            { "selector": "#cv",            "action": play_breakout },
    "frogger":             { "selector": "#cv",            "action": play_frogger },
    "blackjack":           { "selector": ".bj-table",      "action": play_blackjack },
    "plinko":              { "selector": "#cv",            "action": play_plinko },
    "stick-hero":          { "selector": "#cv",            "action": play_stick_hero },
    "hangman":             { "selector": ".hm-stage",      "action": play_hangman },
    "word-search":         { "selector": ".ws-stage",      "action": play_word_search },
    "roulette":            { "selector": ".rt-table",      "action": play_roulette },
    "slot-machine":        { "selector": ".sm-cabinet",    "action": play_slot_machine },
    "asteroid-runner":     { "selector": "#cv",            "action": play_asteroid_runner },
    "higher-lower":        { "selector": ".hl-table",      "action": play_higher_lower },
    "mastermind":          { "selector": ".mm-stage",      "action": play_mastermind },
    # chrome-dino is an external embed, no playbook
}


async def make_thumbnail(slug, browser):
    if slug not in PLAYBOOKS:
        print(f"[{slug}] no playbook defined", file=sys.stderr)
        return False
    out_path = GAMES_DIR / slug / "thumb.png"
    pb = PLAYBOOKS[slug]
    url = f"{BASE_URL}/static/games/{slug}/index.html"

    ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="load")
        await asyncio.sleep(0.4)
        try:
            await pb["action"](page)
        except Exception as e:
            print(f"[{slug}] action error: {e}", file=sys.stderr)
        await asyncio.sleep(0.2)
        elt = await page.query_selector(pb["selector"])
        if not elt:
            print(f"[{slug}] selector {pb['selector']!r} not found", file=sys.stderr)
            return False
        await elt.screenshot(path=str(out_path))
        print(f"[{slug}] wrote {out_path.relative_to(ROOT)}")
        return True
    finally:
        await ctx.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="Game slug(s) to thumbnail")
    ap.add_argument("--all", action="store_true", help="Run every defined playbook")
    args = ap.parse_args()
    targets = list(PLAYBOOKS) if args.all else args.slugs
    if not targets:
        ap.error("Pass a slug or --all")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for slug in targets:
            await make_thumbnail(slug, browser)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
