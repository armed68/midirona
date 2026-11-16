"""
Midirona - Visuals Engine & Atmosphere
Includes:
- Dynamic reactive backgrounds (twinkling starfield, ambient floating motes, audio-pulse aura)
- Falling notes waterfall visualizer (with left/right hand color palettes)
- Rising note trails & chord painting
- Key-hit spark bursts, impact ripples, and floating score texts
"""

import math
import random
import pygame

COLOR_THEMES = {
    'Neon Twilight': {
        'bg_top': (15, 14, 28),
        'bg_bottom': (30, 24, 48),
        'right_hand': (0, 230, 255),
        'right_hand_core': (180, 250, 255),
        'left_hand': (255, 160, 40),
        'left_hand_core': (255, 230, 180),
        'accent': (255, 60, 140),
        'star': (200, 220, 255)
    },
    'Sakura Dream': {
        'bg_top': (28, 16, 26),
        'bg_bottom': (52, 28, 48),
        'right_hand': (255, 130, 185),
        'right_hand_core': (255, 220, 240),
        'left_hand': (170, 140, 255),
        'left_hand_core': (235, 220, 255),
        'accent': (255, 190, 210),
        'star': (255, 210, 230)
    },
    'Emerald Grove': {
        'bg_top': (10, 22, 20),
        'bg_bottom': (18, 42, 36),
        'right_hand': (50, 235, 160),
        'right_hand_core': (200, 255, 230),
        'left_hand': (240, 200, 60),
        'left_hand_core': (255, 245, 190),
        'accent': (80, 255, 210),
        'star': (190, 255, 220)
    },
    'Midnight Ocean': {
        'bg_top': (8, 14, 26),
        'bg_bottom': (14, 28, 54),
        'right_hand': (70, 170, 255),
        'right_hand_core': (210, 235, 255),
        'left_hand': (50, 230, 210),
        'left_hand_core': (200, 255, 250),
        'accent': (120, 200, 255),
        'star': (210, 230, 255)
    }
}


