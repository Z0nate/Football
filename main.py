import pygame
import math
import sys
import random
import socket
import json
import time
import base64
import hashlib
from collections import deque

# ── Init ──────────────────────────────────────────────────────────
pygame.init()

# ── Constants ─────────────────────────────────────────────────────
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 750
FIELD_MARGIN = 55
FIELD_WIDTH = SCREEN_WIDTH - 2 * FIELD_MARGIN
FIELD_HEIGHT = SCREEN_HEIGHT - 2 * FIELD_MARGIN
FIELD_TOP = FIELD_MARGIN
FIELD_LEFT = FIELD_MARGIN
FIELD_RIGHT = SCREEN_WIDTH - FIELD_MARGIN
FIELD_BOTTOM = SCREEN_HEIGHT - FIELD_MARGIN

GOAL_WIDTH = 30
GOAL_HEIGHT = 180
GOAL_TOP = (SCREEN_HEIGHT - GOAL_HEIGHT) // 2
GOAL_BOTTOM = GOAL_TOP + GOAL_HEIGHT

PLAYER_RADIUS = 28
BALL_RADIUS = 18
PLAYER_ACCEL = 0.65
PLAYER_FRICTION = 0.88
PLAYER_MAX_SPEED = 4.2
BALL_FRICTION = 0.985
KICK_POWER = 15
KICK_RANGE = PLAYER_RADIUS + BALL_RADIUS + 12
MAX_BALL_SPEED = 22

PORT = 5555
DISCONNECT_TIMEOUT = 5.0

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRASS_DARK = (34, 85, 51)
GRASS_LIGHT = (42, 100, 60)
GRAY = (30, 30, 30)
DARK_GRAY = (18, 18, 18)
LIGHT_GRAY = (120, 120, 120)
TEAM1_COLOR = (0, 220, 255)
TEAM1_GLOW = (0, 180, 220)
TEAM2_COLOR = (255, 60, 80)
TEAM2_GLOW = (220, 40, 60)
GOLD = (255, 215, 0)
MENU_BG = (15, 15, 25)
MENU_ACCENT = (255, 100, 50)
MENU_TEXT = (220, 220, 230)
MENU_DIM = (100, 100, 110)

# Screen
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Football Online")
clock = pygame.time.Clock()

# Fonts
font = pygame.font.SysFont("consolas", 40, bold=True)
font_large = pygame.font.SysFont("consolas", 72, bold=True)
font_small = pygame.font.SysFont("consolas", 20)
font_replay = pygame.font.SysFont("consolas", 52, bold=True)
font_goal = pygame.font.SysFont("impact", 90, bold=True)
font_title = pygame.font.SysFont("impact", 96, bold=True)
font_menu = pygame.font.SysFont("consolas", 32, bold=True)
font_tiny = pygame.font.SysFont("consolas", 16)

# ── Room ID System ────────────────────────────────────────────────
ROOM_SALT = "football_2026_salt"

def ip_to_room_id(ip):
    """Obfuscate IP into a short room ID."""
    combined = f"{ip}:{ROOM_SALT}"
    hashed = hashlib.sha256(combined.encode()).digest()
    encoded = base64.urlsafe_b64encode(hashed[:6]).decode()
    return encoded[:8].upper()

def room_id_to_ip(room_id):
    """Brute-force decode: try all local IPs. Client must enter actual IP or we use a discovery broadcast."""
    # In practice, the host tells the room ID verbally; the client enters it.
    # For LAN, we can broadcast to find the host.
    return None  # Not directly reversible; use broadcast discovery instead

# ── Screen Shake ──────────────────────────────────────────────────
class ScreenShake:
    def __init__(self):
        self.shake = 0
        self.shake_decay = 0.9

    def add(self, intensity):
        self.shake = max(self.shake, intensity)

    def update(self):
        self.shake *= self.shake_decay
        if self.shake < 0.5:
            self.shake = 0

    def get_offset(self):
        if self.shake <= 0:
            return (0, 0)
        return (random.randint(-int(self.shake), int(self.shake)),
                random.randint(-int(self.shake), int(self.shake)))

shaker = ScreenShake()

# ── Touch controls ─────────────────────────────────────────────
class MobileControls:
    def __init__(self):
        self.joystick_base = (120, SCREEN_HEIGHT - 120)
        self.joystick_radius = 72
        self.active_joystick = False
        self.joystick_id = None
        self.joy_x = 0.0
        self.joy_y = 0.0
        self.kick_pressed = False
        self.kick_down = False
        self.kick_id = None

    def reset(self):
        self.active_joystick = False
        self.joystick_id = None
        self.joy_x = 0.0
        self.joy_y = 0.0
        self.kick_pressed = False
        self.kick_down = False
        self.kick_id = None

    def handle_event(self, event):
        if event.type == pygame.FINGERDOWN:
            x = event.x * SCREEN_WIDTH
            y = event.y * SCREEN_HEIGHT
            if not self.active_joystick and x < SCREEN_WIDTH * 0.5 and y > SCREEN_HEIGHT * 0.55:
                dx = x - self.joystick_base[0]
                dy = y - self.joystick_base[1]
                if math.hypot(dx, dy) <= self.joystick_radius + 24:
                    self.active_joystick = True
                    self.joystick_id = event.finger_id
                    self.joy_x = max(-1.0, min(1.0, dx / self.joystick_radius))
                    self.joy_y = max(-1.0, min(1.0, dy / self.joystick_radius))
            if x > SCREEN_WIDTH * 0.72 and y > SCREEN_HEIGHT * 0.62:
                self.kick_pressed = True
                self.kick_down = True
                self.kick_id = event.finger_id
        elif event.type == pygame.FINGERMOTION:
            if self.active_joystick and event.finger_id == self.joystick_id:
                x = event.x * SCREEN_WIDTH
                y = event.y * SCREEN_HEIGHT
                dx = x - self.joystick_base[0]
                dy = y - self.joystick_base[1]
                dist = min(math.hypot(dx, dy), self.joystick_radius)
                if dist > 0:
                    self.joy_x = dx / dist
                    self.joy_y = dy / dist
                else:
                    self.joy_x = 0.0
                    self.joy_y = 0.0
        elif event.type == pygame.FINGERUP:
            if self.active_joystick and event.finger_id == self.joystick_id:
                self.active_joystick = False
                self.joystick_id = None
                self.joy_x = 0.0
                self.joy_y = 0.0
            if self.kick_down and event.finger_id == self.kick_id:
                self.kick_down = False
                self.kick_id = None

    def get_move_state(self):
        return {
            'up': self.joy_y < -0.2,
            'down': self.joy_y > 0.2,
            'left': self.joy_x < -0.2,
            'right': self.joy_x > 0.2,
        }

    def consume_kick(self):
        pressed = self.kick_pressed
        self.kick_pressed = False
        return pressed

    def draw(self, surface):
        joystick_base = self.joystick_base
        pygame.draw.circle(surface, (255, 255, 255, 70), joystick_base, self.joystick_radius)
        pygame.draw.circle(surface, (255, 255, 255, 120), joystick_base, self.joystick_radius - 10)
        thumb_x = joystick_base[0] + self.joy_x * (self.joystick_radius - 18)
        thumb_y = joystick_base[1] + self.joy_y * (self.joystick_radius - 18)
        pygame.draw.circle(surface, (255, 255, 255, 180), (int(thumb_x), int(thumb_y)), 24)
        pygame.draw.circle(surface, (0, 0, 0, 120), (int(thumb_x), int(thumb_y)), 24, 2)

        kick_x, kick_y = SCREEN_WIDTH - 110, SCREEN_HEIGHT - 120
        pygame.draw.circle(surface, (255, 90, 60, 180), (kick_x, kick_y), 48)
        pygame.draw.circle(surface, (255, 255, 255, 140), (kick_x, kick_y), 48, 2)
        kick_text = font_small.render('KICK', True, WHITE)
        surface.blit(kick_text, (kick_x - kick_text.get_width() // 2, kick_y - kick_text.get_height() // 2))


touch_controls = MobileControls()


class Particle:
    def __init__(self, x, y, color, speed, life, size):
        angle = random.uniform(0, math.pi * 2)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= 1
        self.size = max(0, self.size - 0.15)

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = int(255 * (self.life / self.max_life))
        s = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
        surface.blit(s, (int(self.x - self.size), int(self.y - self.size)))

particles = []

def serialize_particles(particle_list):
    return [[p.x, p.y, p.color[0], p.color[1], p.color[2], p.size, p.life / p.max_life]
            for p in particle_list]

def spawn_particles(x, y, color, count=15, speed=5, life=30, size=6):
    for _ in range(count):
        particles.append(Particle(x, y, color, random.uniform(2, speed), life, random.uniform(2, size)))

def spawn_kick_ripple(x, y, color):
    for _ in range(8):
        particles.append(Particle(x, y, color, random.uniform(1, 3), 20, random.uniform(4, 8)))

# ── Trails ───────────────────────────────────────────────────────
class Trail:
    def __init__(self, max_len=12):
        self.points = deque(maxlen=max_len)

    def add(self, x, y):
        self.points.append((x, y, 255))

    def update(self):
        new_pts = []
        for x, y, a in self.points:
            a -= 22
            if a > 0:
                new_pts.append((x, y, a))
        self.points = deque(new_pts, maxlen=self.points.maxlen)

    def draw(self, surface, radius, color):
        for (x, y, a) in self.points:
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, a), (radius, radius), radius)
            surface.blit(s, (int(x - radius), int(y - radius)))

