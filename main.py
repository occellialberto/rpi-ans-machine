import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from player import play_audio, stop_audio

try:
    import RPi.GPIO as GPIO
except RuntimeError:
    # Running without root may raise a RuntimeError – GPIO calls will then fail.
    print("Warning: GPIO access might require root privileges.")

# ---------------------------------------------------------------------------#
# Configuration                                                              #
# ---------------------------------------------------------------------------#
PIN = 14                                   # GPIO pin to monitor (BCM scheme)
MESSAGE_FILE = "message.wav"      # Audio message to be reproduced
RECORD_DIR = Path("recordings")   # Directory where recordings land
# Use PulseAudio’s recorder. “--format=cd --file-format=wav” is the closest
# equivalent to the old “arecord -q -f cd -t wav”.
RECORD_CMD = [
    "parecord",
    "--rate=16000",
    "--channels=1",
    "--format=s16le",
    "--device=bluez_source.00_16_94_24_F3_F8.handsfree_head_unit",
    "--file-format=wav"
]
POLL_DELAY = 0.02                          # Seconds between GPIO polls
# ---------------------------------------------------------------------------#


def setup_gpio() -> None:
    """
    Prepare the GPIO subsystem.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def read_gpio() -> int:
    """
    Read the monitored pin.
    Returns 0 (LOW) or 1 (HIGH).
    """
    return GPIO.input(PIN)


# ---------------------------------------------------------------------------#
# Playback helper                                                            #
# ---------------------------------------------------------------------------#
def _play_message(blocking: bool = False) -> threading.Thread:
    """
    Play MESSAGE_FILE and return a Thread that finishes when playback ends.
    If `blocking=True` the function itself will not return until the audio
    has been played, but the returned object is still a dummy Thread.
    """
    if blocking:
        play_audio(MESSAGE_FILE, blocking=True)
        return threading.current_thread()  # never queried
    thread = threading.Thread(
        target=play_audio,
        args=(MESSAGE_FILE,),
        kwargs={"blocking": True},  # inside thread: blocking; outside: non-blocking
        daemon=True,
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------------#
# Recording helper                                                           #
# ---------------------------------------------------------------------------#
class Recorder:
    """
    Minimal wrapper around a recording subprocess (e.g. `parecord`).
    """
    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen[str]] = None
        self.file: Optional[Path] = None

    def start(self) -> None:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file = RECORD_DIR / f"call_{timestamp}.wav"
        cmd = [*RECORD_CMD, str(self.file)]
        self.proc = subprocess.Popen(cmd, start_new_session=True)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


# ---------------------------------------------------------------------------#
# Main loop                                                                  #
# ---------------------------------------------------------------------------#
def main() -> None:
    """
    Implements the following state machine:

    • IDLE:
        waiting for GPIO to go from HIGH (1) to LOW (0).
    • PLAY_MESSAGE:
        reproducing MESSAGE_FILE. If GPIO returns HIGH before
        playback completes → abort and return to IDLE.
        When playback finishes while GPIO is still LOW → start recording.
    • RECORDING:
        capturing audio whilst GPIO stays LOW.
        When GPIO returns HIGH → stop recording and return to IDLE.
    """
    setup_gpio()
    last_level = read_gpio()
    state = "IDLE"

    message_thread: Optional[threading.Thread] = None
    recorder = Recorder()

    try:
        while True:
            level = read_gpio()

            falling_edge = last_level == 1 and level == 0
            rising_edge = last_level == 0 and level == 1

            # ----------------------------- IDLE ----------------------------- #
            if state == "IDLE" and falling_edge:
                message_thread = _play_message(blocking=False)
                state = "PLAY_MESSAGE"

            # ------------------------ PLAY_MESSAGE ------------------------- #
            elif state == "PLAY_MESSAGE":
                # Abort if pin goes high before message ends
                if rising_edge:
                    stop_audio()
                    state = "IDLE"
                # Start recording once playback finishes
                elif message_thread and not message_thread.is_alive():
                    recorder.start()
                    state = "RECORDING"

            # -------------------------- RECORDING -------------------------- #
            elif state == "RECORDING" and rising_edge:
                recorder.stop()
                state = "IDLE"

            last_level = level
            time.sleep(POLL_DELAY)

    except KeyboardInterrupt:
        print("\nExiting…")

    finally:
        stop_audio()
        recorder.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
