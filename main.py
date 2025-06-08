import time
import subprocess
from player import play_audio, stop_audio

try:
    import RPi.GPIO as GPIO
except RuntimeError:
    # On some systems running without root will raise a RuntimeError.
    # The script will still import but GPIO calls will fail.
    # You may want to handle permissions separately.
    print("Warning: GPIO access might require root privileges.")

# GPIO pin that we want to read (BCM numbering)
PIN = 14


def receiver_up():
    global audio_process
    audio_process = subprocess.run(["aplay", "message.wav"])
    audio_process.wait()

def receiver_down():
    global audio_process
    audio_process.terminate()

def setup_gpio():
    """
    Prepare the Raspberry Pi GPIO for input on the specified pin.
    """
    GPIO.setmode(GPIO.BCM)          # Use Broadcom pin numbering
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Activate internal pull-down resistor

def read_gpio(pin: int = PIN) -> int:
    """
    Return the current digital state of the given GPIO pin.
    0 -> LOW, 1 -> HIGH
    """
    return GPIO.input(pin)

def main():
    """
    Continuously monitor GPIO 14 and report state changes.
    Press Ctrl-C to exit cleanly.
    """
    setup_gpio()
    last_state = read_gpio()  # Initialize with the current state

    try:
        while True:
            current_state = read_gpio()
            if current_state != last_state:
                print(current_state)
                if current_state == 0:
                    print("CORNETTA ALZATA")
                    play_audio("message.wav")
                else:
                    # Immediately interrupt any ongoing playback when the handset is placed down
                    stop_audio()                       # cut the message short
                    print("CORNETTA ABBASSATA")
                state_str = "HIGH" if current_state else "LOW"
                last_state = current_state
            time.sleep(0.05)  # Small delay to reduce CPU usage
    except KeyboardInterrupt:
        print("\nExiting…")
    finally:
        GPIO.cleanup()        # Always clean up to release GPIO resources

if __name__ == "__main__":
    main()
