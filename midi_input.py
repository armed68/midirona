
import pygame
import pygame.midi

class MidiInputManager:
    def __init__(self):
        self.midi_input = None
        self.device_id = None
        self.device_name = "None"
        self.available_devices = []  
        self._init_midi()

    def _init_midi(self):
        try:
            if not pygame.midi.get_init():
                pygame.midi.init()
            self.refresh_devices()
            self.auto_connect()
        except Exception as e:
            print(f"[MIDI] Error initializing pygame.midi: {e}")

    def refresh_devices(self):
        self.available_devices.clear()
        try:
            count = pygame.midi.get_count()
            for i in range(count):
                info = pygame.midi.get_device_info(i)
                
                if info and info[2] == 1:  
                    raw_name = info[1]
                    name_str = raw_name.decode('utf-8', errors='ignore') if isinstance(raw_name, bytes) else str(raw_name)
                    name_str = ''.join(ch for ch in name_str.split('\x00', 1)[0] if ch.isprintable()).strip() or f"MIDI device {i}"
                    self.available_devices.append((i, name_str))
            print(f"[MIDI] Found {len(self.available_devices)} input device(s): {self.available_devices}")
        except Exception as e:
            print(f"[MIDI] Error enumerating devices: {e}")

    def auto_connect(self):
        if not self.available_devices:
            print("[MIDI] No MIDI input devices found. Using computer keyboard/mouse.")
            return False

        
        target_id = self.available_devices[0][0]
        for dev_id, name in self.available_devices:
            lname = name.lower()
            if any(k in lname for k in ('keystep', 'arturia', 'akai', 'novation', 'korg', 'yamaha', 'roland')):
                target_id = dev_id
                break

        return self.connect(target_id)

    def connect(self, device_id):
        self.disconnect()
        try:
            self.midi_input = pygame.midi.Input(device_id)
            self.device_id = device_id
            for dev_id, name in self.available_devices:
                if dev_id == device_id:
                    self.device_name = name
                    break
            print(f"[MIDI] Connected to '{self.device_name}' (ID: {device_id})")
            return True
        except Exception as e:
            print(f"[MIDI] Failed to connect to device {device_id}: {e}")
            self.midi_input = None
            self.device_id = None
            self.device_name = "None"
            return False

    def disconnect(self):
        if self.midi_input:
            try:
                self.midi_input.close()
            except Exception:
                pass
            self.midi_input = None
            self.device_id = None
            self.device_name = "None"

    def poll_events(self):
        if not self.midi_input:
            return

        try:
            while self.midi_input.poll():
                midi_events = self.midi_input.read(16)
                for event in midi_events:
                    data = event[0]  
                    status = data[0]
                    ev_type = status & 0xF0

                    if ev_type == 0x90:  
                        pitch = data[1]
                        vel = data[2]
                        if vel > 0:
                            yield ('note_on', pitch, vel)
                        else:
                            yield ('note_off', pitch, 0)
                    elif ev_type == 0x80:  
                        pitch = data[1]
                        yield ('note_off', pitch, 0)
                    elif ev_type == 0xB0:  
                        controller = data[1]
                        val = data[2]
                        if controller == 64:  
                            yield ('sustain', val >= 64, val)
                    elif ev_type == 0xE0:  
                        bend = (data[2] << 7) | data[1]
                        yield ('pitch_bend', bend - 8192, 0)
        except Exception as e:
            
            pass

    def close(self):
        self.disconnect()
        try:
            if pygame.midi.get_init():
                pygame.midi.quit()
        except Exception:
            pass
