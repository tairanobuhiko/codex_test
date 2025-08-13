import math
import os
import random
import struct
import sys
import time
import wave

import pygame


# ---------------------------
# Config
# ---------------------------
WIDTH, HEIGHT = 960, 720
FPS = 60
TITLE = "Neon Space Invaders"

# Visual toggles
GLOW_LAYERING = True
STARFIELD_LAYERS = 3
PARTICLE_COUNT = 120
SCREEN_SHAKE = True

# Paths
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")


# ---------------------------
# Utils
# ---------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def ensure_dirs():
    os.makedirs(SOUNDS_DIR, exist_ok=True)


def write_wav(path, frames, sample_rate=44100):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # Convert float [-1,1] to 16-bit signed
        data = b"".join(struct.pack('<h', int(clamp(x, -1.0, 1.0) * 32767)) for x in frames)
        wf.writeframes(data)


def synth_tone(freq=880.0, dur=0.15, vol=0.5, wave_type="sine", sample_rate=44100, decay=0.002):
    n = int(dur * sample_rate)
    frames = []
    for i in range(n):
        t = i / sample_rate
        env = math.exp(-decay * i)  # simple decay envelope
        if wave_type == "sine":
            s = math.sin(2 * math.pi * freq * t)
        elif wave_type == "square":
            s = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
        elif wave_type == "triangle":
            s = 2.0 * abs(2.0 * ((t * freq) % 1.0) - 1.0) - 1.0
        else:
            s = 0.0
        frames.append(vol * env * s)
    return frames


def synth_noise(dur=0.35, vol=0.45, sample_rate=44100):
    n = int(dur * sample_rate)
    frames = []
    for i in range(n):
        env = math.exp(-0.008 * i)  # faster decay for explosion
        s = (random.random() * 2.0 - 1.0)
        frames.append(vol * env * s)
    return frames


def generate_sounds():
    ensure_dirs()
    files = {
        "laser.wav": synth_tone(freq=1200, dur=0.09, vol=0.55, wave_type="square", decay=0.008),
        "powerup.wav": synth_tone(freq=600, dur=0.12, vol=0.5, wave_type="triangle", decay=0.006)
        + synth_tone(freq=900, dur=0.12, vol=0.4, wave_type="triangle", decay=0.006),
        "explosion.wav": synth_noise(dur=0.4, vol=0.6),
        "hit.wav": synth_tone(freq=320, dur=0.06, vol=0.45, wave_type="sine", decay=0.02),
    }
    for name, frames in files.items():
        path = os.path.join(SOUNDS_DIR, name)
        if not os.path.exists(path):
            write_wav(path, frames)


def load_sounds():
    sounds = {}
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        for n in ["laser", "powerup", "explosion", "hit"]:
            path = os.path.join(SOUNDS_DIR, f"{n}.wav")
            if os.path.exists(path):
                sounds[n] = pygame.mixer.Sound(path)
    except Exception:
        sounds = {}
    return sounds


# ---------------------------
# Visual helpers
# ---------------------------
def neon_circle(radius, color, glow=3):
    size = radius * 2 + glow * 6
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    r = radius
    # Glow layers
    if GLOW_LAYERING:
        for i in range(glow, 0, -1):
            alpha = int(18 * i)
            pygame.draw.circle(surf, (*color, alpha), (cx, cy), r + i * 3)
    # Core
    pygame.draw.circle(surf, (*color, 255), (cx, cy), r)
    return surf


def neon_rect(size, color, glow=3, border_radius=8):
    w, h = size
    pad = glow * 4
    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    rect = pygame.Rect(pad, pad, w, h)
    if GLOW_LAYERING:
        for i in range(glow, 0, -1):
            alpha = int(16 * i)
            pygame.draw.rect(surf, (*color, alpha), rect.inflate(i * 6, i * 6), border_radius=border_radius)
    pygame.draw.rect(surf, (*color, 255), rect, border_radius=border_radius)
    return surf


