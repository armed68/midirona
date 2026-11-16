
import pygame


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SOLFEGE_NAMES = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
BLACK_KEY_INDICES = {1, 3, 6, 8, 10}


PC_KEY_MAP = {
    
    pygame.K_z: (0, 0),   
    pygame.K_s: (0, 1),   
    pygame.K_x: (0, 2),   
    pygame.K_d: (0, 3),   
    pygame.K_c: (0, 4),   
    pygame.K_v: (0, 5),   
    pygame.K_g: (0, 6),   
    pygame.K_b: (0, 7),   
    pygame.K_h: (0, 8),   
    pygame.K_n: (0, 9),   
    pygame.K_j: (0, 10),  
    pygame.K_m: (0, 11),  
    
    
    pygame.K_q: (1, 0),   
    pygame.K_2: (1, 1),   
    pygame.K_w: (1, 2),   
    pygame.K_3: (1, 3),   
    pygame.K_e: (1, 4),   
    pygame.K_r: (1, 5),   
    pygame.K_5: (1, 6),   
    pygame.K_t: (1, 7),   
    pygame.K_6: (1, 8),   
    pygame.K_y: (1, 9),   
    pygame.K_7: (1, 10),  
    pygame.K_u: (1, 11),  
    pygame.K_i: (2, 0),   
    pygame.K_9: (2, 1),   
    pygame.K_o: (2, 2),   
    pygame.K_0: (2, 3),   
    pygame.K_p: (2, 4),   
}

PC_KEY_LABELS = {
    pygame.K_z: 'Z', pygame.K_s: 'S', pygame.K_x: 'X', pygame.K_d: 'D',
    pygame.K_c: 'C', pygame.K_v: 'V', pygame.K_g: 'G', pygame.K_b: 'B',
    pygame.K_h: 'H', pygame.K_n: 'N', pygame.K_j: 'J', pygame.K_m: 'M',
    pygame.K_q: 'Q', pygame.K_2: '2', pygame.K_w: 'W', pygame.K_3: '3',
    pygame.K_e: 'E', pygame.K_r: 'R', pygame.K_5: '5', pygame.K_t: 'T',
    pygame.K_6: '6', pygame.K_y: 'Y', pygame.K_7: '7', pygame.K_u: 'U',
    pygame.K_i: 'I', pygame.K_9: '9', pygame.K_o: 'O', pygame.K_0: '0',
    pygame.K_p: 'P'
}

def is_black_key(pitch):
    return (pitch % 12) in BLACK_KEY_INDICES

def get_note_label(pitch, mode='notes'):
    semitone = pitch % 12
    octave = (pitch // 12) - 1
    if mode == 'notes':
        return f"{NOTE_NAMES[semitone]}{octave}"
    elif mode == 'solfege':
        return f"{SOLFEGE_NAMES[semitone]}"
    return ""


class PianoKey:
    def __init__(self, pitch):
        self.pitch = pitch
        self.is_black = is_black_key(pitch)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pressed = False
        self.velocity = 0
        self.expected = False          
        self.expected_hand = 'right'
        self.flash_timer = 0.0         
        self.flash_color = None
        self.mapped_pc_key = None

    def update(self, dt):
        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - dt)
            if self.flash_timer <= 0:
                self.flash_color = None


