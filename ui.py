"""
Midirona - User Interface & Modal Panels
Includes:
- Top Navigation Bar (Game Mode, Song Title, SoundFont, MIDI Status)
- Bottom Timeline & Playback Controller (Play/Pause, Seekbar, Speed)
- Interactive Modals (SoundFont Selector, Song Library, MIDI Devices, Settings, Help)
"""

import os
import pygame
from sf2_engine import clean_text

class Button:
    def __init__(self, rect, text, callback=None, color=(40, 44, 56), hover_color=(60, 68, 86), text_color=(230, 235, 245)):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True
        return False

    def draw(self, surface, font):
        bg = (36, 72, 91) if self.active else ((43, 55, 70) if self.is_hovered else (28, 34, 45))
        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, (52, 72, 88), self.rect, 1, border_radius=8)

        txt_surf = font.render(clean_text(self.text, 200), True, (119, 231, 241) if self.active else self.text_color)
        tx = self.rect.centerx - (txt_surf.get_width() // 2)
        ty = self.rect.centery - (txt_surf.get_height() // 2)
        surface.blit(txt_surf, (tx, ty))


class UIManager:
    """Manages all HUD buttons, top bar, modals, and user dialogs."""
    def __init__(self, screen_w, screen_h, mode_mgr, synth, midi_mgr, visuals, keyboard):
        self.w = screen_w
        self.h = screen_h
        self.mode_mgr = mode_mgr
        self.synth = synth
        self.midi_mgr = midi_mgr
        self.visuals = visuals
        self.keyboard = keyboard

        self.active_modal = None  # None, 'soundfonts', 'songs', 'midi', 'settings', 'help', 'modes'
        self.available_sf2_files = []
        self.sf_error = None   # last failed SoundFont load (shown in the SoundFont window)
        self.refresh_sf2_list()

        # Scroll offsets for lists
        self.sf2_scroll = 0        # scroll index for SF2 file list
        self.preset_scroll = 0     # scroll index for preset list
        self.song_scroll = 0       # scroll index for song list

        self.font = None
        self.font_bold = None
        self.font_small = None
        self.font_title = None
        self._init_fonts()

        self._preset_prev_rect = None
        self._preset_next_rect = None
        self._reverb_dragging = False

        self._build_header_buttons()

    def _init_fonts(self):
        try:
            self.font = pygame.font.SysFont("Segoe UI", 13)
            self.font_bold = pygame.font.SysFont("Segoe UI", 13, bold=True)
            self.font_small = pygame.font.SysFont("Segoe UI", 11)
            self.font_title = pygame.font.SysFont("Segoe UI", 16, bold=True)
        except Exception:
            self.font = pygame.font.Font(None, 16)
            self.font_bold = pygame.font.Font(None, 16)
            self.font_small = pygame.font.Font(None, 14)
            self.font_title = pygame.font.Font(None, 20)

    def refresh_sf2_list(self):
        self.available_sf2_files.clear()
        sf_dir = "soundfonts"
        if os.path.exists(sf_dir):
            for f in sorted(os.listdir(sf_dir)):
                if f.lower().endswith('.sf2'):
                    self.available_sf2_files.append((f, os.path.join(sf_dir, f)))

    def _is_sf2_active(self, fname):
        """Check if this sf2 filename matches the currently loaded one."""
        return (fname in self.synth.active_sf2_name or self.synth.active_sf2_name in fname or
                os.path.splitext(fname)[0].replace('_', ' ') in self.synth.active_sf2_name)

    def _build_header_buttons(self):
        x = 130
        def mk(w, text, cb):
            nonlocal x
            btn = Button((x, 8, w, 28), text, cb)
            x += w + 6
            return btn
        mode_b = mk(120, "Mode: Free", lambda: self.open_modal('modes'))
        song_b = mk(140, "Song: Für Elise", lambda: self.open_modal('songs'))
        sf_b = mk(220, "SoundFont: Grand", lambda: self.open_modal('soundfonts'))
        x += 44  # room for the preset < > arrows
        midi_b = mk(120, "MIDI Device", lambda: self.open_modal('midi'))
        self.header_buttons = [
            mode_b, song_b, sf_b, midi_b,
            Button((self.w - 135, 8, 70, 28), "Settings", lambda: self.open_modal('settings')),
            Button((self.w - 60, 8, 50, 28), "Help", lambda: self.open_modal('help')),
        ]

    def set_dimensions(self, w, h):
        self.w = w
        self.h = h
        self._build_header_buttons()

    def open_modal(self, modal_name):
        if self.active_modal == modal_name:
            self.active_modal = None
        else:
            self.active_modal = modal_name
            # Reset scroll on open
            self.sf2_scroll = 0
            self.preset_scroll = 0
            self.song_scroll = 0
            if modal_name == 'soundfonts':
                self.refresh_sf2_list()
                self.sf_error = None
                self._ensure_preset_visible(center=True)
            elif modal_name == 'midi':
                self.midi_mgr.refresh_devices()
            elif modal_name == 'songs':
                lib = self.mode_mgr.song_library
                lib.rescan()
                self.song_scroll = max(0, lib.current_idx - 3)
                self._clamp_scrolls()

    def close_modal(self):
        self.active_modal = None

    def handle_event(self, event):
        if self._reverb_dragging and event.type == pygame.MOUSEMOTION:
            self._set_reverb_from_pos(event.pos)
            return True
        if self._reverb_dragging and event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._set_reverb_from_pos(event.pos)
            self._reverb_dragging = False
            return True

        # Close modal on ESC
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.active_modal:
                self.close_modal()
                return True

        # Mouse wheel scrolls lists inside modals
        if event.type == pygame.MOUSEWHEEL and self.active_modal:
            self._scroll_modal(-event.y * 3, pygame.mouse.get_pos())
            return True

        # Up/Down/PageUp/PageDown change instrument while the SoundFont window is open
        if event.type == pygame.KEYDOWN and self.active_modal == 'soundfonts':
            step = {pygame.K_UP: -1, pygame.K_DOWN: 1, pygame.K_PAGEUP: -8, pygame.K_PAGEDOWN: 8}.get(event.key)
            if step:
                self._step_preset(step)
                return True

        # If modal is open, modal intercepts clicks
        if self.active_modal:
            if self._handle_modal_click(event):
                return True

        # Header buttons
        for btn in self.header_buttons:
            if btn.handle_event(event):
                return True

        # Preset prev/next arrow buttons (< >) next to SF2 button
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if getattr(self, '_preset_prev_rect', None) and self._preset_prev_rect.collidepoint(event.pos):
                self._step_preset(-1)
                return True
            if getattr(self, '_preset_next_rect', None) and self._preset_next_rect.collidepoint(event.pos):
                self._step_preset(1)
                return True

        # Timeline and playback buttons (space bar for play/pause, left/right for seek)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.mode_mgr.toggle_play_pause()
                return True
            elif event.key == pygame.K_r:
                self.mode_mgr.reset_song()
                return True
            elif event.key == pygame.K_LEFT:
                self.mode_mgr.seek_time(self.mode_mgr.song_time - 3.0)
                return True
            elif event.key == pygame.K_RIGHT:
                self.mode_mgr.seek_time(self.mode_mgr.song_time + 3.0)
                return True
            elif event.key == pygame.K_TAB:
                # Quick switch next soundfont
                self._cycle_next_soundfont()
                return True
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_COMMA):
                self.keyboard.shift_octave(-1)
                return True
            elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_PERIOD):
                self.keyboard.shift_octave(1)
                return True

        # Mouse click on timeline seekbar
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            timeline_rect = pygame.Rect(178, self.h - 34, max(180, self.w - 510), 18)
            if timeline_rect.collidepoint(event.pos):
                if self.mode_mgr.current_song and self.mode_mgr.current_song.duration > 0:
                    ratio = (event.pos[0] - timeline_rect.x) / float(timeline_rect.width)
                    self.mode_mgr.seek_time(ratio * self.mode_mgr.current_song.duration)
                return True

            # Play/pause button bottom left
            play_btn_rect = pygame.Rect(20, self.h - 39, 68, 28)
            if play_btn_rect.collidepoint(event.pos):
                self.mode_mgr.toggle_play_pause()
                return True

            # Reset button
            reset_btn_rect = pygame.Rect(96, self.h - 39, 58, 28)
            if reset_btn_rect.collidepoint(event.pos):
                self.mode_mgr.reset_song()
                return True

        return False

    def _cycle_next_soundfont(self):
        if not self.available_sf2_files:
            return
        cur_path = getattr(self.synth, 'active_sf2_path', None)
        cur = -1
        for i, (fname, fpath) in enumerate(self.available_sf2_files):
            if cur_path and os.path.normpath(fpath) == os.path.normpath(cur_path):
                cur = i
                break
        # Try the following files in order; skip any that fail to load
        n = len(self.available_sf2_files)
        for step in range(1, n + 1):
            _, next_path = self.available_sf2_files[(cur + step) % n]
            if self.synth.load_sf2(next_path):
                self.sf_error = None
                break
            self.sf_error = f"{os.path.basename(next_path)}: {self.synth.last_error or 'could not be loaded'}"

    # -------------------------------------------------------------------------
    # Modal geometry & layout (shared by drawing AND click handling, so they never drift apart)
    # -------------------------------------------------------------------------
    MODAL_SIZES = {
        'modes': (520, 390),
        'songs': (560, 460),
        'midi': (520, 400),
        'settings': (520, 390),
        'help': (680, 420),
        'soundfonts': (800, 580),
    }
    MODES_LIST = [
        ("Free Play", "Improvise with MIDI controller, note trails & reactive particles"),
        ("Practice", "Synthesia-style: Song pauses and waits for you to hit correct notes"),
        ("Rhythm Game", "Hit falling notes on beat for Score, Combos, and Ranks"),
        ("Listen / Autoplay", "Sit back and watch falling notes with active SoundFont"),
        ("Melody Echo", "Listen to short melodies and echo them back (Ear Training)"),
    ]
    THEMES = ['Neon Twilight', 'Sakura Dream', 'Emerald Grove', 'Midnight Ocean']
    RANGES = [('25', '25 Keys'), ('49', '49 Keys'), ('61', '61 Keys'), ('88', '88 Keys'), ('auto', 'Auto-Fit')]
    LABELS = [('notes', 'Notes (C4)'), ('solfege', 'Do Re Mi'), ('keys', 'PC Keys'), ('none', 'None')]

    SF_ROW_H = 30      # preset row pitch (row rect is 26 high)
    SF_FILE_H = 34     # file row pitch (row rect is 30 high)
    SONG_ROW_H = 38    # song row pitch (row rect is 34 high)

    def _modal_rect(self, name=None):
        name = name or self.active_modal
        bw, bh = self.MODAL_SIZES.get(name, (520, 390))
        bw = min(bw, self.w - 30)
        bh = min(bh, self.h - 40)
        return pygame.Rect((self.w - bw) // 2, (self.h - bh) // 2, bw, bh)

    def _fit(self, text, font, max_w):
        """Sanitizes text (NULs crash pygame's renderer) and trims it with an ellipsis to fit max_w pixels."""
        text = clean_text(text, 200)
        if font.size(text)[0] <= max_w:
            return text
        while len(text) > 1 and font.size(text + "…")[0] > max_w:
            text = text[:-1]
        return text + "…"

    @staticmethod
    def _rows_fit(area_h, pitch, row_h):
        return max(1, (area_h + (pitch - row_h)) // pitch)

    def _sf_areas(self, m):
        """Geometry of the SoundFont modal: file column (left) and instrument column (right)."""
        top = m.y + 104
        h = m.bottom - 16 - top
        left = pygame.Rect(m.x + 16, top, 250, h)
        right_x = left.right + 24
        right = pygame.Rect(right_x, top, m.right - 24 - right_x, h)
        return {
            'left': left, 'right': right,
            'rows_left': self._rows_fit(h, self.SF_FILE_H, 30),
            'rows_right': self._rows_fit(h, self.SF_ROW_H, 26),
        }

    def _song_area(self, m):
        top = m.y + 88
        area = pygame.Rect(m.x + 20, top, m.w - 52, m.bottom - 16 - top)
        return area, self._rows_fit(area.h, self.SONG_ROW_H, 34)

    def _clamp_scrolls(self):
        if self.active_modal == 'soundfonts':
            a = self._sf_areas(self._modal_rect())
            n_pre = len(self.synth.parser.presets) if self.synth.parser else 0
            self.preset_scroll = max(0, min(self.preset_scroll, max(0, n_pre - a['rows_right'])))
            self.sf2_scroll = max(0, min(self.sf2_scroll, max(0, len(self.available_sf2_files) - a['rows_left'])))
        elif self.active_modal == 'songs':
            _, rows = self._song_area(self._modal_rect())
            n = len(self.mode_mgr.song_library.songs_list)
            self.song_scroll = max(0, min(self.song_scroll, max(0, n - rows)))

    def _ensure_preset_visible(self, center=False):
        if self.active_modal != 'soundfonts' or not self.synth.parser:
            return
        rows = self._sf_areas(self._modal_rect())['rows_right']
        idx = self.synth.preset_idx
        if center:
            self.preset_scroll = idx - rows // 2
        elif idx < self.preset_scroll:
            self.preset_scroll = idx
        elif idx >= self.preset_scroll + rows:
            self.preset_scroll = idx - rows + 1
        self._clamp_scrolls()

    def _step_preset(self, delta):
        if self.synth.parser and self.synth.parser.presets:
            n = len(self.synth.parser.presets)
            self.synth.set_preset((self.synth.preset_idx + delta) % n)
            self._ensure_preset_visible()

    def _scroll_modal(self, rows, mouse_pos):
        if self.active_modal == 'soundfonts':
            a = self._sf_areas(self._modal_rect())
            if mouse_pos[0] < a['left'].right + 12:
                self.sf2_scroll += rows
            else:
                self.preset_scroll += rows
        elif self.active_modal == 'songs':
            self.song_scroll += rows
        self._clamp_scrolls()

    def _draw_scrollbar(self, surface, area, total, visible, scroll):
        if total <= visible:
            return
        track = pygame.Rect(area.right + 5, area.y, 5, area.h)
        pygame.draw.rect(surface, (34, 38, 50), track, border_radius=3)
        th = max(24, int(track.h * visible / total))
        max_scroll = total - visible
        ty = track.y + int((track.h - th) * (scroll / max_scroll if max_scroll else 0))
        pygame.draw.rect(surface, (0, 190, 235), (track.x, ty, track.w, th), border_radius=3)

    def _sf_file_rows(self, m):
        a = self._sf_areas(m)
        out = []
        for k in range(a['rows_left']):
            i = self.sf2_scroll + k
            if i >= len(self.available_sf2_files):
                break
            fname, fpath = self.available_sf2_files[i]
            out.append((pygame.Rect(a['left'].x, a['left'].y + k * self.SF_FILE_H, a['left'].w, 30), i, fname, fpath))
        return out

    def _sf_preset_rows(self, m):
        a = self._sf_areas(m)
        out = []
        if not self.synth.parser:
            return out
        presets = self.synth.parser.presets
        for k in range(a['rows_right']):
            j = self.preset_scroll + k
            if j >= len(presets):
                break
            out.append((pygame.Rect(a['right'].x, a['right'].y + k * self.SF_ROW_H, a['right'].w, 26), j, presets[j]))
        return out

    def _song_rows(self, m):
        area, rows = self._song_area(m)
        out = []
        songs = self.mode_mgr.song_library.songs_list
        for k in range(rows):
            i = self.song_scroll + k
            if i >= len(songs):
                break
            out.append((pygame.Rect(area.x, area.y + k * self.SONG_ROW_H, area.w, 34), i, songs[i]))
        return out

    def _mode_rows(self, m):
        return [(pygame.Rect(m.x + 20, m.y + 58 + i * 56, m.w - 40, 50), n, d) for i, (n, d) in enumerate(self.MODES_LIST)]

    def _midi_rows(self, m):
        visible = max(1, (m.h - 158) // 40)
        return [(pygame.Rect(m.x + 20, m.y + 58 + i * 40, m.w - 40, 36), dev_id, name)
                for i, (dev_id, name) in enumerate(self.midi_mgr.available_devices[:visible])]

    def _reverb_slider_rect(self, m):
        return pygame.Rect(m.x + 145, m.bottom - 53, m.w - 205, 8)

    def _set_reverb_from_pos(self, pos):
        rect = self._reverb_slider_rect(self._modal_rect())
        amount = (pos[0] - rect.x) / max(1, rect.w)
        self.synth.set_reverb(min(1.0, max(0.0, amount)))

    def _settings_layout(self, m):
        y = m.y + 58
        lay = {'theme_label': y, 'themes': [], 'range_label': y + 106, 'ranges': [], 'label_label': y + 180, 'labels': []}
        for i, th in enumerate(self.THEMES):
            lay['themes'].append((pygame.Rect(m.x + 20 + (i % 2) * 240, y + 24 + (i // 2) * 36, 225, 30), th))
        for i, (code, title) in enumerate(self.RANGES):
            lay['ranges'].append((pygame.Rect(m.x + 20 + i * 94, lay['range_label'] + 24, 86, 28), code, title))
        for i, (code, title) in enumerate(self.LABELS):
            lay['labels'].append((pygame.Rect(m.x + 20 + i * 115, lay['label_label'] + 24, 105, 28), code, title))
        return lay

    # -------------------------------------------------------------------------
    # Modal click handling
    # -------------------------------------------------------------------------
    def _handle_modal_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False

        mx, my = event.pos
        m = self._modal_rect()

        # Click outside modal closes it
        if not m.collidepoint(mx, my):
            self.close_modal()
            return True

        # Close button (top right of modal)
        if pygame.Rect(m.right - 34, m.y + 12, 22, 22).collidepoint(mx, my):
            self.close_modal()
            return True

        if self.active_modal == 'modes':
            for r, name, _ in self._mode_rows(m):
                if r.collidepoint(mx, my):
                    self.mode_mgr.set_mode(name)
                    self.close_modal()
                    return True

        elif self.active_modal == 'soundfonts':
            for r, i, fname, fpath in self._sf_file_rows(m):
                if r.collidepoint(mx, my):
                    if self.synth.load_sf2(fpath):
                        self.preset_scroll = 0
                        self.sf_error = None
                    else:
                        self.sf_error = f"{os.path.basename(fpath)}: {self.synth.last_error or 'could not be loaded'}"
                    return True
            for r, j, p in self._sf_preset_rows(m):
                if r.collidepoint(mx, my):
                    self.synth.set_preset(j)
                    return True

        elif self.active_modal == 'songs':
            for r, i, item in self._song_rows(m):
                if r.collidepoint(mx, my):
                    self.mode_mgr.load_song(i)
                    self.close_modal()
                    return True

        elif self.active_modal == 'midi':
            slider = self._reverb_slider_rect(m)
            if slider.inflate(0, 22).collidepoint(mx, my):
                self._reverb_dragging = True
                self._set_reverb_from_pos((mx, my))
                return True
            for r, dev_id, name in self._midi_rows(m):
                if r.collidepoint(mx, my):
                    self.midi_mgr.connect(dev_id)
                    self.close_modal()
                    return True

        elif self.active_modal == 'settings':
            lay = self._settings_layout(m)
            for r, th in lay['themes']:
                if r.collidepoint(mx, my):
                    self.visuals.set_theme(th)
                    return True
            for r, code, _ in lay['ranges']:
                if r.collidepoint(mx, my):
                    self.keyboard.set_range_preset(code)
                    return True
            for r, code, _ in lay['labels']:
                if r.collidepoint(mx, my):
                    self.keyboard.label_mode = code
                    return True

        return True

    def draw(self, surface):
        # 1. Top Header Bar
        self._draw_header(surface)

        # 2. Bottom Timeline & HUD
        self._draw_bottom_hud(surface)

        # 3. Mode-specific overlay HUD (e.g. Score/Combo in Rhythm mode, Prompt in Practice)
        self._draw_mode_hud(surface)

        # 4. Active Modal (if open)
        if self.active_modal:
            self._draw_modal(surface)

    def _draw_header(self, surface):
        header_rect = pygame.Rect(0, 0, self.w, 48)
        pygame.draw.rect(surface, (12, 16, 23), header_rect)
        pygame.draw.line(surface, (34, 46, 58), (0, 48), (self.w, 48), 1)

        # Midirona Logo / Title
        pygame.draw.circle(surface, (83, 220, 220), (28, 23), 6)
        pygame.draw.circle(surface, (20, 57, 65), (28, 23), 3)
        logo_txt = self.font_title.render("MIDIRONA", True, (225, 239, 242))
        surface.blit(logo_txt, (42, 14))

        # Update button texts dynamically
        self.header_buttons[0].text = self._fit(f"Mode: {self.mode_mgr.current_mode}", self.font_bold, 104)
        song_name = self.mode_mgr.current_song.title if self.mode_mgr.current_song else "No Song"
        self.header_buttons[1].text = self._fit(f"Song: {song_name}", self.font_bold, 124)
        sf_name = self.synth.active_sf2_name

        # Show active preset name in the SF2 button
        preset_label = ""
        if self.synth.parser and self.synth.parser.presets:
            p = self.synth.parser.presets[self.synth.preset_idx]
            p_name = p['name'] or f"Preset {p['preset']}"
            preset_label = f" / {p_name}"
        self.header_buttons[2].text = self._fit(f"{sf_name}{preset_label}", self.font_bold, 204)

        # MIDI Device button status color
        has_midi = (self.midi_mgr.midi_input is not None)
        self.header_buttons[3].text = self._fit(f"MIDI: {self.midi_mgr.device_name}", self.font_bold, 104) if has_midi else "MIDI: Off (Keys)"
        self.header_buttons[3].text_color = (100, 255, 140) if has_midi else (180, 190, 205)

        for btn in self.header_buttons:
            btn.rect.y = 10
            btn.rect.height = 28
            btn.draw(surface, self.font_bold)

        # Preset prev/next buttons (< >) right next to SF2 button
        if self.synth.parser and len(self.synth.parser.presets) > 1:
            sf2_btn = self.header_buttons[2]
            px = sf2_btn.rect.right + 4
            py = sf2_btn.rect.y

            prev_r = pygame.Rect(px, py, 20, 28)
            next_r = pygame.Rect(px + 24, py, 20, 28)
            for r, lbl in ((prev_r, '<'), (next_r, '>')):
                hovered = r.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(surface, (60, 80, 115) if hovered else (38, 44, 60), r, border_radius=4)
                pygame.draw.rect(surface, (80, 110, 160), r, 1, border_radius=4)
                t = self.font_bold.render(lbl, True, (220, 230, 255))
                surface.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))
            # Store rects for click handling
            self._preset_prev_rect = prev_r
            self._preset_next_rect = next_r
        else:
            self._preset_prev_rect = None
            self._preset_next_rect = None

    def _draw_bottom_hud(self, surface):
        hud_rect = pygame.Rect(0, self.h - 50, self.w, 50)
        pygame.draw.rect(surface, (12, 16, 23), hud_rect)
        pygame.draw.line(surface, (34, 46, 58), (0, self.h - 50), (self.w, self.h - 50), 1)

        # Play / Pause button
        is_playing = self.mode_mgr.is_playing
        play_rect = pygame.Rect(20, self.h - 39, 68, 28)
        pygame.draw.rect(surface, (28, 111, 119), play_rect, border_radius=8)
        p_txt = self.font_bold.render("PAUSE" if is_playing else "PLAY", True, (238, 255, 255))
        surface.blit(p_txt, (play_rect.centerx - p_txt.get_width()//2, play_rect.centery - p_txt.get_height()//2))

        # Reset button
        rst_rect = pygame.Rect(96, self.h - 39, 58, 28)
        pygame.draw.rect(surface, (28, 34, 45), rst_rect, border_radius=8)
        r_txt = self.font.render("RESET", True, (190, 207, 213))
        surface.blit(r_txt, (rst_rect.centerx - r_txt.get_width()//2, rst_rect.centery - r_txt.get_height()//2))

        # Timeline Seekbar
        cur_time = self.mode_mgr.song_time
        total_time = self.mode_mgr.current_song.duration if self.mode_mgr.current_song else 1.0
        bar_x = 178
        bar_w = max(180, self.w - 510)
        bar_y = self.h - 25
        bar_h = 6

        # Track
        pygame.draw.rect(surface, (39, 51, 62), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        # Progress
        progress = max(0.0, min(1.0, cur_time / total_time))
        prog_w = int(bar_w * progress)
        if prog_w > 0:
            pygame.draw.rect(surface, (83, 220, 220), (bar_x, bar_y, prog_w, bar_h), border_radius=4)
        # Handle
        pygame.draw.circle(surface, (255, 255, 255), (bar_x + prog_w, bar_y + 4), 6)

        # Time display
        m1, s1 = divmod(int(cur_time), 60)
        m2, s2 = divmod(int(total_time), 60)
        time_str = f"{m1:02d}:{s1:02d} / {m2:02d}:{s2:02d}"
        t_surf = self.font_bold.render(time_str, True, (180, 195, 215))
        surface.blit(t_surf, (bar_x + bar_w + 12, self.h - 32))

        # Octave info
        oct_str = f"Octave: C{self.keyboard.base_octave}  ( [ ] )"
        oct_surf = self.font_small.render(oct_str, True, (130, 145, 165))
        surface.blit(oct_surf, (self.w - oct_surf.get_width() - 20, self.h - 30))

    def _draw_mode_hud(self, surface):
        mode = self.mode_mgr.current_mode
        if mode == 'Practice':
            if self.mode_mgr.is_waiting:
                note_str = "Press the glowing key(s) to continue!"
                tip = self.font_bold.render(note_str, True, (255, 230, 90))
                surface.blit(tip, (self.w // 2 - tip.get_width() // 2, 60))
        elif mode == 'Rhythm Game':
            score_str = f"SCORE: {self.mode_mgr.score:,}  |  COMBO: {self.mode_mgr.combo} (MAX: {self.mode_mgr.max_combo})  |  ACC: {self.mode_mgr.get_accuracy()}%  |  RANK: {self.mode_mgr.get_rank()}"
            s_surf = self.font_bold.render(score_str, True, (0, 240, 255))
            surface.blit(s_surf, (self.w // 2 - s_surf.get_width() // 2, 56))
        elif mode == 'Melody Echo':
            state_text = f"Round {self.mode_mgr.echo_round}: "
            if self.mode_mgr.echo_state == 'playing_prompt':
                state_text += "Listen closely to the melody..."
                col = (255, 220, 100)
            elif self.mode_mgr.echo_state == 'listening':
                state_text += f"Your Turn! Play note {len(self.mode_mgr.echo_player_input) + 1} of {len(self.mode_mgr.echo_sequence)}"
                col = (100, 255, 160)
            else:
                state_text += "Get ready..."
                col = (200, 210, 225)
            s_surf = self.font_bold.render(state_text, True, col)
            surface.blit(s_surf, (self.w // 2 - s_surf.get_width() // 2, 56))

    def _draw_option(self, surface, rect, text, selected):
        bg = (40, 75, 120) if selected else (34, 38, 50)
        pygame.draw.rect(surface, bg, rect, border_radius=5)
        pygame.draw.rect(surface, (0, 210, 255) if selected else (50, 55, 72), rect, 1, border_radius=5)
        lbl = self.font.render(text, True, (255, 255, 255) if selected else (180, 195, 215))
        surface.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.y + 6))

    def _draw_modal(self, surface):
        # Dim background
        dim_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 170))
        surface.blit(dim_surf, (0, 0))

        self._clamp_scrolls()
        m = self._modal_rect()
        modal_x, modal_y, modal_w = m.x, m.y, m.w

        # Modal Window
        pygame.draw.rect(surface, (24, 27, 36), m, border_radius=10)
        pygame.draw.rect(surface, (60, 68, 88), m, 2, border_radius=10)

        # Close button
        close_rect = pygame.Rect(m.right - 34, m.y + 12, 22, 22)
        pygame.draw.rect(surface, (50, 56, 72), close_rect, border_radius=4)
        c_txt = self.font_bold.render("X", True, (240, 240, 240))
        surface.blit(c_txt, (close_rect.centerx - c_txt.get_width() // 2, close_rect.centery - c_txt.get_height() // 2))

        titles = {
            'modes': "Select Game Mode",
            'soundfonts': "SoundFont (.sf2) & Instrument Selector",
            'songs': "Song Library (.mid)",
            'midi': "Hardware MIDI Devices",
            'settings': "Visual & Keyboard Settings",
            'help': "Controls & Information"
        }
        title_txt = self.font_title.render(titles.get(self.active_modal, "Menu"), True, (255, 255, 255))
        surface.blit(title_txt, (modal_x + 24, modal_y + 16))
        pygame.draw.line(surface, (45, 52, 68), (modal_x + 20, modal_y + 48), (modal_x + modal_w - 20, modal_y + 48), 1)

        if self.active_modal == 'modes':
            for r, m_name, desc in self._mode_rows(m):
                is_cur = (self.mode_mgr.current_mode == m_name)
                pygame.draw.rect(surface, (40, 75, 120) if is_cur else (32, 36, 48), r, border_radius=6)
                pygame.draw.rect(surface, (60, 90, 140) if is_cur else (50, 55, 70), r, 1, border_radius=6)
                lbl = self.font_bold.render(m_name, True, (0, 230, 255) if is_cur else (240, 240, 245))
                surface.blit(lbl, (r.x + 14, r.y + 6))
                surface.blit(self.font_small.render(self._fit(desc, self.font_small, r.w - 28), True, (160, 175, 195)), (r.x + 14, r.y + 26))

        elif self.active_modal == 'soundfonts':
            a = self._sf_areas(m)
            info = "Drop any .sf2 file into 'soundfonts/' | Wheel: scroll | Up/Down: change instrument"
            if self.sf_error:
                info, info_col = "Could not load " + self.sf_error, (255, 120, 120)
            else:
                info_col = (130, 220, 150)
            surface.blit(self.font_small.render(self._fit(info, self.font_small, m.w - 48), True, info_col), (modal_x + 24, modal_y + 58))

            n_pre = len(self.synth.parser.presets) if self.synth.parser else 0
            surface.blit(self.font_bold.render(f"SoundFont Files ({len(self.available_sf2_files)}):", True, (200, 215, 235)), (a['left'].x + 4, modal_y + 82))
            surface.blit(self.font_bold.render(f"Instruments / Presets ({n_pre}):", True, (200, 215, 235)), (a['right'].x, modal_y + 82))

            if not self.available_sf2_files:
                surface.blit(self.font_small.render("No .sf2 files found.", True, (240, 180, 100)), (a['left'].x + 8, a['left'].y + 6))

            cur_path = getattr(self.synth, 'active_sf2_path', None)
            for r, i, fname, fpath in self._sf_file_rows(m):
                if cur_path:
                    is_active = os.path.normpath(cur_path) == os.path.normpath(fpath)
                else:
                    is_active = self._is_sf2_active(fname)
                pygame.draw.rect(surface, (28, 68, 108) if is_active else (30, 34, 46), r, border_radius=5)
                pygame.draw.rect(surface, (0, 200, 255) if is_active else (45, 52, 68), r, 1, border_radius=5)
                fn_clean = os.path.splitext(fname)[0].replace('_', ' ')
                if len(fn_clean) > 3 and fn_clean[:2].isdigit():
                    fn_clean = fn_clean[3:].strip()
                lbl = self.font.render(self._fit(fn_clean, self.font, r.w - 20), True, (0, 235, 255) if is_active else (215, 225, 240))
                surface.blit(lbl, (r.x + 10, r.y + 7))
            self._draw_scrollbar(surface, a['left'], len(self.available_sf2_files), a['rows_left'], self.sf2_scroll)

            for r, j, p in self._sf_preset_rows(m):
                is_sel = (self.synth.preset_idx == j)
                pygame.draw.rect(surface, (28, 80, 50) if is_sel else (30, 34, 46), r, border_radius=5)
                pygame.draw.rect(surface, (100, 255, 140) if is_sel else (45, 52, 68), r, 1, border_radius=5)
                p_name = p['name'] or f"Preset {p['preset']}"
                bank = p.get('bank', 0)
                prefix = f"{p['preset']:03d}" if not bank else f"{bank:03d}-{p['preset']:03d}"
                tag_w = 70 if is_sel else 0
                txt = self._fit(f"{prefix}: {p_name}", self.font, r.w - 20 - tag_w)
                surface.blit(self.font.render(txt, True, (120, 255, 160) if is_sel else (215, 225, 240)), (r.x + 10, r.y + 5))
                if is_sel:
                    act = self.font_small.render("▶ ACTIVE", True, (120, 255, 160))
                    surface.blit(act, (r.right - act.get_width() - 8, r.y + 7))
            self._draw_scrollbar(surface, a['right'], n_pre, a['rows_right'], self.preset_scroll)

        elif self.active_modal == 'songs':
            surface.blit(self.font_small.render("Drop any .mid file into 'songs/' folder to play it here! (Mouse wheel: scroll)", True, (130, 220, 150)), (modal_x + 24, modal_y + 60))
            area, rows = self._song_area(m)
            for r, i, item in self._song_rows(m):
                is_cur = (self.mode_mgr.current_song and self.mode_mgr.current_song.filename == item['path'])
                pygame.draw.rect(surface, (30, 70, 110) if is_cur else (32, 36, 48), r, border_radius=6)
                pygame.draw.rect(surface, (0, 210, 255) if is_cur else (48, 54, 70), r, 1, border_radius=6)
                lbl = self.font_bold.render(self._fit(item['title'], self.font_bold, r.w - 28), True, (0, 240, 255) if is_cur else (230, 235, 245))
                surface.blit(lbl, (r.x + 14, r.y + 8))
            self._draw_scrollbar(surface, area, len(self.mode_mgr.song_library.songs_list), rows, self.song_scroll)

        elif self.active_modal == 'midi':
            devices = self.midi_mgr.available_devices
            if not devices:
                surface.blit(self.font.render("No hardware MIDI input devices detected.", True, (240, 180, 100)), (modal_x + 24, modal_y + 78))
                surface.blit(self.font_small.render("Connect a USB MIDI keyboard (e.g. Arturia KeyStep mk2) and reopen.", True, (160, 175, 195)), (modal_x + 24, modal_y + 102))
            for r, dev_id, dev_name in self._midi_rows(m):
                is_con = (self.midi_mgr.device_id == dev_id)
                pygame.draw.rect(surface, (30, 80, 50) if is_con else (32, 36, 48), r, border_radius=6)
                pygame.draw.rect(surface, (100, 255, 140) if is_con else (48, 54, 70), r, 1, border_radius=6)
                tag = self.font_small.render("CONNECTED" if is_con else "CLICK TO CONNECT", True, (120, 255, 160) if is_con else (140, 155, 175))
                lbl = self.font_bold.render(self._fit(dev_name, self.font_bold, r.w - tag.get_width() - 44), True, (120, 255, 160) if is_con else (230, 235, 245))
                surface.blit(lbl, (r.x + 14, r.y + 9))
                surface.blit(tag, (r.right - tag.get_width() - 14, r.y + 11))
            slider = self._reverb_slider_rect(m)
            amount = self.synth.reverb_amount
            value_text = f"{int(amount * 100)}%"
            surface.blit(self.font_bold.render("Reverb", True, (230, 239, 242)), (m.x + 24, slider.y - 9))
            pygame.draw.rect(surface, (43, 54, 65), slider, border_radius=5)
            fill = pygame.Rect(slider.x, slider.y, int(slider.w * amount), slider.h)
            if fill.w > 0:
                pygame.draw.rect(surface, (83, 220, 220), fill, border_radius=5)
            pygame.draw.circle(surface, (236, 248, 248), (slider.x + int(slider.w * amount), slider.centery), 8)
            value = self.font_bold.render(value_text, True, (150, 215, 218))
            surface.blit(value, (slider.right + 12, slider.y - 7))

        elif self.active_modal == 'settings':
            lay = self._settings_layout(m)
            surface.blit(self.font_bold.render("Atmosphere / Color Theme:", True, (255, 255, 255)), (modal_x + 24, lay['theme_label']))
            for r, th in lay['themes']:
                self._draw_option(surface, r, th, self.visuals.theme_name == th)
            surface.blit(self.font_bold.render("Piano Keyboard Range:", True, (255, 255, 255)), (modal_x + 24, lay['range_label']))
            for r, code, title in lay['ranges']:
                self._draw_option(surface, r, title, self.keyboard.range_mode == code)
            surface.blit(self.font_bold.render("Key Labels Display:", True, (255, 255, 255)), (modal_x + 24, lay['label_label']))
            for r, code, title in lay['labels']:
                self._draw_option(surface, r, title, self.keyboard.label_mode == code)

        elif self.active_modal == 'help':
            help_lines = [
                ("Hardware MIDI Controller:", "Plug in any MIDI keyboard (KeyStep, etc.). Velocity sensitive!"),
                ("Computer Keyboard Controls:", "Lower Octave: Z, S, X, D, C, V, G, B, H, N, J, M"),
                ("Upper Octave:", "Q, 2, W, 3, E, R, 5, T, 6, Y, 7, U, I, 9, O"),
                ("Octave Shift:", "[ and ] or , and . to shift base octave"),
                ("Space Bar:", "Play / Pause song"),
                ("Tab Key:", "Quick cycle through .sf2 SoundFonts"),
                ("SoundFont window:", "Mouse wheel to scroll, Up/Down to change instrument"),
                ("R Key:", "Restart current song"),
                ("Custom SoundFonts (.sf2):", "Drop any .sf2 file into 'soundfonts/' folder"),
                ("Custom Songs (.mid):", "Drop any .mid/.midi file into 'songs/' folder"),
            ]
            item_y = modal_y + 58
            for title, desc in help_lines:
                t_surf = self.font_bold.render(title, True, (0, 220, 255))
                surface.blit(t_surf, (modal_x + 24, item_y))
                room = modal_w - 48 - t_surf.get_width() - 10
                surface.blit(self.font.render(self._fit(desc, self.font, room), True, (200, 210, 225)), (modal_x + 24 + t_surf.get_width() + 10, item_y))
                item_y += 32
