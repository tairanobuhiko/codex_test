# Neon Space Invaders (Pygame)

A fancy, modern take on Space Invaders with neon glow visuals, particle effects, starfield parallax, and synthesized sounds generated on first run.

## Features
- Neon additive glow rendering (no external textures required)
- Parallax starfield background and screen shake
- Particle explosions and engine trail
- Power-ups for multishot
- Procedurally generated WAV sound effects (laser, hit, explosion, powerup)

## Run
1. Ensure Python 3.9+ is installed.
2. Install Pygame:
   - `pip install -r requirements.txt` (or `pip install pygame`)
3. Launch the game:
   - `python space_invaders_neon.py`

## Controls
- Move: Arrow keys or WASD
- Shoot: Space
- Restart after Game Over: R
- Quit: Esc

## Notes
- On first run, sound assets are generated under `assets/sounds/`.
- If audio initialization fails, the game runs without sound.
- Toggle performance/visual options at the top of `space_invaders_neon.py`.

Enjoy blasting invaders in neon!