def additive_blit(dst, src, pos):
    dst.blit(src, pos, special_flags=pygame.BLEND_ADD)


# ---------------------------
# Entities
# ---------------------------
NEON_CYAN = (0, 255, 220)
NEON_MAGENTA = (255, 60, 200)
NEON_YELLOW = (255, 240, 0)
NEON_LIME = (120, 255, 60)
NEON_ORANGE = (255, 135, 50)
NEON_BLUE = (70, 160, 255)
NEON_RED = (255, 60, 60)
UI_WHITE = (230, 235, 245)


class StarField:
    def __init__(self, w, h, layers=3):
        self.w, self.h = w, h
        self.layers = []
        for i in range(layers):
            count = 80 * (i + 1)
            speed = 20 * (i + 1)
            color = (80 + 40 * i, 120 + 45 * i, 200 + 20 * i)
            stars = []
            for _ in range(count):
                x = random.random() * w
                y = random.random() * h
                size = 1 + i
                stars.append([x, y, size])
            self.layers.append({"stars": stars, "speed": speed, "color": color})

    def update(self, dt):
        for layer in self.layers:
            for s in layer["stars"]:
                s[1] += layer["speed"] * dt
                if s[1] > self.h:
                    s[0] = random.random() * self.w
                    s[1] = -5

    def draw(self, surf):
        for layer in self.layers:
            color = layer["color"]
            for x, y, size in layer["stars"]:
                pygame.draw.rect(surf, color, (int(x), int(y), size, size))


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-220, 220)
        self.vy = random.uniform(-240, 60)
        self.life = random.uniform(0.4, 0.9)
        self.age = 0.0
        self.color = color
        self.radius = random.randint(1, 3)

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 420 * dt  # gravity-like

    def alive(self):
        return self.age < self.life

    def draw(self, surf):
        t = clamp(1 - self.age / self.life, 0, 1)
        alpha = int(220 * t)
        if alpha <= 0:
            return
        pygame.draw.circle(surf, (*self.color, alpha), (int(self.x), int(self.y)), self.radius)


