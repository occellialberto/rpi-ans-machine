import RPi.GPIO as GPIO
import time

def keypad(callback=None):
    # Usa la numerazione BCM (i numeri GPIO, non i pin fisici)
    GPIO.setmode(GPIO.BCM)

    enable_pin = 11
    numpad_pin = 10
    p_keypad_state = 1
    p_enabled = 0

    PINS = [enable_pin, numpad_pin]
    # Configura i pin come input con pull-up (modifica se serve pull-down)
    for pin in PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print(f"Monitoraggio stato GPIO {PINS[0]} e {PINS[1]} (premi Ctrl+C per uscire)")

    try:
        while True:
            enabled = not GPIO.input(enable_pin)
            if enabled == 1:
                if enabled != p_enabled:
                    number = 0
                keypad_state = GPIO.input(numpad_pin)
                if keypad_state != p_keypad_state and keypad_state == 1:
                    number+=1
                p_keypad_state = keypad_state
            else:
                if enabled != p_enabled:
                    if number == 0:
                        print("No number pressed")
                    else:
                        if number > 9:
                            number = 0
                        print(f"number: {number}")
                        if callback:
                            callback(number)
            p_enabled = enabled
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nUscita dal monitor.")
    finally:
        GPIO.cleanup()
