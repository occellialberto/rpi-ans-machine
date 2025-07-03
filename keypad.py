import RPi.GPIO as GPIO
import time

def keypad(callback=None, multiple = True, full_number_timeout = 1):
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
    p_time = time.time()
    full_number = ""
    try:
        while True:
            enabled = not GPIO.input(enable_pin)
            if enabled == 1:
                p_time = time.time()
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
                        if callback and not multiple:
                            callback(number)
                        if multiple:
                            full_number += str(number)
                            #print(full_number)
            p_enabled = enabled
            if multiple:
                if time.time()-p_time > full_number_timeout and len(full_number)>0:
                    print(f"Full number: {full_number}")
                    if callback:
                       callback(int(full_number))
                    full_number = ""
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nUscita dal monitor.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    keypad()
