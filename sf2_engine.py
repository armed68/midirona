"""
Midirona - SoundFont 2 (SF2) Engine & Parser
Supports loading any standard .sf2 soundfont file, extracting PCM samples,
zone generators, key ranges, loop points, tuning, and synthesizing polyphonic audio.
"""

import os
import struct
import math
import numpy as np
import pygame

def pad_chunk(data):
    if len(data) % 2 != 0:
        return data + b'\x00'
    return data

def make_chunk(chunk_id, data):
    padded = pad_chunk(data)
    return chunk_id.encode('ascii')[:4] + struct.pack('<I', len(data)) + padded

def make_list(list_type, subchunks):
    payload = list_type.encode('ascii')[:4] + b''.join(subchunks)
    return make_chunk('LIST', payload)

def clean_text(raw, max_len=64):
    """Turns raw SF2/MIDI name bytes (or str) into a safe, printable string.
    SF2 name fields are fixed-width and usually padded with NUL + garbage bytes
    ("Piano\\0\\0Xq..."). Everything after the first NUL is dropped, and control
    characters are removed, because pygame's font renderer raises on them."""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).split(b'\x00', 1)[0]
        try:
            s = raw.decode('utf-8')
        except UnicodeDecodeError:
            s = raw.decode('latin-1')
    else:
        s = str(raw).split('\x00', 1)[0]
    s = ''.join(ch for ch in s if ch.isprintable())
    return s.strip()[:max_len]


def _iter_records(raw, fmt):
    size = struct.calcsize(fmt)
    n = len(raw) // size
    return list(struct.iter_unpack(fmt, raw[:n * size]))


