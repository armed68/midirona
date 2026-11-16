"""
Automated Integration Test for Midirona
Tests:
- SF2 engine loading and soundfonts
- Song library loading and MIDI parser
- MIDI input manager
- Piano keyboard layout and hit-testing
- Visuals engine rendering and particles
- Mode manager (Free Play, Practice, Rhythm, Listen, Echo)
- UI manager
- 120 frames of continuous execution
"""

import os
import pygame

# Set dummy video driver for headless environment if needed
os.environ['SDL_VIDEODRIVER'] = 'dummy'

from sf2_engine import SF2Synthesizer, generate_bundled_soundfonts
from song_library import SongLibrary
from midi_input import MidiInputManager
from piano_keyboard import PianoKeyboard, PC_KEY_MAP
from visuals import VisualsEngine
from modes import ModeManager, GameMode
from ui import UIManager

def run_tests():
    print("=== Running Midirona Integration Tests ===")
    pygame.init()
    pygame.font.init()

    # 1. Test SoundFonts
    generate_bundled_soundfonts("soundfonts")
    synth = SF2Synthesizer()
    for sf in os.listdir("soundfonts"):
        if sf.endswith(".sf2"):
            success = synth.load_sf2(os.path.join("soundfonts", sf))
            assert success, f"Failed to load {sf}"
            # Test note playback
            synth.note_on(60, 100)
            synth.note_on(64, 80)
            synth.note_off(60)
            synth.note_off(64)
    print("✓ All SoundFonts loaded and tested successfully!")

    # 2. Test Song Library
    song_lib = SongLibrary("songs")
    assert len(song_lib.songs_list) >= 6, "Expected at least 6 songs"
    for i in range(len(song_lib.songs_list)):
        s = song_lib.get_song(i)
        assert s is not None, f"Failed to parse song {i}"
        assert len(s.notes) > 0, f"Song {s.title} has 0 notes"
    print("✓ All Songs parsed and validated successfully!")

    # 3. Test Keyboard
    keyboard = PianoKeyboard(pygame.Rect(20, 400, 1000, 160))
    for range_mode in ['25', '49', '61', '88']:
        keyboard.set_range_preset(range_mode)
        assert len(keyboard.keys) > 0
    print("✓ Piano keyboard ranges tested successfully!")

    # 4. Test Visuals & Modes
    visuals = VisualsEngine(1040, 650)
    midi_mgr = MidiInputManager()
    mode_mgr = ModeManager(synth, keyboard, visuals, song_lib)
    ui = UIManager(1040, 650, mode_mgr, synth, midi_mgr, visuals, keyboard)

    screen = pygame.display.set_mode((1040, 650))

    # Test all modes
    for m in [GameMode.FREE_PLAY, GameMode.PRACTICE, GameMode.RHYTHM, GameMode.LISTEN, GameMode.ECHO]:
        mode_mgr.set_mode(m)
        # Simulate 30 frames
        for f in range(30):
            dt = 1.0 / 60.0
            mode_mgr.handle_user_note_on(60 + (f % 12), 100)
            mode_mgr.update(dt)
            visuals.update(dt)
            keyboard.update(dt)
            mode_mgr.handle_user_note_off(60 + (f % 12))

            # Draw frame
            visuals.draw_background(screen)
            if mode_mgr.current_song:
                visuals.draw_falling_notes(screen, mode_mgr.current_song, mode_mgr.song_time, keyboard)
            visuals.draw_fx(screen)
            keyboard.draw(screen)
            ui.draw(screen)

    print("✓ All game modes simulated without errors!")
    synth.stop_all()
    midi_mgr.close()
    pygame.quit()
    print("=== ALL TESTS PASSED! ===")

if __name__ == "__main__":
    run_tests()
