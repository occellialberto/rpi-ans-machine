# @file main.py
# @author Alberto Occelli
# @version 1.0
# @date 09/06/2025
# @brief This script is designed to monitor a GPIO pin, play an audio message, and record audio based on the state of the pin.

import logging
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from player import play_audio, stop_audio

import RPi.GPIO as GPIO

# ---------------------------------------------------------------------------#
# Logging setup                                                              #
# ---------------------------------------------------------------------------#
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------#
# Configuration                                                              #
# ---------------------------------------------------------------------------#
PIN = 17                                   # GPIO pin to monitor (BCM scheme)
MESSAGE_FILE = "message_edited.wav"        # Audio message to be reproduced
RECORD_DIR = Path("recordings")            # Directory where recordings land
# Use PulseAudio’s recorder. “--format=cd --file-format=wav” is the closest
# equivalent to the old “arecord -q -f cd -t wav”.
device = "--device=alsa_input.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.mono-fallback"
RECORD_CMD = [
    "parecord",
    "--rate=16000",
    "--channels=1",
    "--format=s16le",
    device,
    "--file-format=wav",
]
POLL_DELAY = 0.02                          # Seconds between GPIO polls
# ---------------------------------------------------------------------------#

## @brief Prepare the GPIO subsystem.
def setup_gpio() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("GPIO initialised (BCM pin %s).", PIN)

## @brief Read the monitored pin.
#  @return 0 (LOW) or 1 (HIGH).
def read_gpio() -> int:
    return GPIO.input(PIN)

# ---------------------------------------------------------------------------#
# Playback helper                                                            #
# ---------------------------------------------------------------------------#

## @brief Play MESSAGE_FILE and return a Thread that finishes when playback ends.
#  @param blocking If `blocking=True` the function itself will not return until the audio
#  has been played, but the returned object is still a dummy Thread.
#  @return thread
def _play_message(blocking: bool = False) -> threading.Thread:
    log.info("Starting message playback (%s, blocking=%s).", MESSAGE_FILE, blocking)
    if blocking:
        play_audio(MESSAGE_FILE, blocking=True)
        log.info("Message playback finished (blocking path).")
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

## @brief Minimal wrapper around a recording subprocess (e.g. `parecord`).
class Recorder:
    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen[str]] = None
        self.file: Optional[Path] = None
        self.start_time: Optional[float] = None

    ## @brief Start recording.
    def start(self) -> None:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file = RECORD_DIR / f"call_{timestamp}.wav"
        cmd = [*RECORD_CMD, str(self.file)]
        log.info("Starting recording → %s", self.file)
        self.proc = subprocess.Popen(cmd, start_new_session=True)
        self.start_time = time.time()

    ## @brief Stop recording.
    def stop(self) -> None:
        if self.proc and self.proc.poll() is None and (time.time() - self.start_time) > 1:
            log.info("Stopping recording.")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                log.warning("Recorder did not terminate, killing.")
                self.proc.kill()
            if self.file:
                log.info("Recording saved: %s", self.file)
        self.proc = None
        self.file = None
        self.start_time = None

# ---------------------------------------------------------------------------#
# Main loop                                                                  #
# ---------------------------------------------------------------------------#

## @brief Implements the following state machine:
#  • IDLE: waiting for GPIO to go from HIGH (1) to LOW (0).
#  • PLAY_MESSAGE: reproducing MESSAGE_FILE. If GPIO returns HIGH before
#  playback completes → abort and return to IDLE.
#  When playback finishes while GPIO is still LOW → start recording.
#  • RECORDING: capturing audio whilst GPIO stays LOW.
#  When GPIO returns HIGH → stop recording and return to IDLE.
def main() -> None:
    subprocess.run(["paplay", "o95.wav"])
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
            if state == "IDLE" and rising_edge:
                log.info("Hang down detected (rising edge) → playing message.")
                message_thread = _play_message(blocking=False)
                state = "PLAY_MESSAGE"

            # ------------------------ PLAY_MESSAGE ------------------------- #
            elif state == "PLAY_MESSAGE":
                # Abort if pin goes high before message ends
                if falling_edge:
                    log.info("Hang up detected during playback → aborting.")
                    stop_audio()
                    state = "IDLE"
                # Start recording once playback finishes
                elif message_thread and not message_thread.is_alive():
                    log.info("Message playback finished → starting recording.")
                    recorder.start()
                    state = "RECORDING"

            # -------------------------- RECORDING -------------------------- #
            elif state == "RECORDING" and falling_edge:
                log.info("Hang down detected.")
                recorder.stop()
                state = "IDLE"

            last_level = level
            time.sleep(POLL_DELAY)

    except KeyboardInterrupt:
        log.info("Keyboard interrupt received – exiting.")

    finally:
        stop_audio()
        recorder.stop()
        GPIO.cleanup()
        log.info("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
