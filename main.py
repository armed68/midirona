
import sys
import os
import pygame


from sf2_engine import SF2Synthesizer, generate_bundled_soundfonts
from song_library import SongLibrary
from midi_input import MidiInputManager
from piano_keyboard import PianoKeyboard, PC_KEY_MAP
from visuals import VisualsEngine
from modes import ModeManager, GameMode
from ui import UIManager

def main():
    
    pygame.init()
    pygame.font.init()

    SCREEN_WIDTH = 1040
    SCREEN_HEIGHT = 650
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Midirona - SF2 Piano Game")

    clock = pygame.time.Clock()
    
    print("[Midirona] Checking SoundFonts and Song Library...")
    generate_bundled_soundfonts("soundfonts")
    song_lib = SongLibrary("songs")

    
    synth = SF2Synthesizer(output_rate=44100)
    
    default_sf2 = os.path.join("soundfonts", "01_Grand_Piano.sf2")
    if os.path.exists(default_sf2):
        synth.load_sf2(default_sf2)

    midi_mgr = MidiInputManager()
    
    keyboard_h = 160
    keyboard_y = SCREEN_HEIGHT - keyboard_h - 48
    keyboard_rect = pygame.Rect(20, keyboard_y, SCREEN_WIDTH - 40, keyboard_h)
    keyboard = PianoKeyboard(keyboard_rect, min_pitch=36, max_pitch=96)

    
    visuals = VisualsEngine(SCREEN_WIDTH, SCREEN_HEIGHT)
    visuals.hit_line_y = keyboard_y

    
    mode_mgr = ModeManager(synth, keyboard, visuals, song_lib)

    
    ui = UIManager(SCREEN_WIDTH, SCREEN_HEIGHT, mode_mgr, synth, midi_mgr, visuals, keyboard)

    
    mouse_dragging = False
    last_mouse_pitch = None
    pressed_pc_keys = {}  

    running = True
    print("\n[Midirona] Game initialized successfully. Ready to play!\n")

    while running:
        dt = clock.tick(60) / 1000.0  
        dt = min(dt, 0.1)             

        
        
        
        for ev in midi_mgr.poll_events():
            ev_type, arg1, arg2 = ev
            if ev_type == 'note_on':
                mode_mgr.handle_user_note_on(arg1, arg2)
            elif ev_type == 'note_off':
                mode_mgr.handle_user_note_off(arg1)
            elif ev_type == 'sustain':
                synth.set_sustain_pedal(arg1)

        
        
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            
            elif event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = max(960, event.w), max(550, event.h)
                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
                keyboard_y = SCREEN_HEIGHT - keyboard_h - 48
                keyboard.set_rect(pygame.Rect(20, keyboard_y, SCREEN_WIDTH - 40, keyboard_h))
                visuals.set_dimensions(SCREEN_WIDTH, SCREEN_HEIGHT, keyboard_y)
                ui.set_dimensions(SCREEN_WIDTH, SCREEN_HEIGHT)

            
            if ui.handle_event(event):
                continue

            
            if event.type == pygame.KEYDOWN:
                if event.key in PC_KEY_MAP and event.key not in pressed_pc_keys:
                    oct_offset, semi = PC_KEY_MAP[event.key]
                    target_pitch = (keyboard.base_octave * 12) + (oct_offset * 12) + semi
                    if 0 <= target_pitch <= 127:
                        pressed_pc_keys[event.key] = target_pitch
                        mode_mgr.handle_user_note_on(target_pitch, velocity=105)

            elif event.type == pygame.KEYUP:
                if event.key in pressed_pc_keys:
                    target_pitch = pressed_pc_keys.pop(event.key)
                    mode_mgr.handle_user_note_off(target_pitch)

            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pitch = keyboard.get_pitch_at_pos(event.pos)
                if pitch is not None:
                    mouse_dragging = True
                    last_mouse_pitch = pitch
                    mode_mgr.handle_user_note_on(pitch, velocity=95)

            elif event.type == pygame.MOUSEMOTION and mouse_dragging:
                pitch = keyboard.get_pitch_at_pos(event.pos)
                if pitch != last_mouse_pitch:
                    if last_mouse_pitch is not None:
                        mode_mgr.handle_user_note_off(last_mouse_pitch)
                    if pitch is not None:
                        mode_mgr.handle_user_note_on(pitch, velocity=95)
                    last_mouse_pitch = pitch

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if mouse_dragging:
                    if last_mouse_pitch is not None:
                        mode_mgr.handle_user_note_off(last_mouse_pitch)
                    mouse_dragging = False
                    last_mouse_pitch = None

        
        
        
        mode_mgr.update(dt)
        visuals.update(dt)
        keyboard.update(dt)

        
        
        
        
        visuals.draw_background(screen)

        
        if mode_mgr.current_song:
            visuals.draw_falling_notes(screen, mode_mgr.current_song, mode_mgr.song_time, keyboard)

        
        visuals.draw_fx(screen)

        
        keyboard.draw(screen)

        
        ui.draw(screen)

        pygame.display.flip()

    
    print("[Midirona] Shutting down...")
    synth.stop_all()
    midi_mgr.close()
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
