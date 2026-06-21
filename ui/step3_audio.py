# This file handles audio settings or processing in the third step of the UI process.

class AudioSettings:
    def __init__(self):
        self.volume = 50  # Default volume level
        self.mute = False  # Mute status

    def set_volume(self, volume):
        if 0 <= volume <= 100:
            self.volume = volume
        else:
            raise ValueError("Volume must be between 0 and 100.")

    def toggle_mute(self):
        self.mute = not self.mute

    def get_audio_settings(self):
        return {
            "volume": self.volume,
            "mute": self.mute
        }

def display_audio_settings(audio_settings):
    settings = audio_settings.get_audio_settings()
    print(f"Volume: {settings['volume']}")
    print(f"Mute: {'On' if settings['mute'] else 'Off'}")