class Bullet:
    def __init__(self, x, y, color=NEON_YELLOW):
        self.x = x
        self.y = y
        self.speed = -680
        self.alive = True
        self.sprite = neon_rect((4, 18), color, glow=2)

    def update(self, dt):
        self.y += self.speed * dt
        if self.y < -40:
            self.alive = False

    def rect(self):
        w, h = self.sprite.get_size()
        return pygame.Rect(int(self.x - w // 2), int(self.y - h // 2), w, h)

    def draw(self, surf):
        additive_blit(surf, self.sprite, (self.rect().x, self.rect().y))


class Enemy:
    def __init__(self, x, y, kind=0):
        self.x = x
        self.y = y
        self.base_y = y
        self.kind = kind
        self.alive = True
        self.timer = random.random() * 100
        colors = [NEON_MAGENTA, NEON_CYAN, NEON_LIME, NEON_ORANGE]
        self.color = colors[kind % len(colors)]
        size = 22 + kind * 4
        self.sprite = neon_rect((size, size), self.color, glow=3, border_radius=6)
        self.wobble = 8 + kind * 2
        self.speed = 40 + kind * 10

    def update(self, dt, t):
        self.timer += dt
        self.y = self.base_y + math.sin(t * 2 + self.x * 0.01) * self.wobble
        self.x += math.sin(t * 0.7 + self.timer * 0.6) * 20 * dt

    def rect(self):
        w, h = self.sprite.get_size()
        return pygame.Rect(int(self.x - w // 2), int(self.y - h // 2), w, h)

    def draw(self, surf):
        additive_blit(surf, self.sprite, (self.rect().x, self.rect().y))


class PowerUp:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vy = 120
        self.alive = True
        self.sprite = neon_circle(10, NEON_BLUE, glow=3)

    def update(self, dt):
        self.y += self.vy * dt
        if self.y > HEIGHT + 20:
            self.alive = False

    def rect(self):
        w, h = self.sprite.get_size()
        return pygame.Rect(int(self.x - w // 2), int(self.y - h // 2), w, h)

    def draw(self, surf):
        additive_blit(surf, self.sprite, (self.rect().x, self.rect().y))


class Player:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT - 80
        self.speed = 420
        self.cd = 0.0
        self.multi = 1
        self.sprite = neon_rect((36, 22), NEON_CYAN, glow=3, border_radius=10)
        self.tail_timer = 0.0

    def update(self, dt, keys):
        ax = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            ax -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            ax += 1
        self.x += ax * self.speed * dt
        self.x = clamp(self.x, 40, WIDTH - 40)
        self.cd = max(0.0, self.cd - dt)
        self.tail_timer += dt

    def shoot(self, bullets, sounds):
        if self.cd > 0:
            return
        spread = 12
        for i in range(self.multi):
            offset = (i - (self.multi - 1) / 2) * spread
            bullets.append(Bullet(self.x + offset, self.y - 20))
        self.cd = 0.18 if self.multi == 1 else 0.24
        s = sounds.get("laser")
        if s:
            s.set_volume(0.4)
            s.play()

    def rect(self):
        w, h = self.sprite.get_size()
        return pygame.Rect(int(self.x - w // 2), int(self.y - h // 2), w, h)

    def draw(self, surf):
        additive_blit(surf, self.sprite, (self.rect().x, self.rect().y))
        # engine trail
        if self.tail_timer > 0.03:
            self.tail_timer = 0
            for i in range(2):
                px = self.x + random.uniform(-7, 7)
                py = self.y + random.uniform(8, 14)
                pygame.draw.circle(surf, (80, 200, 255, 140), (int(px), int(py)), random.randint(2, 3))


# ---------------------------
# Game
# ---------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24)
        self.big_font = pygame.font.SysFont("Arial", 64, bold=True)

        generate_sounds()
        self.sounds = load_sounds()

        self.reset()

    def reset(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.powerups = []
        self.particles = []
        self.starfield = StarField(WIDTH, HEIGHT, layers=STARFIELD_LAYERS)
        self.spawn_wave(1)
        self.wave = 1
        self.score = 0
        self.lives = 3
        self.time = 0
        self.shake = 0
        self.game_over = False

    def spawn_wave(self, wave):
        cols = 9
        rows = 4 + min(3, wave)
        spacing_x = WIDTH // (cols + 1)
        spacing_y = 64
        offset_y = 80
        for r in range(rows):
            for c in range(cols):
                x = spacing_x * (c + 1)
                y = offset_y + r * spacing_y
                self.enemies.append(Enemy(x, y, kind=(r % 4)))

    def update(self, dt):
        if self.game_over:
            return
        self.time += dt
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)
        if keys[pygame.K_SPACE]:
            self.player.shoot(self.bullets, self.sounds)

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

        for e in self.enemies:
            e.update(dt, self.time)
        # Enemies downward drift over time
        for e in self.enemies:
            e.base_y += 4 * dt
            if e.base_y > HEIGHT - 140:
                self.game_over = True

        # Collisions bullets -> enemies
        for b in list(self.bullets):
            br = b.rect()
            for e in list(self.enemies):
                if br.colliderect(e.rect()):
                    self.score += 10
                    b.alive = False
                    e.alive = False
                    self.explode(e.x, e.y, e.color)
                    if random.random() < 0.07:
                        self.powerups.append(PowerUp(e.x, e.y))
                    s = self.sounds.get("hit") or self.sounds.get("explosion")
                    if s:
                        s.set_volume(0.5)
                        s.play()
                    if SCREEN_SHAKE:
                        self.shake = 8
        self.enemies = [e for e in self.enemies if e.alive]

        # Power-ups
        for p in self.powerups:
            p.update(dt)
            if p.rect().colliderect(self.player.rect()):
                self.player.multi = min(5, self.player.multi + 1)
                p.alive = False
                s = self.sounds.get("powerup")
                if s:
                    s.set_volume(0.45)
                    s.play()
        self.powerups = [p for p in self.powerups if p.alive]

        # Particles
        for pa in self.particles:
            pa.update(dt)
        self.particles = [pa for pa in self.particles if pa.alive()]

        # Starfield
        self.starfield.update(dt)

        # Wave cleared
        if not self.enemies:
            self.wave += 1
            self.spawn_wave(self.wave)

        # Shake decay
        self.shake = max(0, self.shake - 60 * dt)

    def explode(self, x, y, color):
        for _ in range(PARTICLE_COUNT // 6):
            self.particles.append(Particle(x, y, color))
        ex = self.sounds.get("explosion")
        if ex:
            ex.set_volume(0.6)
            ex.play()

    def draw_hud(self, surf):
        # Score
        score_s = self.font.render(f"Score {self.score}", True, UI_WHITE)
        surf.blit(score_s, (16, 12))
        # Wave
        wave_s = self.font.render(f"Wave {self.wave}", True, UI_WHITE)
        surf.blit(wave_s, (WIDTH - 140, 12))
        # Lives (visualized as small neon ships)
        for i in range(self.lives):
            ship = neon_rect((20, 12), NEON_CYAN, glow=2, border_radius=6)
            additive_blit(surf, ship, (16 + i * 26, 44))

    def draw_title(self, surf):
        title = self.big_font.render("NEON INVADERS", True, UI_WHITE)
        tw, th = title.get_size()
        # glow behind
        glow = neon_rect((tw + 40, th + 20), NEON_MAGENTA, glow=2, border_radius=12)
        additive_blit(surf, glow, (WIDTH // 2 - (tw + 40)//2, HEIGHT // 2 - 160))
        surf.blit(title, (WIDTH // 2 - tw // 2, HEIGHT // 2 - 150))

        info = self.font.render("Arrows/WASD to move, Space to shoot", True, UI_WHITE)
        surf.blit(info, (WIDTH // 2 - info.get_width() // 2, HEIGHT // 2 - 60))
        info2 = self.font.render("Collect blue orbs for multishot", True, UI_WHITE)
        surf.blit(info2, (WIDTH // 2 - info2.get_width() // 2, HEIGHT // 2 - 32))

    def render(self):
        # background
        self.screen.fill((6, 10, 18))
        self.starfield.draw(self.screen)

        base_offset = (0, 0)
        if self.shake > 0 and SCREEN_SHAKE:
            base_offset = (random.randint(-int(self.shake), int(self.shake)), random.randint(-int(self.shake), int(self.shake)))

        # world surface for additive blits
        world = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # entities
        for p in self.particles:
            p.draw(world)
        for b in self.bullets:
            b.draw(world)
        for e in self.enemies:
            e.draw(world)
        for p in self.powerups:
            p.draw(world)
        self.player.draw(world)

        # Additive composite
        self.screen.blit(world, base_offset, special_flags=pygame.BLEND_ADD)

        self.draw_hud(self.screen)

        if self.game_over:
            over = self.big_font.render("GAME OVER", True, UI_WHITE)
            self.screen.blit(over, (WIDTH // 2 - over.get_width() // 2, HEIGHT // 2 - 40))
            tip = self.font.render("Press R to restart, Esc to quit", True, UI_WHITE)
            self.screen.blit(tip, (WIDTH // 2 - tip.get_width() // 2, HEIGHT // 2 + 30))

    def run(self):
        show_title = True
        title_time = 2.0
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit(0)
                    if event.key == pygame.K_r and self.game_over:
                        self.reset()
                    if event.key == pygame.K_SPACE and show_title:
                        show_title = False

            if show_title:
                self.starfield.update(dt)
                self.screen.fill((6, 10, 18))
                self.starfield.draw(self.screen)
                self.draw_title(self.screen)
                pygame.display.flip()
                continue

            self.update(dt)
            self.render()
            pygame.display.flip()


if __name__ == "__main__":
    try:
        Game().run()
    except Exception as e:
        print("Error:", e)
        pygame.quit()
        raise

