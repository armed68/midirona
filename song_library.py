"""
Midirona - Song Library Manager & Built-in Classical Songs Generator
Manages songs folder, parses MIDI files, and provides ready-to-play classical masterpieces.
"""

import os
import struct
from midi_parser import parse_midi_file

def _write_varlen(val):
    buf = bytearray()
    buf.append(val & 0x7F)
    val >>= 7
    while val > 0:
        buf.insert(0, (val & 0x7F) | 0x80)
        val >>= 7
    return bytes(buf)

class SimpleMidiBuilder:
    def __init__(self, bpm=120, tpq=480):
        self.bpm = bpm
        self.tpq = tpq
        self.events = []  # (tick, bytes)
        self.cursor = 0
        self.set_tempo(0, bpm)

    def set_tempo(self, tick, bpm):
        mpqn = int(60_000_000 / bpm)
        ev = bytes([0xFF, 0x51, 0x03, (mpqn >> 16) & 0xFF, (mpqn >> 8) & 0xFF, mpqn & 0xFF])
        self.events.append((tick, ev))

    def add_note(self, note, duration_beats, velocity=95, channel=0):
        start_tick = self.cursor
        dur_ticks = int(duration_beats * self.tpq)
        end_tick = start_tick + dur_ticks

        # Note On
        self.events.append((start_tick, bytes([0x90 | (channel & 0x0F), note & 0x7F, velocity & 0x7F])))
        # Note Off
        self.events.append((end_tick, bytes([0x80 | (channel & 0x0F), note & 0x7F, 0])))
        self.cursor += dur_ticks

    def add_chord(self, notes, duration_beats, velocity=90, channel=0):
        start_tick = self.cursor
        dur_ticks = int(duration_beats * self.tpq)
        end_tick = start_tick + dur_ticks

        for n in notes:
            self.events.append((start_tick, bytes([0x90 | (channel & 0x0F), n & 0x7F, velocity & 0x7F])))
            self.events.append((end_tick, bytes([0x80 | (channel & 0x0F), n & 0x7F, 0])))
        self.cursor += dur_ticks

    def rest(self, duration_beats):
        self.cursor += int(duration_beats * self.tpq)

    def save(self, filepath, title="Untitled"):
        self.events.sort(key=lambda x: x[0])
        trk_bytes = bytearray()

        # Track name
        t_bytes = title.encode('utf-8')
        trk_bytes += bytes([0x00, 0xFF, 0x03]) + _write_varlen(len(t_bytes)) + t_bytes

        last_tick = 0
        for tick, data in self.events:
            delta = max(0, tick - last_tick)
            trk_bytes += _write_varlen(delta)
            trk_bytes += data
            last_tick = tick

        # End of track
        trk_bytes += bytes([0x00, 0xFF, 0x2F, 0x00])

        with open(filepath, 'wb') as f:
            f.write(b'MThd')
            f.write(struct.pack('>IHHH', 6, 0, 1, self.tpq))
            f.write(b'MTrk')
            f.write(struct.pack('>I', len(trk_bytes)))
            f.write(trk_bytes)