class PianoKeyboard:
    def __init__(self, rect, min_pitch=36, max_pitch=96):
        self.rect = pygame.Rect(rect)
        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.base_octave = 4  
        self.label_mode = 'notes'  
        self.range_mode = '61'     

        self.keys = {}
        self.mouse_pressed_key = None
        self.font = None
        self.font_small = None

        self._init_fonts()
        self.rebuild_keys()

    def _init_fonts(self):
        try:
            self.font = pygame.font.SysFont("Segoe UI", 12, bold=True)
            self.font_small = pygame.font.SysFont("Segoe UI", 10, bold=True)
        except Exception:
            self.font = pygame.font.Font(None, 14)
            self.font_small = pygame.font.Font(None, 12)

    def set_range_preset(self, preset):
        self.range_mode = str(preset).lower()
        if self.range_mode == '25':
            self.min_pitch, self.max_pitch = 48, 72  
        elif self.range_mode == '49':
            self.min_pitch, self.max_pitch = 36, 84  
        elif self.range_mode == '61':
            self.min_pitch, self.max_pitch = 36, 96  
        elif self.range_mode == '88':
            self.min_pitch, self.max_pitch = 21, 108 
        self.rebuild_keys()

    def auto_fit_range(self, song):
        if self.range_mode == 'auto' and song:
            
            self.min_pitch = max(21, (song.min_key // 12) * 12)
            self.max_pitch = min(108, ((song.max_key + 11) // 12) * 12)
            self.rebuild_keys()

    def shift_octave(self, delta):
        new_oct = max(1, min(7, self.base_octave + delta))
        if new_oct != self.base_octave:
            self.base_octave = new_oct
            self._update_pc_key_bindings()

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)
        self.rebuild_keys()

    def rebuild_keys(self):
        self.keys.clear()
        all_pitches = list(range(self.min_pitch, self.max_pitch + 1))
        white_pitches = [p for p in all_pitches if not is_black_key(p)]

        if not white_pitches:
            return

        total_white = len(white_pitches)
        white_w = self.rect.width / total_white
        white_h = self.rect.height
        black_w = white_w * 0.62
        black_h = white_h * 0.64

        white_idx = 0
        white_positions = {}

        
        for p in all_pitches:
            key = PianoKey(p)
            self.keys[p] = key
            if not key.is_black:
                kx = self.rect.x + (white_idx * white_w)
                key.rect = pygame.Rect(int(kx), int(self.rect.y), int(white_w) + 1, int(white_h))
                white_positions[p] = kx
                white_idx += 1

        
        for p in all_pitches:
            key = self.keys[p]
            if key.is_black:
                
                prev_white_p = p - 1
                if prev_white_p in white_positions:
                    px = white_positions[prev_white_p]
                    bx = px + white_w - (black_w / 2.0)
                    key.rect = pygame.Rect(int(bx), int(self.rect.y), int(black_w), int(black_h))
                else:
                    key.rect = pygame.Rect(self.rect.x, self.rect.y, int(black_w), int(black_h))

        self._update_pc_key_bindings()

    def _update_pc_key_bindings(self):
        
        for k in self.keys.values():
            k.mapped_pc_key = None

        base_midi = self.base_octave * 12
        for code, (oct_offset, semi) in PC_KEY_MAP.items():
            target_pitch = base_midi + (oct_offset * 12) + semi
            if target_pitch in self.keys:
                self.keys[target_pitch].mapped_pc_key = PC_KEY_LABELS.get(code, '')

    def get_pitch_at_pos(self, pos):
        x, y = pos
        if not self.rect.collidepoint(x, y):
            return None

        
        for p, key in self.keys.items():
            if key.is_black and key.rect.collidepoint(x, y):
                return p

        
        for p, key in self.keys.items():
            if not key.is_black and key.rect.collidepoint(x, y):
                return p

        return None

    def get_key_x_center(self, pitch):
        key = self.keys.get(pitch)
        if key:
            return key.rect.centerx
        
        return self.rect.centerx

    def get_key_width(self, pitch):
        key = self.keys.get(pitch)
        if key:
            return key.rect.width
        return 16

    def set_key_pressed(self, pitch, pressed, velocity=100):
        key = self.keys.get(pitch)
        if key:
            key.pressed = pressed
            key.velocity = velocity if pressed else 0

    def trigger_flash(self, pitch, color=(100, 255, 120), duration=0.25):
        key = self.keys.get(pitch)
        if key:
            key.flash_timer = duration
            key.flash_color = color

    def clear_expected(self):
        for k in self.keys.values():
            k.expected = False

    def set_expected(self, pitch, expected=True, hand='right'):
        key = self.keys.get(pitch)
        if key:
            key.expected = expected
            key.expected_hand = hand

    def update(self, dt):
        for k in self.keys.values():
            k.update(dt)

    def draw(self, surface):
        
        casing_rect = pygame.Rect(self.rect.x - 4, self.rect.y - 6, self.rect.width + 8, self.rect.height + 12)
        pygame.draw.rect(surface, (20, 22, 28), casing_rect, border_radius=6)
        pygame.draw.rect(surface, (45, 50, 62), casing_rect, 2, border_radius=6)

        
        felt_rect = pygame.Rect(self.rect.x, self.rect.y - 4, self.rect.width, 4)
        pygame.draw.rect(surface, (180, 30, 45), felt_rect)

        
        for p, key in self.keys.items():
            if not key.is_black:
                self._draw_white_key(surface, key)

        
        for p, key in self.keys.items():
            if key.is_black:
                self._draw_black_key(surface, key)

    def _draw_white_key(self, surface, key):
        r = key.rect
        
        if key.flash_color:
            base_col = key.flash_color
        elif key.pressed:
            
            glow_intensity = min(1.0, key.velocity / 100.0)
            base_col = (
                int(160 + 50 * glow_intensity),
                int(220 + 35 * glow_intensity),
                int(250)
            )
        elif key.expected:
            
            base_col = (190, 240, 255) if key.expected_hand == 'right' else (255, 235, 185)
        else:
            base_col = (248, 248, 250)

        
        pygame.draw.rect(surface, base_col, r)

        
        if key.pressed:
            
            pygame.draw.rect(surface, (120, 150, 180), r, 2)
            pygame.draw.line(surface, (100, 130, 160), (r.left, r.top), (r.right, r.top), 3)
        else:
            
            bottom_lip = pygame.Rect(r.left, r.bottom - 6, r.width, 6)
            pygame.draw.rect(surface, (215, 218, 225), bottom_lip)
            
            pygame.draw.line(surface, (80, 85, 95), (r.right - 1, r.top), (r.right - 1, r.bottom), 1)

        
        self._draw_label(surface, key, is_black=False)

    def _draw_black_key(self, surface, key):
        r = key.rect
        if key.flash_color:
            base_col = key.flash_color
        elif key.pressed:
            base_col = (70, 180, 240) if key.velocity > 70 else (50, 140, 200)
        elif key.expected:
            base_col = (80, 180, 230) if key.expected_hand == 'right' else (230, 175, 70)
        else:
            base_col = (28, 30, 36)

        
        pygame.draw.rect(surface, base_col, r, border_bottom_left_radius=3, border_bottom_right_radius=3)

        if not key.pressed and not key.flash_color:
            
            gloss_rect = pygame.Rect(r.left + 2, r.top, r.width - 4, r.height - 8)
            pygame.draw.rect(surface, (48, 52, 60), gloss_rect, border_bottom_left_radius=2, border_bottom_right_radius=2)
            pygame.draw.line(surface, (70, 75, 88), (r.left + 2, r.top), (r.right - 3, r.top), 1)

        
        pygame.draw.rect(surface, (10, 12, 16), r, 1, border_bottom_left_radius=3, border_bottom_right_radius=3)

        
        self._draw_label(surface, key, is_black=True)

    def _draw_label(self, surface, key, is_black):
        if self.label_mode == 'none':
            return

        text = ""
        if self.label_mode == 'keys' and key.mapped_pc_key:
            text = key.mapped_pc_key
        elif self.label_mode in ('notes', 'solfege'):
            text = get_note_label(key.pitch, self.label_mode)
            
            if key.rect.width < 18 and not is_black and (key.pitch % 12 != 0):
                return
            if is_black and key.rect.width < 14:
                return

        if not text or not self.font:
            return

        font_to_use = self.font_small if (key.rect.width < 22 or is_black) else self.font
        text_color = (220, 225, 235) if is_black else (70, 75, 88)
        if key.pressed:
            text_color = (15, 20, 30)

        lbl = font_to_use.render(text, True, text_color)
        lx = key.rect.centerx - (lbl.get_width() // 2)
        ly = key.rect.bottom - lbl.get_height() - (4 if is_black else 8)
        surface.blit(lbl, (lx, ly))