# ── Replay Buffer ─────────────────────────────────────────────────
class ReplayBuffer:
    def __init__(self, max_frames=180):
        self.frames = deque(maxlen=max_frames)

    def record(self, ball, players, particles):
        frame = {
            'ball': [ball.x, ball.y, ball.vx, ball.vy],
            'players': [[p.x, p.y, p.vx, p.vy, p.team, p.label, p.nickname] for p in players],
            'particles': serialize_particles(particles),
            'shake': list(shaker.get_offset())
        }
        self.frames.append(frame)

    def get_frames(self):
        return list(self.frames)

    def clear(self):
        self.frames.clear()

# ── Player Collision ──────────────────────────────────────────────
def resolve_player_collisions(players):
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            p1 = players[i]
            p2 = players[j]
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            dist = math.hypot(dx, dy)
            min_dist = PLAYER_RADIUS * 2
            if dist < min_dist and dist > 0:
                overlap = (min_dist - dist) / 2
                nx = dx / dist
                ny = dy / dist
                p1.x += nx * overlap
                p1.y += ny * overlap
                p2.x -= nx * overlap
                p2.y -= ny * overlap

# ── Player ────────────────────────────────────────────────────────
class Player:
    def __init__(self, x, y, controls, kick_key, label, team, nickname="Player"):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.controls = controls
        self.kick_key = kick_key
        self.label = label
        self.team = team
        self.nickname = nickname
        self.trail = Trail(max_len=10)
        self.prev_kick = False

    def update(self, input_state=None):
        ax = 0.0
        ay = 0.0
        if input_state:
            if input_state.get('up', False):
                ay -= PLAYER_ACCEL
            if input_state.get('down', False):
                ay += PLAYER_ACCEL
            if input_state.get('left', False):
                ax -= PLAYER_ACCEL
            if input_state.get('right', False):
                ax += PLAYER_ACCEL

        self.vx += ax
        self.vy += ay
        self.vx *= PLAYER_FRICTION
        self.vy *= PLAYER_FRICTION

        speed = math.hypot(self.vx, self.vy)
        if speed > PLAYER_MAX_SPEED:
            scale = PLAYER_MAX_SPEED / speed
            self.vx *= scale
            self.vy *= scale

        self.x += self.vx
        self.y += self.vy

        self.x = max(-PLAYER_RADIUS * 2, min(SCREEN_WIDTH + PLAYER_RADIUS * 2, self.x))
        self.y = max(-PLAYER_RADIUS * 2, min(SCREEN_HEIGHT + PLAYER_RADIUS * 2, self.y))

        if speed > 1:
            self.trail.add(self.x, self.y)
        self.trail.update()

    def draw(self, surface):
        if self.x < -100:
            return
        color = TEAM1_COLOR if self.team == 1 else TEAM2_COLOR
        glow = TEAM1_GLOW if self.team == 1 else TEAM2_GLOW

        shadow_surf = pygame.Surface((PLAYER_RADIUS * 2 + 10, PLAYER_RADIUS * 2 + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 60),
                            (5, 10, PLAYER_RADIUS * 2, PLAYER_RADIUS * 2))
        surface.blit(shadow_surf, (int(self.x - PLAYER_RADIUS - 5), int(self.y - PLAYER_RADIUS - 5)))

        self.trail.draw(surface, PLAYER_RADIUS - 8, glow)

        glow_surf = pygame.Surface((PLAYER_RADIUS * 2 + 20, PLAYER_RADIUS * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*glow, 80), (PLAYER_RADIUS + 10, PLAYER_RADIUS + 10), PLAYER_RADIUS + 6)
        surface.blit(glow_surf, (int(self.x - PLAYER_RADIUS - 10), int(self.y - PLAYER_RADIUS - 10)))

        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), PLAYER_RADIUS - 4)
        pygame.draw.circle(surface, BLACK, (int(self.x), int(self.y)), PLAYER_RADIUS, 2)

        if math.hypot(self.vx, self.vy) > 0.5:
            angle = math.atan2(self.vy, self.vx)
            tip_x = self.x + math.cos(angle) * (PLAYER_RADIUS - 6)
            tip_y = self.y + math.sin(angle) * (PLAYER_RADIUS - 6)
            pygame.draw.circle(surface, BLACK, (int(tip_x), int(tip_y)), 5)

        # Nickname above player
        name_surf = font_tiny.render(self.nickname, True, WHITE)
        name_bg = pygame.Surface((name_surf.get_width() + 8, name_surf.get_height() + 4), pygame.SRCALPHA)
        name_bg.fill((0, 0, 0, 120))
        nx = int(self.x - name_bg.get_width() // 2)
        ny = int(self.y - PLAYER_RADIUS - 22)
        surface.blit(name_bg, (nx, ny))
        surface.blit(name_surf, (nx + 4, ny + 2))

        # Label inside circle
        lbl = font_small.render(self.label, True, BLACK)
        surface.blit(lbl, (int(self.x) - lbl.get_width() // 2, int(self.y) - lbl.get_height() // 2))

    def get_pos(self):
        return (self.x, self.y)

# ── Ball ──────────────────────────────────────────────────────────
class Ball:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.reset_timer = 0
        self.trail = Trail(max_len=14)
        self.last_toucher = None

    def update(self, players):
        if self.reset_timer > 0:
            self.reset_timer -= 1
            if self.reset_timer <= 0:
                self.x = SCREEN_WIDTH // 2
                self.y = SCREEN_HEIGHT // 2
                self.vx = 0
                self.vy = 0
            return None

        self.x += self.vx
        self.y += self.vy
        self.vx *= BALL_FRICTION
        self.vy *= BALL_FRICTION

        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_BALL_SPEED:
            scale = MAX_BALL_SPEED / speed
            self.vx *= scale
            self.vy *= scale

        if abs(self.vx) < 0.05:
            self.vx = 0
        if abs(self.vy) < 0.05:
            self.vy = 0

        if self.y - BALL_RADIUS < FIELD_TOP:
            self.y = FIELD_TOP + BALL_RADIUS
            self.vy = abs(self.vy) * 0.85
            shaker.add(2)
        elif self.y + BALL_RADIUS > FIELD_BOTTOM:
            self.y = FIELD_BOTTOM - BALL_RADIUS
            self.vy = -abs(self.vy) * 0.85
            shaker.add(2)

        if self.y < GOAL_TOP or self.y > GOAL_BOTTOM:
            if self.x - BALL_RADIUS < FIELD_LEFT:
                self.x = FIELD_LEFT + BALL_RADIUS
                self.vx = abs(self.vx) * 0.85
                shaker.add(2)
            elif self.x + BALL_RADIUS > FIELD_RIGHT:
                self.x = FIELD_RIGHT - BALL_RADIUS
                self.vx = -abs(self.vx) * 0.85
                shaker.add(2)

        if FIELD_LEFT - GOAL_WIDTH < self.x < FIELD_LEFT and GOAL_TOP < self.y < GOAL_BOTTOM:
            return 2
        elif FIELD_RIGHT < self.x < FIELD_RIGHT + GOAL_WIDTH and GOAL_TOP < self.y < GOAL_BOTTOM:
            return 1

        for player in players:
            px, py = player.get_pos()
            dx = self.x - px
            dy = self.y - py
            dist = math.hypot(dx, dy)
            min_dist = PLAYER_RADIUS + BALL_RADIUS
            if dist < min_dist and dist > 0:
                overlap = min_dist - dist
                nx = dx / dist
                ny = dy / dist
                self.x += nx * overlap
                self.y += ny * overlap
                self.vx += player.vx * 0.35
                self.vy += player.vy * 0.35
                self.last_toucher = player
                shaker.add(3)
                spawn_particles(self.x, self.y, WHITE, count=8, speed=4, life=18, size=4)

        if speed > 2:
            self.trail.add(self.x, self.y)
        self.trail.update()

        return None

    def kick(self, player):
        px, py = player.get_pos()
        dx = self.x - px
        dy = self.y - py
        dist = math.hypot(dx, dy)
        if dist < KICK_RANGE and dist > 0:
            nx = dx / dist
            ny = dy / dist
            self.vx += nx * KICK_POWER
            self.vy += ny * KICK_POWER
            self.last_toucher = player
            shaker.add(4)
            spawn_kick_ripple(self.x, self.y, WHITE)
            return True
        return False

    def reset(self):
        self.reset_timer = 60
        self.last_toucher = None

    def draw_trail(self, surface):
        if self.reset_timer > 0:
            return
        self.trail.draw(surface, BALL_RADIUS - 4, (255, 255, 200))

    def draw(self, surface):
        if self.reset_timer > 0:
            return

        shadow_surf = pygame.Surface((BALL_RADIUS * 2 + 8, BALL_RADIUS * 2 + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 70),
                            (2, 6, BALL_RADIUS * 2, BALL_RADIUS * 2))
        surface.blit(shadow_surf, (int(self.x - BALL_RADIUS - 2), int(self.y - BALL_RADIUS - 2)))

        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), BALL_RADIUS)
        pygame.draw.circle(surface, (220, 220, 220), (int(self.x), int(self.y)), BALL_RADIUS - 4)
        pygame.draw.circle(surface, BLACK, (int(self.x), int(self.y)), BALL_RADIUS, 2)

        pygame.draw.line(surface, BLACK,
                         (int(self.x - BALL_RADIUS + 4), int(self.y)),
                         (int(self.x + BALL_RADIUS - 4), int(self.y)), 1)

# ── Drawing Helpers ───────────────────────────────────────────────
def draw_field(surface):
    tile = 40
    for y in range(FIELD_TOP, FIELD_BOTTOM, tile):
        for x in range(FIELD_LEFT, FIELD_RIGHT, tile):
            color = GRASS_LIGHT if ((x // tile) + (y // tile)) % 2 == 0 else GRASS_DARK
            pygame.draw.rect(surface, color, (x, y, tile, tile))

    pygame.draw.rect(surface, WHITE, (FIELD_LEFT, FIELD_TOP, FIELD_WIDTH, FIELD_HEIGHT), 4)
    pygame.draw.line(surface, WHITE, (SCREEN_WIDTH // 2, FIELD_TOP), (SCREEN_WIDTH // 2, FIELD_BOTTOM), 3)
    pygame.draw.circle(surface, WHITE, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), 70, 3)
    pygame.draw.circle(surface, WHITE, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), 6)

    pygame.draw.rect(surface, WHITE, (FIELD_LEFT, SCREEN_HEIGHT // 2 - 120, 120, 240), 2)
    pygame.draw.rect(surface, WHITE, (FIELD_RIGHT - 120, SCREEN_HEIGHT // 2 - 120, 120, 240), 2)

    pygame.draw.rect(surface, WHITE, (FIELD_LEFT - GOAL_WIDTH, GOAL_TOP, GOAL_WIDTH, GOAL_HEIGHT), 4)
    pygame.draw.rect(surface, WHITE, (FIELD_RIGHT, GOAL_TOP, GOAL_WIDTH, GOAL_HEIGHT), 4)

    for i in range(0, GOAL_HEIGHT, 12):
        pygame.draw.line(surface, (180, 180, 180, 120),
                         (FIELD_LEFT - GOAL_WIDTH, GOAL_TOP + i), (FIELD_LEFT, GOAL_TOP + i), 1)
        pygame.draw.line(surface, (180, 180, 180, 120),
                         (FIELD_RIGHT, GOAL_TOP + i), (FIELD_RIGHT + GOAL_WIDTH, GOAL_TOP + i), 1)
    for i in range(0, GOAL_WIDTH, 8):
        pygame.draw.line(surface, (180, 180, 180, 120),
                         (FIELD_LEFT - GOAL_WIDTH + i, GOAL_TOP), (FIELD_LEFT - GOAL_WIDTH + i, GOAL_BOTTOM), 1)
        pygame.draw.line(surface, (180, 180, 180, 120),
                         (FIELD_RIGHT + i, GOAL_TOP), (FIELD_RIGHT + i, GOAL_BOTTOM), 1)

    pygame.draw.arc(surface, WHITE, (FIELD_LEFT - 20, FIELD_TOP - 20, 40, 40), 0, math.pi / 2, 2)
    pygame.draw.arc(surface, WHITE, (FIELD_RIGHT - 20, FIELD_TOP - 20, 40, 40), math.pi / 2, math.pi, 2)
    pygame.draw.arc(surface, WHITE, (FIELD_LEFT - 20, FIELD_BOTTOM - 20, 40, 40), -math.pi / 2, 0, 2)
    pygame.draw.arc(surface, WHITE, (FIELD_RIGHT - 20, FIELD_BOTTOM - 20, 40, 40), math.pi, 3 * math.pi / 2, 2)


def draw_scores(surface, t1, t2):
    bar = pygame.Surface((SCREEN_WIDTH, 50), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 120))
    surface.blit(bar, (0, 0))

    score_text = font.render(f"{t1}  —  {t2}", True, WHITE)
    surface.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 5))

    p1 = font_small.render("Team 1: WASD + SPACE", True, TEAM1_COLOR)
    p2 = font_small.render("Team 2: WASD + SPACE", True, TEAM2_COLOR)
    surface.blit(p1, (FIELD_LEFT + 10, 15))
    surface.blit(p2, (FIELD_RIGHT - p2.get_width() - 10, 15))

    for i in range(5):
        c1 = TEAM1_COLOR if i < t1 else (60, 60, 60)
        c2 = TEAM2_COLOR if i < t2 else (60, 60, 60)
        pygame.draw.circle(surface, c1, (SCREEN_WIDTH // 2 - 90 - i * 22, 28), 6)
        pygame.draw.circle(surface, c2, (SCREEN_WIDTH // 2 + 90 + i * 22, 28), 6)


def draw_winner(surface, winner_team, winner_name=None):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    color = TEAM1_COLOR if winner_team == 1 else TEAM2_COLOR
    if winner_name:
        title = f"{winner_name.upper()} WINS!"
    else:
        title = f"TEAM {winner_team} WINS!"
    text = font_large.render(title, True, color)
    shadow = font_large.render(title, True, BLACK)
    sub = font_small.render("Host: Press R to restart  |  Anyone: ESC to quit", True, WHITE)

    surface.blit(shadow, (SCREEN_WIDTH // 2 - text.get_width() // 2 + 3, SCREEN_HEIGHT // 2 - 45 + 3))
    surface.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 45))
    surface.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, SCREEN_HEIGHT // 2 + 45))


def draw_goal_flash(surface, message, timer):
    radius = 100 + (90 - timer) * 4
    alpha = int(255 * (timer / 90))
    flash = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(flash, (255, 255, 255, alpha // 3), (radius, radius), radius)
    surface.blit(flash, (SCREEN_WIDTH // 2 - radius, SCREEN_HEIGHT // 2 - radius))

    text = font_goal.render(message, True, GOLD)
    shadow = font_goal.render(message, True, BLACK)
    y_pos = SCREEN_HEIGHT // 2 - 100
    surface.blit(shadow, (SCREEN_WIDTH // 2 - text.get_width() // 2 + 3, y_pos + 3))
    surface.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y_pos))


def draw_replay_banner(surface):
    banner = pygame.Surface((200, 40), pygame.SRCALPHA)
    banner.fill((0, 0, 0, 160))
    surface.blit(banner, (SCREEN_WIDTH // 2 - 100, 60))
    text = font_replay.render("REPLAY", True, GOLD)
    surface.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 62))


def draw_replay_trails(surface, replay_frames, replay_index):
    if not replay_frames or replay_index < 0:
        return

    trail_len = 10
    for p_idx in range(len(replay_frames[0]['players'])):
        for t in range(1, trail_len + 1):
            idx = replay_index - t
            if idx < 0:
                break
            frame = replay_frames[idx]
            px, py, _, _, team, _, _ = frame['players'][p_idx]
            alpha = int(180 * (1 - t / (trail_len + 1)))
            color = TEAM1_GLOW if team == 1 else TEAM2_GLOW
            radius = PLAYER_RADIUS - 8
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, alpha), (radius, radius), radius)
            surface.blit(s, (int(px - radius), int(py - radius)))

    ball_trail_len = 12
    for t in range(1, ball_trail_len + 1):
        idx = replay_index - t
        if idx < 0:
            break
        bx, by, _, _ = replay_frames[idx]['ball']
        alpha = int(180 * (1 - t / (ball_trail_len + 1)))
        radius = BALL_RADIUS - 4
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 255, 200, alpha), (radius, radius), radius)
        surface.blit(s, (int(bx - radius), int(by - radius)))


def draw_replay_frame(surface, frame):
    bx, by, bvx, bvy = frame['ball']

    shadow_surf = pygame.Surface((BALL_RADIUS * 2 + 8, BALL_RADIUS * 2 + 8), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surf, (0, 0, 0, 70), (2, 6, BALL_RADIUS * 2, BALL_RADIUS * 2))
    surface.blit(shadow_surf, (int(bx - BALL_RADIUS - 2), int(by - BALL_RADIUS - 2)))

    pygame.draw.circle(surface, WHITE, (int(bx), int(by)), BALL_RADIUS)
    pygame.draw.circle(surface, (220, 220, 220), (int(bx), int(by)), BALL_RADIUS - 4)
    pygame.draw.circle(surface, BLACK, (int(bx), int(by)), BALL_RADIUS, 2)
    pygame.draw.line(surface, BLACK,
                     (int(bx - BALL_RADIUS + 4), int(by)),
                     (int(bx + BALL_RADIUS - 4), int(by)), 1)

    for px, py, pvx, pvy, team, label, nickname in frame['players']:
        color = TEAM1_COLOR if team == 1 else TEAM2_COLOR
        glow = TEAM1_GLOW if team == 1 else TEAM2_GLOW

        shadow_surf = pygame.Surface((PLAYER_RADIUS * 2 + 10, PLAYER_RADIUS * 2 + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 60), (5, 10, PLAYER_RADIUS * 2, PLAYER_RADIUS * 2))
        surface.blit(shadow_surf, (int(px - PLAYER_RADIUS - 5), int(py - PLAYER_RADIUS - 5)))

        glow_surf = pygame.Surface((PLAYER_RADIUS * 2 + 20, PLAYER_RADIUS * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*glow, 80), (PLAYER_RADIUS + 10, PLAYER_RADIUS + 10), PLAYER_RADIUS + 6)
        surface.blit(glow_surf, (int(px - PLAYER_RADIUS - 10), int(py - PLAYER_RADIUS - 10)))

        pygame.draw.circle(surface, color, (int(px), int(py)), PLAYER_RADIUS)
        pygame.draw.circle(surface, WHITE, (int(px), int(py)), PLAYER_RADIUS - 4)
        pygame.draw.circle(surface, BLACK, (int(px), int(py)), PLAYER_RADIUS, 2)

        if math.hypot(pvx, pvy) > 0.5:
            angle = math.atan2(pvy, pvx)
            tip_x = px + math.cos(angle) * (PLAYER_RADIUS - 6)
            tip_y = py + math.sin(angle) * (PLAYER_RADIUS - 6)
            pygame.draw.circle(surface, BLACK, (int(tip_x), int(tip_y)), 5)

        # Nickname
        name_surf = font_tiny.render(nickname, True, WHITE)
        name_bg = pygame.Surface((name_surf.get_width() + 8, name_surf.get_height() + 4), pygame.SRCALPHA)
        name_bg.fill((0, 0, 0, 120))
        nx = int(px - name_bg.get_width() // 2)
        ny = int(py - PLAYER_RADIUS - 22)
        surface.blit(name_bg, (nx, ny))
        surface.blit(name_surf, (nx + 4, ny + 2))

        lbl = font_small.render(label, True, BLACK)
        surface.blit(lbl, (int(px) - lbl.get_width() // 2, int(py) - lbl.get_height() // 2))

    for px, py, r, g, b, size, life_ratio in frame.get('particles', []):
        alpha = int(255 * life_ratio)
        s = pygame.Surface((int(size * 2), int(size * 2)), pygame.SRCALPHA)
        pygame.draw.circle(s, (r, g, b, alpha), (int(size), int(size)), int(size))
        surface.blit(s, (int(px - size), int(py - size)))


def render_game(surface, ball, players, particles, team1_score, team2_score,
                goal_message, goal_timer, in_replay, replay_frames, replay_index, winner, winner_name=None,
                shake_offset=None):
    draw_field(surface)
    draw_scores(surface, team1_score, team2_score)

    if in_replay and replay_frames and 0 <= replay_index < len(replay_frames):
        frame = replay_frames[replay_index]
        draw_replay_trails(surface, replay_frames, replay_index)
        draw_replay_frame(surface, frame)
        draw_replay_banner(surface)
        if shake_offset is None:
            shake_offset = tuple(frame.get('shake', [0, 0]))
    else:
        ball.draw_trail(surface)
        for p in players:
            p.draw(surface)
        ball.draw(surface)
        for pt in particles:
            pt.draw(surface)
        if shake_offset is None:
            shake_offset = shaker.get_offset()

    if goal_timer > 0:
        draw_goal_flash(surface, goal_message, min(goal_timer, 90))

    if winner and not in_replay:
        draw_winner(surface, winner, winner_name)

    return shake_offset or (0, 0)


def get_state_dict(ball, players, particles, team1_score, team2_score,
                   goal_message, goal_timer, in_replay, winner, winner_name=''):
    return {
        'ball': [ball.x, ball.y, ball.vx, ball.vy],
        'brt': ball.reset_timer,
        'players': [[p.x, p.y, p.vx, p.vy, p.team, p.label, p.nickname] for p in players],
        'scores': [team1_score, team2_score],
        'msg': goal_message if goal_timer > 0 else '',
        'replay': in_replay,
        'winner': winner or 0,
        'winner_name': winner_name or '',
        'gt': goal_timer,
        'particles': serialize_particles(particles),
        'shake': list(shaker.get_offset()),
    }


def apply_state_dict(state, ball, players):
    b = state['ball']
    ball.x, ball.y, ball.vx, ball.vy = b[0], b[1], b[2], b[3]
    ball.reset_timer = state.get('brt', 0)

    for i, p_data in enumerate(state['players']):
        if i < len(players):
            players[i].x, players[i].y = p_data[0], p_data[1]
            players[i].vx, players[i].vy = p_data[2], p_data[3]
            players[i].nickname = p_data[6] if len(p_data) > 6 else f"Player {i+1}"
            speed = math.hypot(players[i].vx, players[i].vy)
            if speed > 1:
                players[i].trail.add(players[i].x, players[i].y)
            players[i].trail.update()

    speed = math.hypot(ball.vx, ball.vy)
    if speed > 2:
        ball.trail.add(ball.x, ball.y)
    ball.trail.update()

    particles.clear()
    for pt_data in state.get('particles', []):
        pt = Particle(0, 0, WHITE, 0, 0, 0)
        pt.x, pt.y = pt_data[0], pt_data[1]
        pt.color = (pt_data[2], pt_data[3], pt_data[4])
        pt.size = pt_data[5]
        pt.life = int(pt_data[6] * 50)
        pt.max_life = 50
        particles.append(pt)

    return state.get('shake', [0, 0])


# ── Styled Menu System ──────────────────────────────────────────
def draw_menu_background(surface):
    surface.fill(MENU_BG)
    # Animated grid effect
    for i in range(0, SCREEN_WIDTH, 60):
        pygame.draw.line(surface, (30, 30, 45), (i, 0), (i, SCREEN_HEIGHT), 1)
    for i in range(0, SCREEN_HEIGHT, 60):
        pygame.draw.line(surface, (30, 30, 45), (0, i), (SCREEN_WIDTH, i), 1)

    # Center glow
    glow = pygame.Surface((400, 400), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (40, 40, 60, 80), (0, 0, 400, 400))
    surface.blit(glow, (SCREEN_WIDTH // 2 - 200, 100))


def draw_menu_button(surface, text, y, selected, hover=False):
    color = MENU_ACCENT if selected else (MENU_DIM if not hover else (150, 150, 160))
    bg_color = (40, 40, 55) if selected else (25, 25, 35)

    text_surf = font_menu.render(text, True, color)
    w = max(300, text_surf.get_width() + 60)
    h = 50
    x = SCREEN_WIDTH // 2 - w // 2

    # Button background
    btn = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(btn, (*bg_color, 220), (0, 0, w, h), border_radius=8)
    if selected:
        pygame.draw.rect(btn, (*MENU_ACCENT, 180), (0, 0, w, h), 2, border_radius=8)
    surface.blit(btn, (x, y))

    # Text
    surface.blit(text_surf, (SCREEN_WIDTH // 2 - text_surf.get_width() // 2, y + 10))

    return pygame.Rect(x, y, w, h)


def draw_text_input(surface, label, value, y, active):
    color = MENU_ACCENT if active else MENU_DIM
    label_surf = font_small.render(label, True, color)
    surface.blit(label_surf, (SCREEN_WIDTH // 2 - 200, y))

    # Input box
    box_w = 400
    box_h = 40
    box_x = SCREEN_WIDTH // 2 - box_w // 2
    box_y = y + 25

    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    box_color = (50, 50, 65) if active else (35, 35, 45)
    pygame.draw.rect(box, (*box_color, 220), (0, 0, box_w, box_h), border_radius=6)
    pygame.draw.rect(box, (*color, 150), (0, 0, box_w, box_h), 2, border_radius=6)
    surface.blit(box, (box_x, box_y))

    # Cursor blink
    display_val = value + ('|' if active and int(time.time() * 2) % 2 == 0 else '')
    val_surf = font_small.render(display_val, True, WHITE)
    surface.blit(val_surf, (box_x + 12, box_y + 10))

    return pygame.Rect(box_x, box_y, box_w, box_h)


def show_menu():
    options = [
        {'id': 'local_1v1', 'label': 'LOCAL 1v1'},
        {'id': 'host_1v1', 'label': 'HOST 1v1 MATCH'},
        {'id': 'host_2v2', 'label': 'HOST 2v2 MATCH'},
        {'id': 'join', 'label': 'JOIN MATCH'},
    ]
    selected = 0
    nickname = "Player"
    room_input = ""
    menu_state = 'main'  # 'main', 'nickname', 'room', 'join_wait'
    active_input = 'nickname'
    btn_rects = []

    while True:
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None, None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_clicked = True
            if event.type == pygame.KEYDOWN:
                if menu_state == 'main':
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(options)
                    if event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(options)
                    if event.key == pygame.K_RETURN:
                        chosen = options[selected]['id']
                        if chosen == 'local_1v1':
                            return chosen, 'Local 1', None
                        if chosen.startswith('host'):
                            menu_state = 'nickname'
                            active_input = 'nickname'
                        else:
                            menu_state = 'nickname'
                            active_input = 'nickname'
                    if event.key == pygame.K_ESCAPE:
                        return None, None, None
                elif menu_state in ('nickname', 'room'):
                    if event.key == pygame.K_RETURN:
                        if menu_state == 'nickname':
                            menu_state = 'room' if options[selected]['id'] == 'join' else 'host_wait'
                            active_input = 'room' if options[selected]['id'] == 'join' else 'none'
                        elif menu_state == 'room':
                            menu_state = 'join_wait'
                    elif event.key == pygame.K_BACKSPACE:
                        if active_input == 'nickname':
                            nickname = nickname[:-1]
                        else:
                            room_input = room_input[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        menu_state = 'main'
                    elif event.key == pygame.K_TAB:
                        active_input = 'room' if active_input == 'nickname' else 'nickname'
                    else:
                        if event.unicode.isprintable():
                            if active_input == 'nickname' and len(nickname) < 12:
                                nickname += event.unicode
                            elif active_input == 'room' and len(room_input) < 12:
                                room_input += event.unicode.upper()

        draw_menu_background(screen)

        # Title
        title = font_title.render("FOOTBALL", True, WHITE)
        subtitle = font_large.render("ONLINE", True, MENU_ACCENT)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))
        screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 140))

        if menu_state == 'main':
            btn_rects = []
            start_y = 280
            for i, opt in enumerate(options):
                rect = draw_menu_button(screen, opt['label'], start_y + i * 70, i == selected)
                btn_rects.append(rect)

            # Mouse hover
            for i, rect in enumerate(btn_rects):
                if rect.collidepoint(mouse_pos):
                    selected = i
                    if mouse_clicked:
                        chosen = options[i]['id']
                        if chosen == 'local_1v1':
                            return chosen, 'Local 1', None
                        if chosen.startswith('host'):
                            menu_state = 'nickname'
                            active_input = 'nickname'
                        else:
                            menu_state = 'nickname'
                            active_input = 'nickname'

            hint = font_tiny.render("UP/DOWN to navigate  |  ENTER to select  |  ESC to quit", True, MENU_DIM)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 560))

        elif menu_state == 'nickname':
            draw_text_input(screen, "YOUR NICKNAME", nickname, 280, active_input == 'nickname')
            hint = font_tiny.render("ENTER to continue  |  ESC to go back", True, MENU_DIM)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 400))

        elif menu_state == 'room':
            draw_text_input(screen, "YOUR NICKNAME", nickname, 240, active_input == 'nickname')
            draw_text_input(screen, "ROOM CODE", room_input, 340, active_input == 'room')
            hint = font_tiny.render("TAB to switch  |  ENTER to join  |  ESC to go back", True, MENU_DIM)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 460))

        elif menu_state == 'host_wait':
            return options[selected]['id'], nickname, None

        elif menu_state == 'join_wait':
            return 'join', nickname, room_input

        pygame.display.flip()
        clock.tick(60)

def show_notice(message, duration=2.5):
    start = time.time()
    while time.time() - start < duration:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        draw_menu_background(screen)
        text = font_large.render(message, True, MENU_ACCENT)
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 20))
        pygame.display.flip()
        clock.tick(60)

# ── Local 1v1 ───────────────────────────────────────────────────
def local_main(local_nickname):
    p1 = Player(FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "1", 1, local_nickname or "Local 1")
    p2 = Player(FIELD_LEFT + 100, SCREEN_HEIGHT // 2 + 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "2", 1, "Idle")
    p3 = Player(FIELD_RIGHT - 100, SCREEN_HEIGHT // 2, {
        'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT
    }, pygame.K_RETURN, "3", 2, "Local 2")
    p4 = Player(FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 + 60,
                {'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT},
                pygame.K_RETURN, "4", 2, "Idle")

    players = [p1, p2, p3, p4]
    ball = Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    p2.x, p2.y = -1000, -1000
    p4.x, p4.y = -1000, -1000

    team1_score = 0
    team2_score = 0
    winner = None
    winner_name = ""
    goal_message = ""
    goal_timer = 0

    replay_buffer = ReplayBuffer(max_frames=180)
    replay_frames = []
    replay_index = 0
    in_replay = False
    touch_controls.reset()

    running = True
    while running:
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            touch_controls.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if winner and event.key == pygame.K_r:
                    team1_score = 0
                    team2_score = 0
                    winner = None
                    winner_name = ""
                    ball.x = SCREEN_WIDTH // 2
                    ball.y = SCREEN_HEIGHT // 2
                    ball.vx = 0
                    ball.vy = 0
                    ball.reset_timer = 0
                    ball.last_toucher = None
                    p1.x, p1.y = FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60
                    p3.x, p3.y = FIELD_RIGHT - 100, SCREEN_HEIGHT // 2
                    p2.x, p2.y = -1000, -1000
                    p4.x, p4.y = -1000, -1000
                    for p in players:
                        p.vx = 0
                        p.vy = 0
                        p.prev_kick = False
                    replay_buffer.clear()
                    replay_frames = []
                    replay_index = 0
                    in_replay = False
                    goal_timer = 0
                    particles.clear()
                if not winner and not in_replay:
                    if event.key == p1.kick_key:
                        ball.kick(p1)
                    if event.key == p3.kick_key:
                        ball.kick(p3)

        mobile_kick = touch_controls.consume_kick()
        if not winner and not in_replay and mobile_kick:
            ball.kick(p1)

        if in_replay:
            replay_index += 1
            if replay_index >= len(replay_frames):
                in_replay = False
                goal_message = ""
                goal_timer = 0
                replay_buffer.clear()
                ball.reset()
                p1.x, p1.y = FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60
                p3.x, p3.y = FIELD_RIGHT - 100, SCREEN_HEIGHT // 2
                p2.x, p2.y = -1000, -1000
                p4.x, p4.y = -1000, -1000
                for p in players:
                    p.vx = 0
                    p.vy = 0
                    p.prev_kick = False
                particles.clear()
        elif not winner:
            mobile_move = touch_controls.get_move_state()
            p1_input = {
                'up': keys[p1.controls['up']] or mobile_move['up'],
                'down': keys[p1.controls['down']] or mobile_move['down'],
                'left': keys[p1.controls['left']] or mobile_move['left'],
                'right': keys[p1.controls['right']] or mobile_move['right'],
            }
            p3_input = {
                'up': keys[p3.controls['up']],
                'down': keys[p3.controls['down']],
                'left': keys[p3.controls['left']],
                'right': keys[p3.controls['right']],
            }

            p1.update(p1_input)
            p3.update(p3_input)
            resolve_player_collisions(players)

            scorer = ball.update(players)

            for pt in particles[:]:
                pt.update()
                if pt.life <= 0:
                    particles.remove(pt)

            if scorer:
                if scorer == 1:
                    team1_score += 1
                else:
                    team2_score += 1

                if ball.last_toucher and ball.last_toucher.team == scorer:
                    winner_name = ball.last_toucher.nickname
                    goal_message = f"GOAL! {ball.last_toucher.nickname}"
                else:
                    winner_name = f"Team {scorer}"
                    goal_message = f"GOAL! TEAM {scorer}"

                shaker.add(18)
                spawn_particles(ball.x, ball.y, GOLD, count=40, speed=10, life=50, size=8)
                spawn_particles(ball.x, ball.y, WHITE, count=20, speed=7, life=40, size=5)

                replay_buffer.record(ball, players, particles)
                replay_frames = replay_buffer.get_frames()
                replay_index = 0
                in_replay = True
                replay_buffer.clear()
                goal_timer = len(replay_frames) + 60

                if team1_score >= 5:
                    winner = 1
                    if not winner_name:
                        winner_name = p1.nickname or "Team 1"
                elif team2_score >= 5:
                    winner = 2
                    if not winner_name:
                        winner_name = p3.nickname or "Team 2"
            else:
                replay_buffer.record(ball, players, particles)

        shaker.update()

        if in_replay and replay_frames:
            frame = replay_frames[replay_index]
            state = {
                'ball': frame['ball'],
                'brt': ball.reset_timer,
                'players': frame['players'],
                'scores': [team1_score, team2_score],
                'msg': goal_message,
                'replay': True,
                'winner': winner or 0,
                'winner_name': winner_name or '',
                'gt': goal_timer,
                'particles': frame.get('particles', []),
                'shake': frame.get('shake', list(shaker.get_offset())),
            }
        else:
            state = get_state_dict(ball, players, particles, team1_score, team2_score,
                                   goal_message, goal_timer, in_replay, winner, winner_name)

        game_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        shake_x, shake_y = render_game(game_surf, ball, players, particles, team1_score, team2_score,
                    goal_message, goal_timer, in_replay, replay_frames, replay_index, winner, winner_name)
        screen.blit(game_surf, (shake_x, shake_y))
        pygame.display.flip()
        clock.tick(60)


# ── Host ──────────────────────────────────────────────────────────
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def host_main(mode, host_nickname):
    needed_clients = 1 if '1v1' in mode else 3
    available_ids = [2] if '1v1' in mode else [1, 2, 3]

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', PORT))
    server_socket.setblocking(False)

    local_ip = get_local_ip()
    room_id = ip_to_room_id(local_ip)

    clients = {}  # addr -> {'id': pid, 'nickname': str}
    client_inputs = {}  # addr -> input dict
    client_last_time = {}  # addr -> timestamp

    # Players
    p1 = Player(FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "1", 1, host_nickname)
    p2 = Player(FIELD_LEFT + 100, SCREEN_HEIGHT // 2 + 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "2", 1, "Player 2")
    p3 = Player(FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 - 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "3", 2, "Player 3")
    p4 = Player(FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 + 60,
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                pygame.K_SPACE, "4", 2, "Player 4")

    players = [p1, p2, p3, p4]
    ball = Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    if '1v1' in mode:
        p2.x, p2.y = -1000, -1000
        p4.x, p4.y = -1000, -1000

    # Lobby
    in_lobby = True
    while in_lobby:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_SPACE and len(clients) > 0:
                    in_lobby = False

        try:
            while True:
                data, addr = server_socket.recvfrom(1024)
                msg = data.decode('utf-8')
                if msg.startswith('JOIN') and addr not in clients and available_ids:
                    parts = msg.split('|')
                    client_nick = parts[1] if len(parts) > 1 else f"Player {available_ids[0] + 1}"
                    pid = available_ids.pop(0)
                    clients[addr] = {'id': pid, 'nickname': client_nick[:12]}
                    client_last_time[addr] = time.time()
                    players[pid].nickname = client_nick[:12]
                    server_socket.sendto(f'ASSIGN|{pid}'.encode(), addr)
        except BlockingIOError:
            pass

        if len(clients) == needed_clients:
            in_lobby = False

        draw_menu_background(screen)

        title = font_large.render("LOBBY", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        mode_text = font_menu.render(f"Mode: {mode.upper().replace('_', ' ')}", True, MENU_ACCENT)
        screen.blit(mode_text, (SCREEN_WIDTH // 2 - mode_text.get_width() // 2, 150))

        # Room code display
        room_bg = pygame.Surface((320, 60), pygame.SRCALPHA)
        pygame.draw.rect(room_bg, (40, 40, 55, 220), (0, 0, 320, 60), border_radius=8)
        pygame.draw.rect(room_bg, (*MENU_ACCENT, 180), (0, 0, 320, 60), 2, border_radius=8)
        screen.blit(room_bg, (SCREEN_WIDTH // 2 - 160, 220))

        room_label = font_small.render("ROOM CODE", True, MENU_DIM)
        screen.blit(room_label, (SCREEN_WIDTH // 2 - room_label.get_width() // 2, 228))

        room_text = font.render(room_id, True, GOLD)
        screen.blit(room_text, (SCREEN_WIDTH // 2 - room_text.get_width() // 2, 250))

        ip_text = font_tiny.render(f"IP: {local_ip}:{PORT}", True, (80, 80, 90))
        screen.blit(ip_text, (SCREEN_WIDTH // 2 - ip_text.get_width() // 2, 290))

        status = font_small.render(f"Players: {len(clients) + 1}/{needed_clients + 1}", True, WHITE)
        screen.blit(status, (SCREEN_WIDTH // 2 - status.get_width() // 2, 340))

        # Player list
        names = [(p1.nickname, TEAM1_COLOR, True),
                 (p2.nickname, TEAM1_COLOR, '1v1' not in mode),
                 (p3.nickname, TEAM2_COLOR, True),
                 (p4.nickname, TEAM2_COLOR, '1v1' not in mode)]

        for i, (name, color, active) in enumerate(names):
            y = 400 + i * 45
            if not active:
                color = (80, 80, 80)
            text = font_small.render(f"  {name}", True, color)
            screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))

        hint = font_tiny.render("Press SPACE to start  |  ESC to quit", True, MENU_DIM)
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 620))

        pygame.display.flip()
        clock.tick(60)

    # Broadcast START with nicknames
    start_data = json.dumps({'nicknames': [p.nickname for p in players]})
    for addr in clients:
        server_socket.sendto(f'START|{start_data}'.encode(), addr)

    # Game state
    team1_score = 0
    team2_score = 0
    winner = None
    winner_name = ""
    goal_message = ""
    goal_timer = 0

    replay_buffer = ReplayBuffer(max_frames=180)
    replay_frames = []
    replay_index = 0
    in_replay = False
    touch_controls.reset()

    running = True
    while running:
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            touch_controls.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if winner and event.key == pygame.K_r:
                    team1_score = 0
                    team2_score = 0
                    winner = None
                    winner_name = ""
                    ball.x = SCREEN_WIDTH // 2
                    ball.y = SCREEN_HEIGHT // 2
                    ball.vx = 0
                    ball.vy = 0
                    ball.reset_timer = 0
                    ball.last_toucher = None
                    p1.x, p1.y = FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60
                    p2.x, p2.y = (-1000, -1000) if '1v1' in mode else (FIELD_LEFT + 100, SCREEN_HEIGHT // 2 + 60)
                    p3.x, p3.y = FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 - 60
                    p4.x, p4.y = (-1000, -1000) if '1v1' in mode else (FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 + 60)
                    for p in players:
                        p.vx = 0
                        p.vy = 0
                        p.prev_kick = False
                    replay_buffer.clear()
                    replay_frames = []
                    replay_index = 0
                    in_replay = False
                    goal_timer = 0
                    particles.clear()
                if not winner and not in_replay and event.key == p1.kick_key:
                    ball.kick(p1)

        mobile_kick = touch_controls.consume_kick()
        if not winner and not in_replay and mobile_kick:
            ball.kick(p1)

        # Receive inputs
        try:
            while True:
                data, addr = server_socket.recvfrom(1024)
                msg = data.decode('utf-8')
                if msg.startswith('INPUT') and addr in clients:
                    parts = msg.split('|')
                    if len(parts) == 6:
                        inp = {
                            'up': int(parts[1]),
                            'down': int(parts[2]),
                            'left': int(parts[3]),
                            'right': int(parts[4]),
                            'kick': int(parts[5])
                        }
                        client_inputs[addr] = inp
                        client_last_time[addr] = time.time()
        except BlockingIOError:
            pass

        disconnected_addr = None
        for addr in clients:
            last_seen = client_last_time.get(addr, time.time())
            if time.time() - last_seen > DISCONNECT_TIMEOUT:
                disconnected_addr = addr

        if disconnected_addr:
            nickname = clients[disconnected_addr]['nickname']
            for addr in clients:
                if addr != disconnected_addr:
                    server_socket.sendto(f'DISCONNECT|{nickname}'.encode(), addr)
            show_notice(f"{nickname} disconnected")
            server_socket.close()
            return

        # Update
        if in_replay:
            replay_index += 1
            if replay_index >= len(replay_frames):
                in_replay = False
                goal_message = ""
                goal_timer = 0
                replay_buffer.clear()
                ball.reset()
                p1.x, p1.y = FIELD_LEFT + 100, SCREEN_HEIGHT // 2 - 60
                if '1v1' not in mode:
                    p2.x, p2.y = FIELD_LEFT + 100, SCREEN_HEIGHT // 2 + 60
                p3.x, p3.y = FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 - 60
                if '1v1' not in mode:
                    p4.x, p4.y = FIELD_RIGHT - 100, SCREEN_HEIGHT // 2 + 60
                for p in players:
                    p.vx = 0
                    p.vy = 0
                    p.prev_kick = False
                particles.clear()
        elif not winner:
            mobile_move = touch_controls.get_move_state()
            host_input = {
                'up': keys[p1.controls['up']] or mobile_move['up'],
                'down': keys[p1.controls['down']] or mobile_move['down'],
                'left': keys[p1.controls['left']] or mobile_move['left'],
                'right': keys[p1.controls['right']] or mobile_move['right'],
            }
            p1.update(host_input)

            for addr, info in clients.items():
                pid = info['id']
                inp = client_inputs.get(addr, {})
                if time.time() - client_last_time.get(addr, 0) > 1.0:
                    inp = {}
                p = players[pid]
                p.update(inp)

                if inp.get('kick') and not p.prev_kick and not ball.reset_timer:
                    ball.kick(p)
                p.prev_kick = inp.get('kick', False)

            resolve_player_collisions(players)

            scorer = ball.update(players)

            for pt in particles[:]:
                pt.update()
                if pt.life <= 0:
                    particles.remove(pt)

            if scorer:
                if scorer == 1:
                    team1_score += 1
                else:
                    team2_score += 1

                if ball.last_toucher and ball.last_toucher.team == scorer:
                    goal_message = f"GOAL! {ball.last_toucher.nickname}"
                else:
                    goal_message = f"GOAL! TEAM {scorer}"

                shaker.add(18)
                spawn_particles(ball.x, ball.y, GOLD, count=40, speed=10, life=50, size=8)
                spawn_particles(ball.x, ball.y, WHITE, count=20, speed=7, life=40, size=5)

                replay_buffer.record(ball, players, particles)
                replay_frames = replay_buffer.get_frames()
                replay_index = 0
                in_replay = True
                replay_buffer.clear()
                goal_timer = len(replay_frames) + 60

                if team1_score >= 5:
                    winner = 1
                elif team2_score >= 5:
                    winner = 2
            else:
                replay_buffer.record(ball, players, particles)

        shaker.update()

        # Build state
        if in_replay and replay_frames:
            frame = replay_frames[replay_index]
            state = {
                'ball': frame['ball'],
                'brt': ball.reset_timer,
                'players': frame['players'],
                'scores': [team1_score, team2_score],
                'msg': goal_message,
                'replay': True,
                'winner': winner or 0,
                'winner_name': winner_name or '',
                'gt': goal_timer,
                'particles': frame.get('particles', []),
                'shake': list(shaker.get_offset()),
            }
        else:
            state = get_state_dict(ball, players, particles, team1_score, team2_score,
                                   goal_message, goal_timer, in_replay, winner, winner_name)

        state_data = 'STATE|' + json.dumps(state)
        for addr in clients:
            server_socket.sendto(state_data.encode(), addr)

        # Render
        game_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        shake_x, shake_y = render_game(game_surf, ball, players, particles, team1_score, team2_score,
                    goal_message, goal_timer, in_replay, replay_frames, replay_index, winner, winner_name)
        screen.blit(game_surf, (shake_x, shake_y))
        pygame.display.flip()
        clock.tick(60)


# ── Client ────────────────────────────────────────────────────────
def client_main(server_ip, client_nickname):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))
    sock.setblocking(False)
    server_addr = (server_ip, PORT)

    sock.sendto(f'JOIN|{client_nickname}'.encode(), server_addr)

    # Wait for assign
    player_id = None
    nicknames = ["Player 1", "Player 2", "Player 3", "Player 4"]
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

        try:
            while True:
                data, addr = sock.recvfrom(1024)
                msg = data.decode('utf-8')
                if msg.startswith('ASSIGN'):
                    player_id = int(msg.split('|')[1])
                    waiting = False
        except BlockingIOError:
            pass

        draw_menu_background(screen)
        title = font_large.render("CONNECTING...", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
        pygame.display.flip()
        clock.tick(60)

    # Wait for start
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

        try:
            while True:
                data, addr = sock.recvfrom(4096)
                msg = data.decode('utf-8')
                if msg.startswith('START'):
                    parts = msg.split('|', 1)
                    if len(parts) > 1:
                        try:
                            start_data = json.loads(parts[1])
                            nicknames = start_data.get('nicknames', nicknames)
                        except:
                            pass
                    waiting = False
                elif msg.startswith('STATE|'):
                    waiting = False
        except BlockingIOError:
            pass

        draw_menu_background(screen)
        text = font_large.render(f"{nicknames[player_id]}", True, GOLD)
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
        sub = font_small.render("Waiting for game start...", True, WHITE)
        screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, SCREEN_HEIGHT // 2 + 20))
        pygame.display.flip()
        clock.tick(60)

    # Game objects
    players = [
        Player(-1000, -1000, {}, pygame.K_SPACE, "1", 1, nicknames[0]),
        Player(-1000, -1000, {}, pygame.K_SPACE, "2", 1, nicknames[1]),
        Player(-1000, -1000, {}, pygame.K_SPACE, "3", 2, nicknames[2]),
        Player(-1000, -1000, {}, pygame.K_SPACE, "4", 2, nicknames[3]),
    ]
    ball = Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    team1_score = 0
    team2_score = 0
    winner = None
    winner_name = ""
    goal_message = ""
    goal_timer = 0
    in_replay = False
    client_history = []
    replay_index = 0
    touch_controls.reset()

    running = True
    last_state_time = time.time()
    while running:
        keys = pygame.key.get_pressed()
        kick = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            touch_controls.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_SPACE:
                    kick = True

        mobile_move = touch_controls.get_move_state()
        input_up = int(keys[pygame.K_w] or mobile_move['up'])
        input_down = int(keys[pygame.K_s] or mobile_move['down'])
        input_left = int(keys[pygame.K_a] or mobile_move['left'])
        input_right = int(keys[pygame.K_d] or mobile_move['right'])
        kick = int(kick or touch_controls.consume_kick())
        input_msg = f"INPUT|{input_up}|{input_down}|{input_left}|{input_right}|{kick}"
        sock.sendto(input_msg.encode(), server_addr)

        state = None
        try:
            while True:
                data, addr = sock.recvfrom(8192)
                msg = data.decode('utf-8')
                if msg.startswith('STATE|'):
                    try:
                        state = json.loads(msg[6:])
                        last_state_time = time.time()
                    except json.JSONDecodeError:
                        pass
                elif msg.startswith('DISCONNECT|'):
                    other_nick = msg.split('|', 1)[1]
                    show_notice(f"{other_nick} disconnected")
                    sock.close()
                    return
        except BlockingIOError:
            pass

        if time.time() - last_state_time > DISCONNECT_TIMEOUT:
            show_notice("Host disconnected")
            sock.close()
            return

        shake_x, shake_y = 0, 0
        if state:
            team1_score, team2_score = state['scores']
            goal_message = state['msg']
            goal_timer = state['gt']
            in_replay = state['replay']
            winner = state['winner'] if state['winner'] else None
            winner_name = state.get('winner_name', '')
            shake_x, shake_y = apply_state_dict(state, ball, players)

            if in_replay:
                client_history.append(state)
                replay_index = len(client_history) - 1
            else:
                client_history.clear()
                replay_index = 0

        game_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        render_game(game_surf, ball, players, particles, team1_score, team2_score,
                    goal_message, goal_timer, in_replay, client_history, replay_index, winner, winner_name)
        touch_controls.draw(game_surf)
        screen.blit(game_surf, (shake_x, shake_y))
        pygame.display.flip()
        clock.tick(60)


# ── Entry ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        mode, nickname, room_code = show_menu()
        if mode is None:
            break

        if mode == 'local_1v1':
            local_main(nickname)
        elif mode.startswith('host'):
            host_main(mode, nickname)
        else:
            target_ip = '127.0.0.1'
            if room_code:
                discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                discover_sock.settimeout(2.0)
                try:
                    discover_sock.sendto(f'DISCOVER|{room_code}'.encode(), ('<broadcast>', PORT))
                    data, addr = discover_sock.recvfrom(1024)
                    if data.decode('utf-8') == 'FOUND':
                        target_ip = addr[0]
                except Exception:
                    pass
                finally:
                    discover_sock.close()
            client_main(target_ip, nickname)

    pygame.quit()
    sys.exit()