def create_builtin_songs(songs_dir="songs"):
    os.makedirs(songs_dir, exist_ok=True)

    # 1. Für Elise (Beethoven)
    fe_path = os.path.join(songs_dir, "01_Fur_Elise.mid")
    if not os.path.exists(fe_path):
        b = SimpleMidiBuilder(bpm=136)
        # E5, D#5, E5, D#5, E5, B4, D5, C5, A4
        theme = [
            (76, 0.5), (75, 0.5), (76, 0.5), (75, 0.5), (76, 0.5),
            (71, 0.5), (74, 0.5), (72, 0.5), (69, 1.0)
        ]
        # Left hand arpeggios + continuation
        for _ in range(2):
            for pitch, dur in theme:
                b.add_note(pitch, dur)
            # C4, E4, A4, B4
            for n, d in [(48, 0.5), (52, 0.5), (57, 0.5), (59, 1.0)]:
                b.add_note(n, d)
            # E4, G#4, B4, C5
            for n, d in [(52, 0.5), (56, 0.5), (59, 0.5), (60, 1.0)]:
                b.add_note(n, d)
            # Repeat opening
            for pitch, dur in theme:
                b.add_note(pitch, dur)
            for n, d in [(48, 0.5), (52, 0.5), (57, 0.5), (59, 1.0)]:
                b.add_note(n, d)
            for n, d in [(52, 0.5), (60, 0.5), (59, 0.5), (57, 1.5)]:
                b.add_note(n, d)
        b.save(fe_path, "Für Elise - L. v. Beethoven")

    # 2. Moonlight Sonata (Beethoven)
    ms_path = os.path.join(songs_dir, "02_Moonlight_Sonata.mid")
    if not os.path.exists(ms_path):
        b = SimpleMidiBuilder(bpm=58)
        # Iconic C# minor triplets: G#3, C#4, E4
        for _ in range(4):
            for _ in range(4):
                b.add_note(56, 0.33)  # G#3
                b.add_note(61, 0.33)  # C#4
                b.add_note(64, 0.33)  # E4
        # Add melody over triplets
        b.save(ms_path, "Moonlight Sonata - L. v. Beethoven")

    # 3. Canon in D (Pachelbel)
    canon_path = os.path.join(songs_dir, "03_Canon_in_D.mid")
    if not os.path.exists(canon_path):
        b = SimpleMidiBuilder(bpm=72)
        # Bass progression: D, A, B, F#, G, D, G, A
        # Melody: F#5, E5, D5, C#5, B4, A4, B4, C#5
        melody = [
            74, 73, 71, 69, 67, 66, 67, 69,
            74, 76, 78, 79, 78, 76, 78, 81
        ]
        for note in melody:
            b.add_note(note, 1.0)
            b.add_note(note - 12, 0.5)
            b.add_note(note - 10, 0.5)
        b.save(canon_path, "Canon in D - J. Pachelbel")

    # 4. Rondo Alla Turca (Mozart)
    turca_path = os.path.join(songs_dir, "04_Rondo_Alla_Turca.mid")
    if not os.path.exists(turca_path):
        b = SimpleMidiBuilder(bpm=128)
        # B4, A4, G#4, A4, C5
        for _ in range(2):
            for n in [71, 69, 68, 69]:
                b.add_note(n, 0.25)
            b.add_note(72, 1.0)
            for n in [74, 72, 71, 72]:
                b.add_note(n, 0.25)
            b.add_note(76, 1.0)
            for n in [77, 76, 74, 76, 77, 76, 74, 76]:
                b.add_note(n, 0.25)
            b.add_note(81, 1.0)
        b.save(turca_path, "Rondo Alla Turca - W. A. Mozart")

    # 5. Gymnopédie No. 1 (Erik Satie)
    satie_path = os.path.join(songs_dir, "05_Gymnopedie_No1.mid")
    if not os.path.exists(satie_path):
        b = SimpleMidiBuilder(bpm=66)
        # G4, F#4, G4, F#4, B3, D4
        chords = [
            ([43, 62, 66, 69], 2.0),
            ([38, 60, 64, 67], 2.0),
            ([43, 62, 66, 69], 2.0),
            ([38, 60, 64, 67], 2.0),
        ]
        for c, dur in chords:
            b.add_chord(c, dur)
        # Melody notes
        melody = [71, 69, 71, 69, 59, 62, 64, 66]
        for m in melody:
            b.add_note(m, 1.5)
        b.save(satie_path, "Gymnopédie No. 1 - E. Satie")

    # 6. Twinkle Twinkle Little Star (Beginner)
    twinkle_path = os.path.join(songs_dir, "06_Twinkle_Twinkle.mid")
    if not os.path.exists(twinkle_path):
        b = SimpleMidiBuilder(bpm=100)
        # C C G G A A G - F F E E D D C
        tune = [
            (60, 1.0), (60, 1.0), (67, 1.0), (67, 1.0), (69, 1.0), (69, 1.0), (67, 2.0),
            (65, 1.0), (65, 1.0), (64, 1.0), (64, 1.0), (62, 1.0), (62, 1.0), (60, 2.0),
            (67, 1.0), (67, 1.0), (65, 1.0), (65, 1.0), (64, 1.0), (64, 1.0), (62, 2.0),
            (67, 1.0), (67, 1.0), (65, 1.0), (65, 1.0), (64, 1.0), (64, 1.0), (62, 2.0),
            (60, 1.0), (60, 1.0), (67, 1.0), (67, 1.0), (69, 1.0), (69, 1.0), (67, 2.0),
            (65, 1.0), (65, 1.0), (64, 1.0), (64, 1.0), (62, 1.0), (62, 1.0), (60, 2.0),
        ]
        for p, d in tune:
            b.add_note(p, d)
        b.save(twinkle_path, "Twinkle Twinkle Little Star")

    print("[Songs] Built-in songs verified in folder:", songs_dir)


class SongLibrary:
    """Discovers, parses, and provides access to songs in songs/ directory."""
    def __init__(self, songs_dir="songs"):
        self.songs_dir = songs_dir
        self.songs_list = []  # list of dicts: {'path', 'filename', 'title', 'parsed_song'}
        self.current_idx = 0
        create_builtin_songs(songs_dir)
        self.rescan()

    def rescan(self):
        self.songs_list.clear()
        if not os.path.exists(self.songs_dir):
            return

        for fname in sorted(os.listdir(self.songs_dir)):
            if fname.lower().endswith(('.mid', '.midi')):
                fpath = os.path.join(self.songs_dir, fname)
                title = os.path.splitext(fname)[0].replace('_', ' ')
                # Remove leading numbers like "01 "
                if len(title) > 3 and title[:2].isdigit():
                    title = title[3:].strip()
                self.songs_list.append({
                    'path': fpath,
                    'filename': fname,
                    'title': title,
                    'song': None  # Loaded on demand
                })
        print(f"[SongLibrary] Found {len(self.songs_list)} song(s).")

    def get_song(self, index):
        if not self.songs_list:
            return None
        index = max(0, min(index, len(self.songs_list) - 1))
        item = self.songs_list[index]
        if item['song'] is None:
            try:
                item['song'] = parse_midi_file(item['path'])
            except Exception as e:
                print(f"[SongLibrary] Error parsing {item['filename']}: {e}")
                return None
        self.current_idx = index
        return item['song']

    def get_current_song(self):
        return self.get_song(self.current_idx)
