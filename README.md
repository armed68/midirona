[README.md](https://github.com/user-attachments/files/34904019/README.md)
# midirona
A game for midi keyboard users or just a pc can run ppython that use midi keyboard and van use sf2 .mid files
# Midirona - SF2 SoundFont Supported Piano Game 🎹

**Midirona** has been developed from the ground up as a **standalone, high-performance desktop game (Python & Pygame & NumPy)**, inspired by [FunkyChickenCape's Pianora prototype on itch.io] btw my version is better (https://funkychickencape.itch.io/pianora)).

You can dynamically change game sounds using **.sf2 (SoundFont 2)** files, and play however you like with any external **physical MIDI keyboard/controller**, computer keyboard, or mouse!

---

## 🌟 Key Features

### 1. 🎵 Full SoundFont (.sf2) Support
- Directly reads and polyphonically synthesizes all sound banks in the standard SoundFont 2.04 (.sf2) format.
- Key velocity sensitivity: Soft tone when pressed lightly, bright and rich tone when struck hard.
- **Included Sound Banks (`soundfonts/`):**
  - `01_Grand_Piano.sf2`: Acoustic Concert Grand Piano
  - `02_Electric_Piano.sf2`: Vintage Rhodes / Chime Electric Piano
  - `03_Chiptune_8Bit.sf2`: Retro 8-bit Pulse / Square Wave Synth
  - `04_Dream_Synth_Pad.sf2`: Dreamy atmospheric ambient pad
  - `05_Harpsichord.sf2`: Baroque harpsichord (bright plucked acoustic)
  - `06_Music_Box.sf2`: Magical music box bell
- **Note:** Compressed `.sf3` (OGG) sound banks are not supported; the game will reject them without crashing and display the reason in the SoundFont window. Please use standard (uncompressed) `.sf2` files.
- **Add Your Own SF2 Files:** Simply copy any `.sf2` file into the `soundfonts/` folder; it will instantly appear in the game menu and can be selected with a single click!

---

### 2. 🎹 Real Hardware MIDI Support
- Automatically detects USB / MIDI keyboards and controllers (via `pygame.midi`).
- Supports Velocity sensitivity, Pitch Bend, and Sustain Pedal (CC 64).
- You can switch connected devices anytime using the **"MIDI Device"** button in the top menu.

---

### 3. 🎮 5 Different Game Modes

1. **Free Play:**
   - Improvise freely at the piano.
   - A visual feast accompanied by rising note trails and energy sparks every time you press a key.

2. **Practice (Synthesia Wait Mode):**
   - While playing a song, **the game pauses and waits for you to press the correct key** when the falling notes reach the target line!
   - The keys to be pressed glow on the keyboard (cyan for the right hand, golden yellow for the left hand).
   - Ideal for learning new pieces stress-free at your own pace.

3. **Rhythm Game:**
   - Score points by hitting the falling notes on time!
   - `PERFECT (+100)`, `GOOD (+50)`, `MISS`.
   - Real-time Combo counter, Accuracy percentage (%), and S, A, B, C rank grades.

4. **Listen / Autoplay:**
   - Sit back and watch your chosen piece played with the SF2 sound bank, complete with a falling note waterfall and keyboard animations.
   - Includes a timeline scrubber for rewinding/fast-forwarding and speed adjustment.

5. **Melody Echo (Ear Training):**
   - The game plays a short melody and then asks you to play it back from memory.
   - The melody gets longer and more challenging with each round.

---

### 4. 🎼 Built-in Classical Pieces & Custom MIDI Loading
- **Included Pieces (`songs/`):**
  - Beethoven - Für Elise
  - Beethoven - Moonlight Sonata
  - Mozart - Rondo Alla Turca
  - Pachelbel - Canon in D
  - Erik Satie - Gymnopédie No. 1
  - Twinkle Twinkle Little Star (For beginners)
- **Add Your Own Tracks:** Drop any `.mid` or `.midi` file into the `songs/` folder; it will immediately show up in the game library!

---

## ⌨️ Controls & Shortcuts

| Key | Function |
| :--- | :--- |
| **MIDI Keyboard** | Plug and play! Velocity-sensitive real keys |
| **Z, S, X, D, C, V, G, B, H, N, J, M** | Lower Octave (C, C#, D, D#, E...) |
| **Q, 2, W, 3, E, R, 5, T, 6, Y, 7, U, I, 9, O** | Upper Octave |
| **[ / ] or , / .** | Shift octave down / up |
| **Space** | Play / Pause Song |
| **Tab** | Quickly switch to the next Sound Bank (.sf2) |
| **R** | Restart song from the beginning |
| **Left / Right Arrow** | Rewind / Fast-forward song by 3 seconds |
| **ESC** | Close open menu |
| **Mouse** | Play by clicking or sliding across keys (glissando) |

---

## 🚀 Installation & How to Run

### Prerequisites
Make sure you have **Python 3.8+** installed, then install the required dependencies:
```bash
pip install pygame numpy
```

### Running the Game
1. **Windows:** Double-click the **`run_game.bat`** file in Windows Explorer.
2. **All Platforms (Terminal / Command Prompt):**
   ```bash
   python main.py
   ```

Have fun! 🎶
(note my english isnt that good so i use ai for translation)