class SF2Parser:
    """Parses SoundFont 2.x (.sf2) binary RIFF files. Never raises on malformed
    data: problems are reported through `self.error` and `is_valid`."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.presets = []
        self.instruments = []
        self.samples = []      # indexed EXACTLY like the shdr table (sampleID == index)
        self.raw_smpl = None
        self.info = {}
        self.version = (2, 0)
        self.error = None
        self.is_valid = False
        self.parse()

    def parse(self):
        if not os.path.exists(self.filepath):
            self.error = "File not found"
            return

        with open(self.filepath, 'rb') as f:
            data = f.read()

        if len(data) < 20 or data[:4] != b'RIFF' or data[8:12] != b'sfbk':
            self.error = "Not a valid SoundFont 2 (.sf2) file"
            return

        mv = memoryview(data)
        file_len = len(data)
        pdta_chunks = {}
        pos = 12

        while pos + 8 <= file_len:
            chunk_id = bytes(mv[pos:pos + 4]).decode('ascii', errors='ignore')
            chunk_size = struct.unpack_from('<I', data, pos + 4)[0]
            body_start = pos + 8
            body_end = min(file_len, body_start + chunk_size)
            pos = body_start + chunk_size + (chunk_size & 1)
            if chunk_id != 'LIST' or body_end - body_start < 4:
                continue

            list_type = bytes(mv[body_start:body_start + 4]).decode('ascii', errors='ignore')
            sub = body_start + 4
            while sub + 8 <= body_end:
                sub_id = bytes(mv[sub:sub + 4]).decode('ascii', errors='ignore')
                sub_size = struct.unpack_from('<I', data, sub + 4)[0]
                p_start = sub + 8
                p_end = min(body_end, p_start + sub_size)
                sub = p_start + sub_size + (sub_size & 1)

                if list_type == 'INFO':
                    if sub_id == 'ifil' and p_end - p_start >= 4:
                        self.version = struct.unpack_from('<HH', data, p_start)
                    elif sub_id in ('INAM', 'isng', 'ICMT', 'ICOP'):
                        self.info[sub_id] = clean_text(bytes(mv[p_start:p_end]))
                elif list_type == 'sdta':
                    if sub_id == 'smpl':
                        n = (p_end - p_start) // 2   # tolerate an odd byte count
                        if n > 0:
                            self.raw_smpl = np.frombuffer(data, dtype='<i2', count=n, offset=p_start)
                elif list_type == 'pdta':
                    pdta_chunks[sub_id] = bytes(mv[p_start:p_end])

        if self.version[0] >= 3:
            self.error = "SF3 (compressed) SoundFonts are not supported - use an uncompressed .sf2"
            return
        if self.raw_smpl is None:
            self.error = "SoundFont contains no sample data"
            return

        self._parse_pdta(pdta_chunks)
        if not self.presets:
            self.error = "SoundFont contains no playable instruments"
        self.is_valid = bool(self.presets)

    # ------------------------------------------------------------------
    @staticmethod
    def _collect_zones(bags, gens, bag_start, bag_end, terminal_oper):
        """Returns (global_generators, [zone_generators...]) for bags[bag_start:bag_end].
        A zone is a 'real' zone if it ends in the terminal generator (sampleID for
        instruments, instrument for presets); a first zone without it is the global zone."""
        glob, zones = {}, []
        bag_end = min(bag_end, len(bags) - 1)
        for b in range(max(0, bag_start), bag_end):
            g0, g1 = bags[b][0], bags[b + 1][0]
            g = {}
            for k in range(g0, min(g1, len(gens))):
                oper, amt = gens[k]
                g[oper] = amt
            if terminal_oper in g:
                zones.append(g)
            elif b == bag_start:
                glob = g
        return glob, zones

    @staticmethod
    def _ranges(m):
        kr, vr = m.get(43), m.get(44)
        k = (kr & 0xFF, (kr >> 8) & 0xFF) if kr is not None else (0, 127)
        v = (vr & 0xFF, (vr >> 8) & 0xFF) if vr is not None else (0, 127)
        return k, v

    def _parse_pdta(self, chunks):
        n_raw = len(self.raw_smpl)

        # 1. Sample headers. Index in self.samples == sampleID used by zones.
        for i, rec in enumerate(_iter_records(chunks.get('shdr', b''), '<20sIIIIIBbHH')):
            name, start, end, ls, le, rate, key, corr, link, stype = rec
            name_s = clean_text(name, 20)
            end = min(end, n_raw)
            valid = (name_s != 'EOS' and start < end and end - start >= 8 and not (stype & 0x8000))
            ls = min(max(ls, start), end)
            le = min(max(le, start), end)
            self.samples.append({
                'id': i, 'name': name_s, 'valid': valid,
                'start': start, 'end': end, 'loopstart': ls, 'loopend': le,
                'rate': rate if 4000 <= rate <= 192000 else 44100,
                'root_key': key if key <= 127 else 60,
                'correction': corr, 'type': stype,
            })

        pgen = _iter_records(chunks.get('pgen', b''), '<Hh')
        pbag = _iter_records(chunks.get('pbag', b''), '<HH')
        igen = _iter_records(chunks.get('igen', b''), '<Hh')
        ibag = _iter_records(chunks.get('ibag', b''), '<HH')

        # 2. Instruments
        inst_recs = _iter_records(chunks.get('inst', b''), '<20sH')
        for idx in range(len(inst_recs) - 1):
            name, bag_start = inst_recs[idx]
            bag_end = inst_recs[idx + 1][1]
            glob, raw_zones = self._collect_zones(ibag, igen, bag_start, bag_end, 53)
            zones = []
            for zi, g in enumerate(raw_zones):
                m = {**glob, **g}
                sid = m[53] & 0xFFFF
                if sid >= len(self.samples) or not self.samples[sid]['valid']:
                    continue
                (kmin, kmax), (vmin, vmax) = self._ranges(m)
                root = m.get(58, -1)
                zones.append({
                    'uid': (idx, zi), 'sample_id': sid,
                    'key_min': kmin, 'key_max': kmax, 'vel_min': vmin, 'vel_max': vmax,
                    'root_key': root if 0 <= root <= 127 else None,
                    'coarse_tune': m.get(51, 0), 'fine_tune': m.get(52, 0),
                    'scale_tuning': m.get(56, 100), 'attenuation': m.get(48, 0),
                    'attack': m.get(34, -12000), 'loop_mode': m.get(54, 0) & 3,
                    'pan': m.get(17, 0),
                })
            self.instruments.append({'id': idx, 'name': clean_text(name, 20), 'zones': zones})

        # 3. Presets
        phdr = _iter_records(chunks.get('phdr', b''), '<20sHHHIII')
        all_presets = []
        for idx in range(len(phdr) - 1):
            name, preset, bank, bag_start = phdr[idx][:4]
            bag_end = phdr[idx + 1][3]
            glob, raw_zones = self._collect_zones(pbag, pgen, bag_start, bag_end, 41)
            zones = []
            for g in raw_zones:
                m = {**glob, **g}
                inst_id = m[41] & 0xFFFF
                if inst_id >= len(self.instruments) or not self.instruments[inst_id]['zones']:
                    continue
                (kmin, kmax), (vmin, vmax) = self._ranges(m)
                zones.append({'instrument': inst_id, 'key_min': kmin, 'key_max': kmax,
                              'vel_min': vmin, 'vel_max': vmax,
                              'coarse_tune': m.get(51, 0), 'fine_tune': m.get(52, 0),
                              'attenuation': m.get(48, 0)})
            all_presets.append({
                'name': clean_text(name, 20) or f"Preset {preset}",
                'preset': preset, 'bank': bank,
                'instruments': [z['instrument'] for z in zones],
                'zones': zones,
            })

        # Only list instruments that can actually make sound; keep bank/program order.
        playable = [p for p in all_presets if p['zones']]
        self.presets = sorted(playable, key=lambda p: (p['bank'], p['preset']))


class SF2Synthesizer:
    """Synthesizes audio notes using loaded SoundFont (.sf2) samples."""
    MAX_CACHE = 320          # max pre-rendered notes kept in memory
    MAX_NOTE_SECONDS = 5.0   # one-shot samples
    MAX_LOOP_SECONDS = 6.0   # looped samples are unrolled to this length

    def __init__(self, output_rate=44100):
        self.output_rate = output_rate
        self.parser = None
        self.preset_idx = 0
        self.active_sf2_name = "None"
        self.active_sf2_path = None
        self.last_error = None
        self.sound_cache = {}
        self.active_channels = {}  # note -> pygame.mixer.Channel
        self.sustain_pedal = False
        self.sustained_notes = set()
        self.audio_ok = False
        self.mixer_channels = 2
        self._warned = set()
        self._init_mixer()

    def _init_mixer(self):
        """Make sure the mixer is 16-bit; adopt whatever sample rate the device gave us."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=self.output_rate, size=-16, channels=2, buffer=512)
            freq, size, ch = pygame.mixer.get_init()
            if size != -16 or ch not in (1, 2):
                pygame.mixer.quit()
                pygame.mixer.init(frequency=freq, size=-16, channels=2, buffer=512)
                freq, size, ch = pygame.mixer.get_init()
            self.output_rate, self.mixer_channels = freq, ch
            pygame.mixer.set_num_channels(64)
            self.audio_ok = True
        except Exception as e:
            print(f"[SF2] Audio device unavailable, running silent: {e}")
            self.audio_ok = False

    def _warn_once(self, key, msg):
        if key not in self._warned:
            self._warned.add(key)
            print(msg)

    def load_sf2(self, sf2_path):
        """Loads a new .sf2 soundfont. Returns True on success; on failure the
        previous soundfont stays active and `last_error` explains why."""
        self.last_error = None
        try:
            parser = SF2Parser(sf2_path)
        except Exception as e:   # includes MemoryError
            self.last_error = f"{type(e).__name__}: {e}"
            print(f"[SF2] Error loading {sf2_path}: {self.last_error}")
            return False

        if not parser.is_valid:
            self.last_error = parser.error or "Invalid or empty soundfont"
            print(f"[SF2] Cannot load {os.path.basename(sf2_path)}: {self.last_error}")
            return False

        self.stop_all()
        self.parser = parser
        self.preset_idx = 0
        self.active_sf2_path = sf2_path
        self.active_sf2_name = parser.info.get('INAM') or clean_text(os.path.splitext(os.path.basename(sf2_path))[0])
        self.sound_cache.clear()
        print(f"[SF2] Loaded soundfont: '{self.active_sf2_name}' with {len(parser.presets)} preset(s)")
        return True

    def get_preset_names(self):
        if not self.parser:
            return []
        return [f"{p['preset']:03d}: {p['name']}" for p in self.parser.presets]

    def set_preset(self, idx):
        if self.parser and 0 <= idx < len(self.parser.presets):
            self.preset_idx = idx
            self.sound_cache.clear()

    def set_sustain_pedal(self, pressed):
        self.sustain_pedal = pressed
        if not pressed:
            for note in list(self.sustained_notes):
                self._stop_note_channel(note)
            self.sustained_notes.clear()

    # ------------------------------------------------------------------
    def _select_zones(self, note, velocity):
        """Picks the sample zone(s) for this key/velocity (several = stereo pair / layers)."""
        preset = self.parser.presets[self.preset_idx]
        insts = self.parser.instruments

        def collect(check_vel):
            for pz in preset['zones']:
                if not (pz['key_min'] <= note <= pz['key_max']):
                    continue
                if check_vel and not (pz['vel_min'] <= velocity <= pz['vel_max']):
                    continue
                hits = [(iz, pz) for iz in insts[pz['instrument']]['zones']
                        if iz['key_min'] <= note <= iz['key_max']
                        and (not check_vel or iz['vel_min'] <= velocity <= iz['vel_max'])]
                if hits:
                    return hits[:4]
            return []

        hits = collect(True) or collect(False)
        if hits:
            return hits

        # Key outside every zone: use the zone whose key range is nearest.
        best, best_d = [], 1 << 30
        for pz in preset['zones']:
            for iz in insts[pz['instrument']]['zones']:
                d = max(iz['key_min'] - note, note - iz['key_max'], 0)
                if d < best_d:
                    best, best_d = [(iz, pz)], d
        return best

    def _render_zone(self, iz, pz, note):
        """Renders one sample zone to a float32 mono array (int16 scale) at the output rate."""
        sh = self.parser.samples[iz['sample_id']]
        raw = self.parser.raw_smpl
        start, end = sh['start'], sh['end']

        root = iz['root_key'] if iz['root_key'] is not None else sh['root_key']
        semis = ((note - root) * (iz['scale_tuning'] / 100.0)
                 + iz['coarse_tune'] + pz['coarse_tune']
                 + (iz['fine_tune'] + pz['fine_tune'] + sh['correction']) / 100.0)
        ratio = (2.0 ** (max(-72.0, min(72.0, semis)) / 12.0)) * (sh['rate'] / float(self.output_rate))
        ratio = min(max(ratio, 0.03), 48.0)

        looped = iz['loop_mode'] in (1, 3) and (sh['loopend'] - sh['loopstart']) >= 16
        if looped:
            ls, le = sh['loopstart'] - start, sh['loopend'] - start
            out_len = int(self.output_rate * self.MAX_LOOP_SECONDS)
            pos = np.arange(out_len, dtype=np.float64) * ratio
            over = pos >= le
            if over.any():
                pos[over] = ls + np.mod(pos[over] - ls, le - ls)
            last = le - 1
        else:
            n = end - start
            out_len = min(int(self.output_rate * self.MAX_NOTE_SECONDS), int((n - 2) / ratio))
            if out_len < 8:
                return None
            pos = np.arange(out_len, dtype=np.float64) * ratio
            last = n - 1

        i0 = pos.astype(np.int64)
        frac = (pos - i0).astype(np.float32)
        s0 = raw[start + i0].astype(np.float32)
        s1 = raw[start + np.minimum(i0 + 1, last)].astype(np.float32)
        out = s0 + (s1 - s0) * frac

        # Initial attenuation (centibels) -> linear gain
        att = min(max(iz['attenuation'] + pz['attenuation'], 0), 400)
        if att:
            out *= 10.0 ** (-att / 200.0)

        # Volume-envelope attack as a simple fade-in
        if iz['attack'] > -12000:
            atk_s = min(2.0 ** (iz['attack'] / 1200.0), 3.0)
            n_atk = min(len(out), int(atk_s * self.output_rate))
            if n_atk > 32:
                out[:n_atk] *= np.linspace(0.0, 1.0, n_atk, dtype=np.float32)

        fade = min(1024, len(out) // 2)
        if fade > 0:
            out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
        return out

    def _render_note_sound(self, note, zones):
        layers = []
        for iz, pz in zones:
            arr = self._render_zone(iz, pz, note)
            if arr is not None:
                layers.append((arr, iz))
        if not layers:
            return None

        n = max(len(a) for a, _ in layers)
        left = np.zeros(n, dtype=np.float32)
        right = np.zeros(n, dtype=np.float32)
        for arr, iz in layers:
            stype = self.parser.samples[iz['sample_id']]['type'] & 0x7FFF
            if stype == 4:      # left sample of a stereo pair
                gl, gr = 1.0, 0.0
            elif stype == 2:    # right sample
                gl, gr = 0.0, 1.0
            else:               # mono: honour the zone's pan (-500..500)
                p = min(max((iz['pan'] + 500) / 1000.0, 0.0), 1.0)
                gl, gr = math.cos(p * math.pi / 2), math.sin(p * math.pi / 2)
            left[:len(arr)] += arr * gl
            right[:len(arr)] += arr * gr

        pcm_l = np.clip(left, -32767, 32767).astype(np.int16)
        pcm_r = np.clip(right, -32767, 32767).astype(np.int16)
        if self.mixer_channels == 1:
            data = ((pcm_l.astype(np.int32) + pcm_r.astype(np.int32)) // 2).astype(np.int16)
        else:
            data = np.ascontiguousarray(np.column_stack((pcm_l, pcm_r)))
        return pygame.sndarray.make_sound(data)

    def note_on(self, note, velocity=100):
        """Triggers a note. Never raises: a broken sample must not take the game down."""
        if not self.audio_ok or not self.parser or not self.parser.presets:
            return
        try:
            zones = self._select_zones(note, velocity)
            if not zones:
                return
            cache_key = (self.preset_idx, note, tuple(iz['uid'] for iz, _ in zones))
            snd = self.sound_cache.get(cache_key)
            if snd is None:
                snd = self._render_note_sound(note, zones)
                if snd is None:
                    return
                if len(self.sound_cache) >= self.MAX_CACHE:
                    self.sound_cache.pop(next(iter(self.sound_cache)))
                self.sound_cache[cache_key] = snd

            if note in self.active_channels:
                self._stop_note_channel(note)   # retrigger: don't leave the old one ringing
            snd.set_volume(max(0.08, min(1.0, (velocity / 127.0) ** 1.35)))
            channel = snd.play()
            if channel:
                self.active_channels[note] = channel
            self.sustained_notes.discard(note)
        except Exception as e:
            self._warn_once(('note', type(e).__name__),
                            f"[SF2] Could not play note {note}: {type(e).__name__}: {e}")

    def note_off(self, note):
        """Triggers a note off event (or holds if sustain pedal is active)."""
        if self.sustain_pedal:
            self.sustained_notes.add(note)
        else:
            self._stop_note_channel(note)

    def _stop_note_channel(self, note):
        channel = self.active_channels.pop(note, None)
        try:
            if channel and channel.get_busy():
                channel.fadeout(120)
        except Exception:
            pass

    def stop_all(self):
        """Immediately halts all playing notes."""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass
        self.active_channels.clear()
        self.sustained_notes.clear()


# =============================================================================
# Built-in High-Quality SoundFont Generator
# Generates authentic, playable .sf2 files for Midirona
# =============================================================================

class SF2Writer:
    """Generates standard SoundFont 2.04 binary files."""
    def __init__(self, name="Midirona SoundFont"):
        self.name = name
        self.samples = []
        self.presets = []

    def add_sample(self, name, pcm_int16, sample_rate=44100, root_key=60, loop_start=None, loop_end=None):
        if loop_start is None:
            loop_start = 0
        if loop_end is None:
            loop_end = len(pcm_int16)
        idx = len(self.samples)
        self.samples.append({
            'name': name[:20],
            'data': pcm_int16,
            'rate': sample_rate,
            'root_key': root_key,
            'loop_start': loop_start,
            'loop_end': loop_end
        })
        return idx

    def add_preset(self, name, preset_num=0, bank=0, zones=None):
        if zones is None:
            zones = []
        self.presets.append({
            'name': name[:20],
            'preset_num': preset_num,
            'bank': bank,
            'zones': zones
        })

    def write(self, filepath):
        info_chunks = [
            make_chunk('ifil', struct.pack('<HH', 2, 4)),
            make_chunk('isng', b'EMU8000\x00'),
            make_chunk('INAM', self.name.encode('utf-8')[:20] + b'\x00')
        ]
        list_info = make_list('INFO', info_chunks)

        smpl_data = bytearray()
        sample_offsets = []
        for s in self.samples:
            smpl_data.extend(b'\x00' * 92)
            actual_start = len(smpl_data) // 2
            smpl_data.extend(s['data'].tobytes())
            actual_end = len(smpl_data) // 2
            smpl_data.extend(b'\x00' * 92)

            sample_offsets.append({
                'start': actual_start,
                'end': actual_end,
                'loopstart': actual_start + s['loop_start'],
                'loopend': actual_start + s['loop_end'],
                'rate': s['rate'],
                'root_key': s['root_key'],
                'name': s['name']
            })

        list_sdta = make_list('sdta', [make_chunk('smpl', bytes(smpl_data))])

        shdr_data = bytearray()
        for so in sample_offsets:
            name_bytes = so['name'].encode('ascii', errors='ignore')[:20].ljust(20, b'\x00')
            shdr_data.extend(struct.pack('<20sIIIIIBbHH',
                name_bytes, so['start'], so['end'], so['loopstart'], so['loopend'],
                so['rate'], so['root_key'], 0, 0, 1
            ))
        shdr_data.extend(struct.pack('<20sIIIIIBbHH', b'EOS\x00'.ljust(20, b'\x00'), 0,0,0,0,0,0,0,0,0))
        c_shdr = make_chunk('shdr', bytes(shdr_data))

        inst_data = bytearray()
        ibag_data = bytearray()
        igen_data = bytearray()

        current_igen = 0
        current_ibag = 0
        inst_headers = []

        for p_idx, p in enumerate(self.presets):
            inst_name = p['name'][:16] + "_inst"
            inst_headers.append((inst_name, current_ibag))

            for z in p['zones']:
                ibag_data.extend(struct.pack('<HH', current_igen, 0))
                current_ibag += 1

                key_min = z.get('key_min', 0)
                key_max = z.get('key_max', 127)
                igen_data.extend(struct.pack('<Hh', 43, (key_max << 8) | key_min))
                igen_data.extend(struct.pack('<Hh', 44, (127 << 8) | 0))

                count = 2
                if 'root_key' in z:
                    igen_data.extend(struct.pack('<Hh', 58, z['root_key']))
                    count += 1
                if 'attack' in z:
                    igen_data.extend(struct.pack('<Hh', 34, z['attack']))
                    count += 1
                if 'decay' in z:
                    igen_data.extend(struct.pack('<Hh', 36, z['decay']))
                    count += 1
                if 'sustain' in z:
                    igen_data.extend(struct.pack('<Hh', 37, z['sustain']))
                    count += 1
                if 'release' in z:
                    igen_data.extend(struct.pack('<Hh', 38, z['release']))
                    count += 1

                s_id = z.get('sample_idx', 0)
                igen_data.extend(struct.pack('<Hh', 53, s_id))
                count += 1
                current_igen += count

        ibag_data.extend(struct.pack('<HH', current_igen, 0))
        igen_data.extend(struct.pack('<Hh', 0, 0))

        for name, ibag_ndx in inst_headers:
            name_bytes = name.encode('ascii', errors='ignore')[:20].ljust(20, b'\x00')
            inst_data.extend(struct.pack('<20sH', name_bytes, ibag_ndx))
        inst_data.extend(struct.pack('<20sH', b'EOI\x00'.ljust(20, b'\x00'), current_ibag))

        phdr_data = bytearray()
        pbag_data = bytearray()
        pgen_data = bytearray()

        current_pgen = 0
        current_pbag = 0
        for p_idx, p in enumerate(self.presets):
            name_bytes = p['name'].encode('ascii', errors='ignore')[:20].ljust(20, b'\x00')
            phdr_data.extend(struct.pack('<20sHHHIII', name_bytes, p['preset_num'], p['bank'], current_pbag, 0, 0, 0))
            pbag_data.extend(struct.pack('<HH', current_pgen, 0))
            current_pbag += 1
            pgen_data.extend(struct.pack('<Hh', 41, p_idx))
            current_pgen += 1

        phdr_data.extend(struct.pack('<20sHHHIII', b'EOP\x00'.ljust(20, b'\x00'), 255, 0, current_pbag, 0, 0, 0))
        pbag_data.extend(struct.pack('<HH', current_pgen, 0))
        pgen_data.extend(struct.pack('<Hh', 0, 0))

        pmod_data = bytes(10)
        imod_data = bytes(10)

        c_phdr = make_chunk('phdr', bytes(phdr_data))
        c_pbag = make_chunk('pbag', bytes(pbag_data))
        c_pmod = make_chunk('pmod', pmod_data)
        c_pgen = make_chunk('pgen', bytes(pgen_data))
        c_inst = make_chunk('inst', bytes(inst_data))
        c_ibag = make_chunk('ibag', bytes(ibag_data))
        c_imod = make_chunk('imod', imod_data)
        c_igen = make_chunk('igen', bytes(igen_data))

        list_pdta = make_list('pdta', [c_phdr, c_pbag, c_pmod, c_pgen, c_inst, c_ibag, c_imod, c_igen, c_shdr])
        full_content = list_info + list_sdta + list_pdta
        riff_header = b'RIFF' + struct.pack('<I', len(full_content) + 4) + b'sfbk'

        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(riff_header)
            f.write(full_content)
        print(f"[SF2] Generated SoundFont: {filepath}")


def generate_bundled_soundfonts(output_dir="soundfonts"):
    """Creates a suite of distinct, beautiful .sf2 soundfont files."""
    os.makedirs(output_dir, exist_ok=True)
    sr = 44100

    # 1. Concert Grand Piano
    piano_path = os.path.join(output_dir, "01_Grand_Piano.sf2")
    if not os.path.exists(piano_path):
        writer = SF2Writer("Concert Grand Piano")
        # Multi-sample roots across octaves: C2 (36), C3 (48), C4 (60), C5 (72), C6 (84)
        roots = [(36, 65.41), (48, 130.81), (60, 261.63), (72, 523.25), (84, 1046.50)]
        sample_indices = []
        for key, freq in roots:
            dur = 2.2 if key < 60 else (1.8 if key < 75 else 1.2)
            t = np.linspace(0, dur, int(sr * dur), False)
            # Piano harmonic spectrum: fundamental + decay harmonics + hammer transient
            decay_rate = 1.6 + (key / 35.0)
            env = np.exp(-decay_rate * t)
            hammer = np.exp(-60.0 * t) * np.sin(2 * np.pi * 3200 * t) * 0.25
            sig = (
                1.00 * np.sin(2 * np.pi * freq * t) +
                0.55 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-decay_rate * 1.3 * t) +
                0.28 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-decay_rate * 1.8 * t) +
                0.14 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-decay_rate * 2.4 * t) +
                0.07 * np.sin(2 * np.pi * 5 * freq * t) * np.exp(-decay_rate * 3.0 * t) +
                hammer
            )
            pcm = (sig / np.max(np.abs(sig) + 1e-6) * 26000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"Piano_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 42, 'sample_idx': sample_indices[0][1], 'root_key': 36},
            {'key_min': 43, 'key_max': 54, 'sample_idx': sample_indices[1][1], 'root_key': 48},
            {'key_min': 55, 'key_max': 66, 'sample_idx': sample_indices[2][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 78, 'sample_idx': sample_indices[3][1], 'root_key': 72},
            {'key_min': 79, 'key_max': 127, 'sample_idx': sample_indices[4][1], 'root_key': 84},
        ]
        writer.add_preset("Concert Grand Piano", preset_num=0, bank=0, zones=zones)
        writer.write(piano_path)

    # 2. Electric Piano (Vintage Rhodes / Chime)
    ep_path = os.path.join(output_dir, "02_Electric_Piano.sf2")
    if not os.path.exists(ep_path):
        writer = SF2Writer("Electric Piano")
        roots = [(48, 130.81), (60, 261.63), (72, 523.25), (84, 1046.50)]
        sample_indices = []
        for key, freq in roots:
            dur = 2.0
            t = np.linspace(0, dur, int(sr * dur), False)
            env = np.exp(-2.2 * t)
            # Rhodes tine: metallic high chime + round sine fundamental + tremolo/vibrato
            tine = np.exp(-25.0 * t) * np.sin(2 * np.pi * freq * 7.0 * t) * 0.4
            sig = (
                1.00 * np.sin(2 * np.pi * freq * t) +
                0.35 * np.sin(2 * np.pi * 2 * freq * t) +
                0.12 * np.sin(2 * np.pi * 3 * freq * t) +
                tine
            )
            pcm = (sig / np.max(np.abs(sig) + 1e-6) * 25000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"EP_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 54, 'sample_idx': sample_indices[0][1], 'root_key': 48},
            {'key_min': 55, 'key_max': 66, 'sample_idx': sample_indices[1][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 78, 'sample_idx': sample_indices[2][1], 'root_key': 72},
            {'key_min': 79, 'key_max': 127, 'sample_idx': sample_indices[3][1], 'root_key': 84},
        ]
        writer.add_preset("Stage Electric Piano", preset_num=0, bank=0, zones=zones)
        writer.write(ep_path)

    # 3. 8-Bit Chiptune / Retro Pulse
    chip_path = os.path.join(output_dir, "03_Chiptune_8Bit.sf2")
    if not os.path.exists(chip_path):
        writer = SF2Writer("8-Bit Chiptune")
        roots = [(48, 130.81), (60, 261.63), (72, 523.25)]
        sample_indices = []
        for key, freq in roots:
            dur = 1.4
            t = np.linspace(0, dur, int(sr * dur), False)
            # 25% duty cycle square wave + vibrato
            phase = (2 * np.pi * freq * t) % (2 * np.pi)
            sq = np.where(phase < 0.5 * np.pi, 1.0, -1.0)
            env = np.exp(-2.8 * t)
            pcm = (sq * 18000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"Chip_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 54, 'sample_idx': sample_indices[0][1], 'root_key': 48},
            {'key_min': 55, 'key_max': 66, 'sample_idx': sample_indices[1][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 127, 'sample_idx': sample_indices[2][1], 'root_key': 72},
        ]
        writer.add_preset("8-Bit Pulse Lead", preset_num=0, bank=0, zones=zones)
        writer.write(chip_path)

    # 4. Dream Synth Pad (Atmospheric ambient pad)
    pad_path = os.path.join(output_dir, "04_Dream_Synth_Pad.sf2")
    if not os.path.exists(pad_path):
        writer = SF2Writer("Dream Synth Pad")
        roots = [(48, 130.81), (60, 261.63), (72, 523.25)]
        sample_indices = []
        for key, freq in roots:
            dur = 2.5
            t = np.linspace(0, dur, int(sr * dur), False)
            # Warm detuned supersaw / chorus pad with soft attack
            attack_len = int(sr * 0.15)
            attack = np.linspace(0.0, 1.0, attack_len)
            decay = np.exp(-1.2 * (t[attack_len:] - t[attack_len]))
            env = np.concatenate([attack, decay])
            f1, f2, f3 = freq * 0.996, freq * 1.000, freq * 1.004
            sig = np.sin(2*np.pi*f1*t) + np.sin(2*np.pi*f2*t) + np.sin(2*np.pi*f3*t)
            pcm = (sig / 3.0 * 24000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"Pad_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 54, 'sample_idx': sample_indices[0][1], 'root_key': 48},
            {'key_min': 55, 'key_max': 66, 'sample_idx': sample_indices[1][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 127, 'sample_idx': sample_indices[2][1], 'root_key': 72},
        ]
        writer.add_preset("Atmospheric Dream Pad", preset_num=0, bank=0, zones=zones)
        writer.write(pad_path)

    # 5. Harpsichord (Baroque plucked string)
    harp_path = os.path.join(output_dir, "05_Harpsichord.sf2")
    if not os.path.exists(harp_path):
        writer = SF2Writer("Harpsichord")
        roots = [(48, 130.81), (60, 261.63), (72, 523.25)]
        sample_indices = []
        for key, freq in roots:
            dur = 1.6
            t = np.linspace(0, dur, int(sr * dur), False)
            env = np.exp(-3.5 * t)
            # Sharp plucked harmonics
            sig = sum((1.0 / n) * np.sin(2 * np.pi * n * freq * t) for n in range(1, 9))
            pcm = (sig / np.max(np.abs(sig) + 1e-6) * 23000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"Harp_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 54, 'sample_idx': sample_indices[0][1], 'root_key': 48},
            {'key_min': 55, 'key_max': 66, 'sample_idx': sample_indices[1][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 127, 'sample_idx': sample_indices[2][1], 'root_key': 72},
        ]
        writer.add_preset("Baroque Harpsichord", preset_num=0, bank=0, zones=zones)
        writer.write(harp_path)

    # 6. Music Box (Magical bell chimes)
    mb_path = os.path.join(output_dir, "06_Music_Box.sf2")
    if not os.path.exists(mb_path):
        writer = SF2Writer("Music Box")
        roots = [(60, 261.63), (72, 523.25), (84, 1046.50)]
        sample_indices = []
        for key, freq in roots:
            dur = 2.0
            t = np.linspace(0, dur, int(sr * dur), False)
            env = np.exp(-2.5 * t)
            sig = (
                1.00 * np.sin(2 * np.pi * freq * t) +
                0.60 * np.sin(2 * np.pi * 3.0 * freq * t) * np.exp(-4.0 * t) +
                0.25 * np.sin(2 * np.pi * 5.4 * freq * t) * np.exp(-6.0 * t)
            )
            pcm = (sig / np.max(np.abs(sig) + 1e-6) * 25000 * env).astype(np.int16)
            s_idx = writer.add_sample(f"MB_K{key}", pcm, sample_rate=sr, root_key=key)
            sample_indices.append((key, s_idx))

        zones = [
            {'key_min': 0, 'key_max': 66, 'sample_idx': sample_indices[0][1], 'root_key': 60},
            {'key_min': 67, 'key_max': 78, 'sample_idx': sample_indices[1][1], 'root_key': 72},
            {'key_min': 79, 'key_max': 127, 'sample_idx': sample_indices[2][1], 'root_key': 84},
        ]
        writer.add_preset("Celestial Music Box", preset_num=0, bank=0, zones=zones)
        writer.write(mb_path)

    print("[SF2] All bundled soundfonts generated successfully!")
