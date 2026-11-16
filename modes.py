
import time
import random
import pygame

class GameMode:
    FREE_PLAY = "Free Play"
    PRACTICE = "Practice"
    RHYTHM = "Rhythm Game"
    LISTEN = "Listen / Autoplay"
    ECHO = "Melody Echo"


class ModeManager:
    def __init__(self, synth, keyboard, visuals, song_library):
        self.synth = synth
        self.keyboard = keyboard
        self.visuals = visuals
        self.song_library = song_library

        self.current_mode = GameMode.FREE_PLAY
        self.current_song = None
        self.song_time = 0.0
        self.is_playing = False
        self.playback_speed = 1.0   

        
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.perfect_count = 0
        self.good_count = 0
        self.miss_count = 0

        
        self.waiting_for_keys = set()
        self.is_waiting = False

        
        self.echo_round = 1
        self.echo_sequence = []
        self.echo_player_input = []
        self.echo_state = 'ready'  
        self.echo_timer = 0.0

        
        self.load_song(0)

    def set_mode(self, mode_name):
        self.current_mode = mode_name
        self.reset_song()
        if mode_name == GameMode.ECHO:
            self.start_echo_game()
        print(f"[Mode] Switched to mode: '{mode_name}'")

    def load_song(self, song_index):
        song = self.song_library.get_song(song_index)
        if song:
            self.current_song = song
            self.reset_song()
            self.keyboard.auto_fit_range(song)

    def reset_song(self):
        self.song_time = 0.0
        self.is_playing = (self.current_mode in (GameMode.PRACTICE, GameMode.RHYTHM, GameMode.LISTEN))
        self.waiting_for_keys.clear()
        self.is_waiting = False
        self.keyboard.clear_expected()

        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.perfect_count = 0
        self.good_count = 0
        self.miss_count = 0

        if self.current_song:
            self.current_song.reset_state()

    def toggle_play_pause(self):
        self.is_playing = not self.is_playing
        if not self.is_playing:
            self.synth.stop_all()

    def seek_time(self, target_time):
        if not self.current_song:
            return
        target_time = max(0.0, min(self.current_song.duration, target_time))
        self.song_time = target_time
        self.synth.stop_all()

        
        for n in self.current_song.notes:
            if n.start_time < target_time - 0.2:
                n.hit = True
            else:
                n.hit = False
                n.missed = False

    def handle_user_note_on(self, pitch, velocity=100):
        
        self.synth.note_on(pitch, velocity)
        self.keyboard.set_key_pressed(pitch, True, velocity)

        
        kx = self.keyboard.get_key_x_center(pitch)
        ky = self.keyboard.rect.top
        kw = self.keyboard.get_key_width(pitch)
        hand = 'right' if pitch >= 60 else 'left'
        self.visuals.trigger_key_burst(kx, ky, hand, velocity, pitch=pitch, key_width=kw)

        
        if self.current_mode == GameMode.PRACTICE:
            self._handle_practice_hit(pitch)
        elif self.current_mode == GameMode.RHYTHM:
            self._handle_rhythm_hit(pitch)
        elif self.current_mode == GameMode.ECHO:
            self._handle_echo_input(pitch)

    def handle_user_note_off(self, pitch):
        self.synth.note_off(pitch)
        self.keyboard.set_key_pressed(pitch, False)
        
        self.visuals.stop_key_trail(pitch)

    
    
    
    def _update_practice_mode(self, dt):
        if not self.current_song or not self.is_playing:
            return

        
        
        target_notes = [n for n in self.current_song.notes if not n.hit and (n.start_time - self.song_time) <= 0.04]

        if target_notes and not self.is_waiting:
            
            earliest_time = min(n.start_time for n in target_notes)
            chord_notes = [n for n in target_notes if abs(n.start_time - earliest_time) < 0.08]
            self.waiting_for_keys = set(n.pitch for n in chord_notes)
            self.is_waiting = True

            
            self.keyboard.clear_expected()
            for n in chord_notes:
                self.keyboard.set_expected(n.pitch, True, n.hand)

        if not self.is_waiting:
            self.song_time += dt * self.playback_speed

            
            if self.song_time > self.current_song.duration + 1.0:
                self.reset_song()

    def _handle_practice_hit(self, pitch):
        if self.is_waiting and pitch in self.waiting_for_keys:
            self.waiting_for_keys.remove(pitch)
            self.keyboard.set_expected(pitch, False)
            self.keyboard.trigger_flash(pitch, (100, 255, 140), 0.3)

            
            for n in self.current_song.notes:
                if not n.hit and n.pitch == pitch and abs(n.start_time - self.song_time) < 0.35:
                    n.hit = True
                    break

            if not self.waiting_for_keys:
                
                self.is_waiting = False
                self.keyboard.clear_expected()

    
    
    
    def _update_rhythm_mode(self, dt):
        if not self.current_song or not self.is_playing:
            return

        self.song_time += dt * self.playback_speed

        
        for n in self.current_song.notes:
            if not n.hit and not n.missed:
                
                if (self.song_time - n.start_time) > 0.18:
                    n.missed = True
                    self.miss_count += 1
                    self.combo = 0
                    kx = self.keyboard.get_key_x_center(n.pitch)
                    self.visuals.add_floating_text("MISS", kx, self.visuals.hit_line_y - 20, 'miss')
                    self.keyboard.trigger_flash(n.pitch, (255, 70, 80), 0.2)

        
        if self.song_time > self.current_song.duration + 2.0:
            self.reset_song()

    def _handle_rhythm_hit(self, pitch):
        if not self.current_song or not self.is_playing:
            return

        
        candidates = [n for n in self.current_song.notes if not n.hit and not n.missed and n.pitch == pitch]
        if not candidates:
            return

        closest_note = min(candidates, key=lambda n: abs(n.start_time - self.song_time))
        time_diff = abs(closest_note.start_time - self.song_time)

        kx = self.keyboard.get_key_x_center(pitch)
        ky = self.visuals.hit_line_y - 20

        if time_diff <= 0.08:  
            closest_note.hit = True
            self.perfect_count += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.score += 100 + (self.combo * 5)
            self.visuals.add_floating_text("PERFECT +100", kx, ky, 'perfect')
            self.keyboard.trigger_flash(pitch, (80, 255, 160), 0.25)
        elif time_diff <= 0.18:  
            closest_note.hit = True
            self.good_count += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.score += 50 + (self.combo * 2)
            self.visuals.add_floating_text("GOOD +50", kx, ky, 'good')
            self.keyboard.trigger_flash(pitch, (255, 230, 80), 0.25)

    def get_accuracy(self):
        total = self.perfect_count + self.good_count + self.miss_count
        if total == 0:
            return 100.0
        return round(((self.perfect_count * 100.0 + self.good_count * 60.0) / (total * 100.0)) * 100.0, 1)

    def get_rank(self):
        acc = self.get_accuracy()
        if acc >= 95.0: return "S"
        if acc >= 85.0: return "A"
        if acc >= 70.0: return "B"
        return "C"

    
    
    
    def _update_listen_mode(self, dt):
        if not self.current_song or not self.is_playing:
            return

        prev_time = self.song_time
        self.song_time += dt * self.playback_speed

        
        for n in self.current_song.notes:
            if prev_time <= n.start_time < self.song_time:
                self.synth.note_on(n.pitch, n.velocity)
                self.keyboard.set_key_pressed(n.pitch, True, n.velocity)
                kx = self.keyboard.get_key_x_center(n.pitch)
                ky = self.keyboard.rect.top
                kw = self.keyboard.get_key_width(n.pitch)
                self.visuals.trigger_key_burst(kx, ky, n.hand, n.velocity, pitch=n.pitch, key_width=kw)
                n.hit = True
            elif prev_time <= n.end_time < self.song_time:
                self.synth.note_off(n.pitch)
                self.keyboard.set_key_pressed(n.pitch, False)
                self.visuals.stop_key_trail(n.pitch)

        if self.song_time > self.current_song.duration + 1.5:
            self.reset_song()

    
    
    
    def start_echo_game(self):
        self.echo_round = 1
        self._generate_echo_sequence()

    def _generate_echo_sequence(self):
        
        length = min(7, 2 + self.echo_round)
        
        scale = [60, 62, 64, 65, 67, 69, 71, 72]
        self.echo_sequence = [random.choice(scale) for _ in range(length)]
        self.echo_player_input.clear()
        self.echo_state = 'playing_prompt'
        self.echo_timer = 0.5

    def _update_echo_mode(self, dt):
        if self.echo_state == 'playing_prompt':
            self.echo_timer -= dt
            if self.echo_timer <= 0:
                if self.echo_sequence:
                    idx = len(self.echo_player_input)
                    if idx < len(self.echo_sequence):
                        pitch = self.echo_sequence[idx]
                        self.synth.note_on(pitch, 100)
                        self.keyboard.set_key_pressed(pitch, True, 100)
                        self.keyboard.trigger_flash(pitch, (100, 220, 255), 0.35)
                        self.echo_player_input.append(pitch)
                        self.echo_timer = 0.55
                    else:
                        
                        self.synth.stop_all()
                        for k in self.keyboard.keys.values():
                            k.pressed = False
                        self.echo_player_input.clear()
                        self.echo_state = 'listening'

    def _handle_echo_input(self, pitch):
        if self.echo_state != 'listening':
            return

        expected_idx = len(self.echo_player_input)
        if expected_idx < len(self.echo_sequence):
            expected_pitch = self.echo_sequence[expected_idx]
            if pitch == expected_pitch:
                self.echo_player_input.append(pitch)
                self.keyboard.trigger_flash(pitch, (100, 255, 140), 0.3)
                if len(self.echo_player_input) == len(self.echo_sequence):
                    
                    self.score += self.echo_round * 150
                    self.echo_round += 1
                    self.visuals.add_floating_text("PERFECT ECHO! +ROUND", self.visuals.w // 2, self.visuals.h // 2, 'perfect')
                    self.echo_state = 'playing_prompt'
                    self.echo_timer = 1.0
                    self._generate_echo_sequence()
            else:
                
                self.keyboard.trigger_flash(pitch, (255, 70, 80), 0.4)
                self.visuals.add_floating_text("TRY AGAIN!", self.visuals.w // 2, self.visuals.h // 2, 'miss')
                self.echo_player_input.clear()
                self.echo_state = 'playing_prompt'
                self.echo_timer = 1.0

    
    
    
    def update(self, dt):
        if self.current_mode == GameMode.PRACTICE:
            self._update_practice_mode(dt)
        elif self.current_mode == GameMode.RHYTHM:
            self._update_rhythm_mode(dt)
        elif self.current_mode == GameMode.LISTEN:
            self._update_listen_mode(dt)
        elif self.current_mode == GameMode.ECHO:
            self._update_echo_mode(dt)
