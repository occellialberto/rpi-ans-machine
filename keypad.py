import RPi.GPIO as GPIO
import time

def keypad(callback_number=None, callback_rotation=None, multiple = True, full_number_timeout = 1,
           stop_event=None):
    # Usa la numerazione BCM (i numeri GPIO, non i pin fisici)
    GPIO.setmode(GPIO.BCM)

    enable_pin = 11
    numpad_pin = 10
    p_keypad_state = 1
    p_enabled = 0
    number = 0

    PINS = [enable_pin, numpad_pin]
    # Configura i pin come input con pull-up (modifica se serve pull-down)
    for pin in PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print(f"Monitoraggio stato GPIO {PINS[0]} e {PINS[1]} (premi Ctrl+C per uscire)")
    p_time = time.time()
    full_number = ""
    try:
        while stop_event is None or not stop_event.is_set():
            enabled = not GPIO.input(enable_pin)
            if enabled == 1:
                p_time = time.time()
                if enabled != p_enabled:
                    if callback_rotation:
                        callback_rotation()
                    number = 0
                keypad_state = GPIO.input(numpad_pin)
                if keypad_state != p_keypad_state and keypad_state == 1:
                    number+=1
                p_keypad_state = keypad_state
            else:
                if enabled != p_enabled:
                    if number == 0:
                        pass
                    else:
                        if number > 9:
                            number = 0
                        print(f"{number}", end = "", flush = True)
                        if callback_number and not multiple:
                            callback_number(number)
                        if multiple:
                            full_number += str(number)
                            #print(full_number)
            p_enabled = enabled
            if multiple:
                if not enabled and time.time()-p_time > full_number_timeout and len(full_number)>0:
                    print(f" -> Full number: {full_number}")
                    if callback_number:
                       callback_number(full_number)
                    full_number = ""
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nUscita dal monitor.")
    finally:
        GPIO.cleanup(PINS)


if __name__ == "__main__":
    keypad()