class Particle:
    """Spark / dust particle."""
    def __init__(self, x, y, vx, vy, color, life, size=3.0, gravity=0.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.max_life = life
        self.life = life
        self.size = size
        self.gravity = gravity

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt

    def is_alive(self):
        return self.life > 0


class RisingNoteTrail:
    """Rising glowing ribbon painted into the sky when a key is played."""
    def __init__(self, x, width, color, speed=140.0):
        self.x = x
        self.width = max(8, width)
        self.color = color
        self.speed = speed
        self.segments = []  # [(y, alpha, height)]
        self.bottom_y = 0.0
        self.is_active = True
        self.age = 0.0

    def update(self, dt, target_y):
        self.age += dt
        # Shift segments upward
        for seg in self.segments:
            seg['y'] -= self.speed * dt
            seg['alpha'] = max(0.0, seg['alpha'] - dt * 0.45)

        self.segments = [s for s in self.segments if s['y'] > -50 and s['alpha'] > 0.02]

    def add_segment(self, y, height, alpha=0.85):
        self.segments.append({'y': y, 'h': height, 'alpha': alpha})


class FloatingText:
    """Floating feedback text for scores: PERFECT, GOOD, MISS."""
    def __init__(self, text, x, y, color=(255, 255, 255), life=0.85):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.life -= dt
        self.y -= 35 * dt

    def is_alive(self):
        return self.life > 0


class VisualsEngine:
    """Renders the game's dynamic backgrounds, falling notes, trails, and FX."""
    def __init__(self, screen_w, screen_h):
        self.w = screen_w
        self.h = screen_h
        self.theme_name = 'Neon Twilight'
        self.theme = COLOR_THEMES[self.theme_name]
        self.note_speed = 340.0       # Pixels per second falling speed
        self.show_trails = True
        self.hit_line_y = screen_h - 170

        # Background Stars & Motes
        self.stars = []
        self._init_stars(90)
        self.motes = []
        self._init_motes(35)

        # Particle FX
        self.particles = []
        self.rising_trails = {}  # pitch -> RisingNoteTrail
        self.floating_texts = []
        self.aura_energy = 0.0  # Pulsing reactivity

        self.font_score = None
        self._init_fonts()

    def _init_fonts(self):
        try:
            self.font_score = pygame.font.SysFont("Segoe UI", 18, bold=True)
        except Exception:
            self.font_score = pygame.font.Font(None, 20)

    def set_theme(self, theme_name):
        if theme_name in COLOR_THEMES:
            self.theme_name = theme_name
            self.theme = COLOR_THEMES[theme_name]

    def set_dimensions(self, w, h, hit_line_y):
        self.w = w
        self.h = h
        self.hit_line_y = hit_line_y

    def _init_stars(self, count):
        self.stars.clear()
        for _ in range(count):
            self.stars.append({
                'x': random.uniform(0, self.w),
                'y': random.uniform(0, self.h * 0.75),
                'size': random.uniform(1.0, 2.5),
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.8, 2.2)
            })

    def _init_motes(self, count):
        self.motes.clear()
        for _ in range(count):
            self.motes.append({
                'x': random.uniform(0, self.w),
                'y': random.uniform(0, self.h * 0.8),
                'vx': random.uniform(-12, 12),
                'vy': random.uniform(-18, -4),
                'size': random.uniform(2.0, 4.5),
                'alpha': random.uniform(0.3, 0.8)
            })

    def trigger_key_burst(self, x, y, hand='right', velocity=100, pitch=None, key_width=20):
        """Spawns sparkling particles when a key is struck. In Free Play, also starts a rising trail."""
        color = self.theme['right_hand'] if hand == 'right' else self.theme['left_hand']
        core_col = self.theme['right_hand_core'] if hand == 'right' else self.theme['left_hand_core']
        
        # Audio reactive pulse
        self.aura_energy = min(1.0, self.aura_energy + (velocity / 120.0) * 0.4)

        num_sparks = int(8 + (velocity / 127.0) * 16)
        for _ in range(num_sparks):
            ang = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            spd = random.uniform(80, 280) * (velocity / 100.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            part_col = core_col if random.random() < 0.4 else color
            life = random.uniform(0.35, 0.75)
            size = random.uniform(2.0, 4.0)
            self.particles.append(Particle(x, y - 4, vx, vy, part_col, life, size, gravity=320.0))

        # Rising trail: start or extend a trail for this pitch
        if pitch is not None:
            if pitch not in self.rising_trails:
                self.rising_trails[pitch] = RisingNoteTrail(
                    x=x, width=max(10, key_width - 2), color=color, speed=160.0
                )
            trail = self.rising_trails[pitch]
            trail.bottom_y = float(y)
            trail.is_active = True

    def stop_key_trail(self, pitch):
        """Marks a trail as inactive (note released) so it fades out."""
        if pitch in self.rising_trails:
            self.rising_trails[pitch].is_active = False

    def add_floating_text(self, text, x, y, grade='perfect'):
        colors = {
            'perfect': (80, 255, 160),
            'good': (255, 220, 60),
            'miss': (255, 70, 90)
        }
        col = colors.get(grade, (255, 255, 255))
        self.floating_texts.append(FloatingText(text, x, y, col))

    def update(self, dt):
        # Update aura reactivity
        if self.aura_energy > 0:
            self.aura_energy = max(0.0, self.aura_energy - dt * 1.8)

        # Update motes
        for m in self.motes:
            m['x'] = (m['x'] + m['vx'] * dt) % self.w
            m['y'] = m['y'] + m['vy'] * dt
            if m['y'] < 0:
                m['y'] = self.hit_line_y
                m['x'] = random.uniform(0, self.w)

        # Update particles
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.is_alive()]

        # Update rising trails: active ones grow upward, inactive ones fade
        dead_pitches = []
        for pitch, trail in self.rising_trails.items():
            if trail.is_active:
                # Add a new segment at the bottom (piano top) each frame
                seg_h = trail.speed * dt + 2
                trail.add_segment(trail.bottom_y, seg_h, alpha=0.82)
            trail.update(dt, 0)
            if not trail.segments and not trail.is_active:
                dead_pitches.append(pitch)
        for pitch in dead_pitches:
            del self.rising_trails[pitch]

        # Update floating texts
        for ft in self.floating_texts:
            ft.update(dt)
        self.floating_texts = [ft for ft in self.floating_texts if ft.is_alive()]

    def draw_background(self, surface):
        """Draws reactive sky gradient, starfield, and floating motes."""
        # Reactive background color shift
        top_c = self.theme['bg_top']
        bot_c = self.theme['bg_bottom']
        
        # Audio aura shift
        if self.aura_energy > 0:
            glow = self.theme['right_hand']
            r = min(255, int(bot_c[0] + glow[0] * self.aura_energy * 0.15))
            g = min(255, int(bot_c[1] + glow[1] * self.aura_energy * 0.15))
            b = min(255, int(bot_c[2] + glow[2] * self.aura_energy * 0.15))
            bot_c = (r, g, b)

        # Draw smooth vertical background gradient
        grad_surf = pygame.Surface((1, self.h))
        for y in range(self.h):
            ratio = y / float(self.h)
            col = (
                int(top_c[0] + (bot_c[0] - top_c[0]) * ratio),
                int(top_c[1] + (bot_c[1] - top_c[1]) * ratio),
                int(top_c[2] + (bot_c[2] - top_c[2]) * ratio)
            )
            grad_surf.set_at((0, y), col)
        pygame.transform.scale(grad_surf, (self.w, self.h), surface)

        # Twinkling stars
        ticks = pygame.time.get_ticks() / 1000.0
        star_col = self.theme['star']
        for s in self.stars:
            twinkle = 0.5 + 0.5 * math.sin(ticks * s['speed'] + s['phase'])
            col = (
                int(star_col[0] * twinkle),
                int(star_col[1] * twinkle),
                int(star_col[2] * twinkle)
            )
            pygame.draw.circle(surface, col, (int(s['x']), int(s['y'])), max(1, int(s['size'])))

        # Ambient floating motes
        for m in self.motes:
            alpha = int(m['alpha'] * 180)
            mote_surf = pygame.Surface((int(m['size']*2), int(m['size']*2)), pygame.SRCALPHA)
            pygame.draw.circle(mote_surf, (*self.theme['right_hand'], alpha), (int(m['size']), int(m['size'])), int(m['size']))
            surface.blit(mote_surf, (int(m['x']), int(m['y'])))

        # Hit line / target bar right above keyboard
        target_col = (110, 130, 160)
        glow_alpha = int(80 + self.aura_energy * 140)
        line_surf = pygame.Surface((self.w, 4), pygame.SRCALPHA)
        line_surf.fill((*self.theme['accent'], glow_alpha))
        surface.blit(line_surf, (0, int(self.hit_line_y - 2)))
        pygame.draw.line(surface, target_col, (0, self.hit_line_y), (self.w, self.hit_line_y), 2)

    def draw_falling_notes(self, surface, song, song_time, keyboard):
        """Draws falling note blocks with high precision timing and vibrant colors."""
        if not song:
            return

        visible_window_sec = (self.hit_line_y + 100) / self.note_speed

        for note in song.notes:
            # Check if note is currently in visible time window
            dt_start = note.start_time - song_time
            dt_end = note.end_time - song_time

            if dt_start > visible_window_sec:
                # Far in the future
                continue
            if dt_end < -0.3:
                # Already passed
                continue

            # Calculate screen Y coordinates
            y_hit = self.hit_line_y
            y_bottom = y_hit - (dt_start * self.note_speed)
            y_top = y_hit - (dt_end * self.note_speed)

            # Ensure minimum height
            h = max(10, y_bottom - y_top)
            y = y_bottom - h

            # Get horizontal position from piano keyboard
            center_x = keyboard.get_key_x_center(note.pitch)
            width = max(12, keyboard.get_key_width(note.pitch) - 3)
            x = center_x - (width // 2)

            # Pick color by hand
            is_right = (note.hand == 'right')
            base_color = self.theme['right_hand'] if is_right else self.theme['left_hand']
            core_color = self.theme['right_hand_core'] if is_right else self.theme['left_hand_core']

            # Fade note out if already hit
            alpha = 90 if note.hit else 240
            note_rect = pygame.Rect(int(x), int(y), int(width), int(h))

            # Draw outer glow / block
            note_surf = pygame.Surface((note_rect.width, note_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(note_surf, (*base_color, alpha), (0, 0, note_rect.width, note_rect.height), border_radius=4)
            # Inner bright core
            core_w = max(4, note_rect.width - 6)
            core_rect = pygame.Rect(3, 2, core_w, max(4, note_rect.height - 4))
            pygame.draw.rect(note_surf, (*core_color, int(alpha * 0.75)), core_rect, border_radius=3)

            # Border stroke
            pygame.draw.rect(note_surf, (255, 255, 255, int(alpha * 0.9)), (0, 0, note_rect.width, note_rect.height), 1, border_radius=4)
            surface.blit(note_surf, note_rect)

    def draw_fx(self, surface):
        """Draws rising note trails, spark particles and floating score feedback."""
        # Rising note trails (Free Play steam rising from piano keys)
        for pitch, trail in list(self.rising_trails.items()):
            if not trail.segments:
                continue
            color = trail.color
            half_w = trail.width // 2
            cx = int(trail.x)
            for seg in trail.segments:
                alpha = max(0, min(255, int(seg['alpha'] * 220)))
                seg_h = max(2, int(seg['h']))
                # Draw glowing column rising upward
                seg_surf = pygame.Surface((trail.width + 8, seg_h + 4), pygame.SRCALPHA)
                # Soft outer glow
                pygame.draw.rect(seg_surf, (*color, alpha // 3), (0, 0, trail.width + 8, seg_h + 4), border_radius=4)
                # Bright inner ribbon
                pygame.draw.rect(seg_surf, (*color, alpha), (4, 2, trail.width, seg_h), border_radius=3)
                # Bright core center line
                core_alpha = min(255, int(alpha * 1.4))
                pygame.draw.rect(seg_surf, (255, 255, 255, core_alpha // 3), (trail.width // 2, 2, max(2, trail.width // 4), seg_h), border_radius=2)
                surface.blit(seg_surf, (cx - half_w - 4, int(seg['y']) - seg_h // 2))

        # Particles
        for p in self.particles:
            alpha = max(0, min(255, int((p.life / p.max_life) * 255)))
            p_surf = pygame.Surface((int(p.size*2), int(p.size*2)), pygame.SRCALPHA)
            pygame.draw.circle(p_surf, (*p.color, alpha), (int(p.size), int(p.size)), int(p.size))
            surface.blit(p_surf, (int(p.x - p.size), int(p.y - p.size)))

        # Floating score texts
        if self.font_score:
            for ft in self.floating_texts:
                alpha = max(0, min(255, int((ft.life / ft.max_life) * 255)))
                txt_surf = self.font_score.render(ft.text, True, ft.color)
                txt_surf.set_alpha(alpha)
                surface.blit(txt_surf, (int(ft.x - txt_surf.get_width() // 2), int(ft.y)))
