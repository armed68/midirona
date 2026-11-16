
import os
import struct

class Note:
    def __init__(self, pitch, start_time, end_time, velocity=100, channel=0, track=0):
        self.pitch = pitch              
        self.start_time = start_time    
        self.end_time = end_time        
        self.duration = max(0.05, end_time - start_time)
        self.velocity = velocity        
        self.channel = channel
        self.track = track
        self.hand = 'left' if pitch < 60 else 'right'
        
        
        self.hit = False
        self.missed = False
        self.hit_time = None
        self.active_playing = False

    def __repr__(self):
        return f"<Note pitch={self.pitch} start={self.start_time:.2f}s dur={self.duration:.2f}s hand={self.hand}>"


class MidiSong:
    def __init__(self, title="Untitled", filename=""):
        self.title = title
        self.filename = filename
        self.notes = []             
        self.duration = 0.0         
        self.min_key = 21           
        self.max_key = 108          
        self.tempo_bpm = 120.0
        self.tracks_count = 0
        self.time_signature = (4, 4)

    def sort_notes(self):
        self.notes.sort(key=lambda n: (n.start_time, n.pitch))
        if self.notes:
            self.duration = max(n.end_time for n in self.notes)
            self.min_key = max(21, min(n.pitch for n in self.notes) - 2)
            self.max_key = min(108, max(n.pitch for n in self.notes) + 2)

    def reset_state(self):
        for n in self.notes:
            n.hit = False
            n.missed = False
            n.hit_time = None
            n.active_playing = False


def _read_varlen(data, pos):
    val = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return val, pos


def parse_midi_file(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"MIDI file not found: {filepath}")

    with open(filepath, 'rb') as f:
        raw = f.read()

    if len(raw) < 14 or raw[:4] != b'MThd':
        raise ValueError(f"Invalid MIDI header in {filepath}")

    length, fmt, ntracks, division = struct.unpack('>IHHH', raw[4:14])
    is_smpte = bool(division & 0x8000)
    ticks_per_beat = division if not is_smpte else 480

    pos = 14
    raw_tracks = []
    while pos < len(raw) - 8:
        if raw[pos:pos+4] == b'MTrk':
            trk_len = struct.unpack('>I', raw[pos+4:pos+8])[0]
            trk_data = raw[pos+8:pos+8+trk_len]
            raw_tracks.append(trk_data)
            pos += 8 + trk_len
        else:
            pos += 1

    
    
    all_events = []
    song_title = os.path.splitext(os.path.basename(filepath))[0].replace('_', ' ').title()

    for trk_idx, trk_data in enumerate(raw_tracks):
        trk_pos = 0
        current_tick = 0
        running_status = None
        trk_len = len(trk_data)

        while trk_pos < trk_len:
            delta, trk_pos = _read_varlen(trk_data, trk_pos)
            current_tick += delta

            if trk_pos >= trk_len:
                break

            status = trk_data[trk_pos]
            if status >= 0x80:
                running_status = status
                trk_pos += 1
            else:
                status = running_status
                if status is None:
                    trk_pos += 1
                    continue

            ev_type = status & 0xF0
            channel = status & 0x0F

            if status == 0xFF:  
                if trk_pos >= trk_len:
                    break
                meta_type = trk_data[trk_pos]
                trk_pos += 1
                meta_len, trk_pos = _read_varlen(trk_data, trk_pos)
                meta_data = trk_data[trk_pos:trk_pos+meta_len]
                trk_pos += meta_len

                if meta_type == 0x51 and len(meta_data) >= 3:  
                    mpqn = (meta_data[0] << 16) | (meta_data[1] << 8) | meta_data[2]
                    all_events.append((current_tick, 'tempo', mpqn))
                elif meta_type == 0x03 and meta_data:  
                    try:
                        name = meta_data.split(b'\x00', 1)[0].decode('utf-8', errors='ignore').strip()
                        name = ''.join(ch for ch in name if ch.isprintable())
                        if name and trk_idx == 0:
                            song_title = name
                    except Exception:
                        pass
                elif meta_type == 0x2F:  
                    break

            elif status in (0xF0, 0xF7):  
                sys_len, trk_pos = _read_varlen(trk_data, trk_pos)
                trk_pos += sys_len

            elif ev_type in (0x80, 0x90):  
                if trk_pos + 1 >= trk_len:
                    break
                note = trk_data[trk_pos]
                vel = trk_data[trk_pos+1]
                trk_pos += 2
                is_on = (ev_type == 0x90) and (vel > 0)
                all_events.append((current_tick, 'note', (is_on, note, vel, channel, trk_idx)))

            elif ev_type in (0xA0, 0xB0, 0xE0):
                trk_pos += 2
            elif ev_type in (0xC0, 0xD0):
                trk_pos += 1

    
    all_events.sort(key=lambda ev: ev[0])

    
    tempo_map = []  
    current_tick = 0
    current_time = 0.0
    current_mpqn = 500000  

    for ev in all_events:
        tick = ev[0]
        if tick > current_tick:
            delta_ticks = tick - current_tick
            seconds = (delta_ticks * current_mpqn) / (ticks_per_beat * 1_000_000.0)
            current_time += seconds
            current_tick = tick

        if ev[1] == 'tempo':
            current_mpqn = ev[2]
            tempo_map.append((tick, current_time, current_mpqn))

    def tick_to_seconds(target_tick):
        t = 0.0
        last_tick = 0
        mpqn = 500000
        for map_tick, map_time, map_mpqn in tempo_map:
            if target_tick <= map_tick:
                delta = target_tick - last_tick
                return t + (delta * mpqn) / (ticks_per_beat * 1_000_000.0)
            delta = map_tick - last_tick
            t += (delta * mpqn) / (ticks_per_beat * 1_000_000.0)
            last_tick = map_tick
            mpqn = map_mpqn
        delta = target_tick - last_tick
        return t + (delta * mpqn) / (ticks_per_beat * 1_000_000.0)

    
    open_notes = {}  
    finished_notes = []

    for ev in all_events:
        if ev[1] != 'note':
            continue
        tick = ev[0]
        is_on, pitch, vel, channel, trk_idx = ev[2]
        key = (channel, pitch)

        if is_on:
            if key not in open_notes:
                open_notes[key] = []
            open_notes[key].append((tick, vel, trk_idx))
        else:
            if key in open_notes and open_notes[key]:
                start_tick, start_vel, start_trk = open_notes[key].pop(0)
                start_sec = tick_to_seconds(start_tick)
                end_sec = tick_to_seconds(tick)
                if end_sec > start_sec + 0.02:
                    finished_notes.append(Note(pitch, start_sec, end_sec, start_vel, channel, start_trk))

    
    for key, pending in open_notes.items():
        channel, pitch = key
        for start_tick, start_vel, start_trk in pending:
            start_sec = tick_to_seconds(start_tick)
            finished_notes.append(Note(pitch, start_sec, start_sec + 0.5, start_vel, channel, start_trk))

    song = MidiSong(song_title, filepath)
    song.notes = finished_notes
    song.tracks_count = len(raw_tracks)
    song.tempo_bpm = round(60_000_000.0 / current_mpqn, 1)
    song.sort_notes()

    
    tracks_used = set(n.track for n in song.notes)
    if len(tracks_used) >= 2:
        min_trk = min(tracks_used)
        for n in song.notes:
            n.hand = 'right' if n.track == min_trk else 'left'
    else:
        for n in song.notes:
            n.hand = 'left' if n.pitch < 60 else 'right'

    return song
