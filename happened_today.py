import logging
import time
import threading
import random
from pathlib import Path
from typing import Optional

from player import play_audio, stop_audio
import RPi.GPIO as GPIO

# === CONFIGURAZIONE ===
PIN = 17                     # Numero BCM del pin da monitorare
EVENTS_DIR = Path("events")  # Cartella dei file audio
POLL_DELAY = 0.02            # Pausa tra i poll (20 ms)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("GPIO initialised (BCM pin %s).", PIN)

def read_gpio():
    return GPIO.input(PIN)

def _play_random_event(blocking=False) -> threading.Thread:
    event_files = list(EVENTS_DIR.glob("*.mp3")) + list(EVENTS_DIR.glob("*.wav"))
    random.shuffle(event_files)

    def play_all():
        # (opzionale) Suona today.mp3 se esiste
        intro = EVENTS_DIR / "today.mp3"
        if intro.exists():
            log.info("Playing: %s", intro)
            play_audio(str(intro), blocking=True)
        for event_file in event_files:
            log.info("Playing event: %s", event_file)
            play_audio(str(event_file), blocking=True)

    if blocking:
        play_all()
        return threading.current_thread()
    else:
        th = threading.Thread(target=play_all, daemon=True)
        th.start()
        return th

def main():
    setup_gpio()
    log.info("In attesa...")

    last_level = read_gpio()
    state = "IDLE"
    event_thread: Optional[threading.Thread] = None

    try:
        while True:
            level = read_gpio()
            falling_edge = last_level == 1 and level == 0
            rising_edge  = last_level == 0 and level == 1

            # ================== IDLE: Avvia playback se ricevi rising edge ===================
            if state == "IDLE" and rising_edge:
                log.info("OFF-HOOK rilevato (rising edge), parto con la riproduzione.")
                stop_audio()
                event_thread = _play_random_event(blocking=False)
                state = "PLAY_MESSAGE"

            # ============ PLAY_MESSAGE: Stop se ricevi falling edge (hang-up/disconnessione) ==========
            elif state == "PLAY_MESSAGE":
                if falling_edge:
                    log.info("ON-HOOK rilevato durante riproduzione: stop audio.")
                    stop_audio()    # <-- questa funzione ora ferma DAVVERO tutti i playback
                    state = "IDLE"
            last_level = level
            time.sleep(POLL_DELAY)

    except KeyboardInterrupt:
        log.info("Keyboard interrupt ricevuto – chiudo.")

    finally:
        stop_audio()
        GPIO.cleanup()
        log.info("GPIO liberato. Bye!")

if __name__ == "__main__":
    main()