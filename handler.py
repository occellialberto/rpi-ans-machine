from dataclasses import dataclass


# Record these prompts/content as WAV files, or change the paths here.
NAVIGATION_AUDIO = {
    "MENU_SERVIZI": "messages/menu_servizi.wav",
    "MENU_PRINCIPALE": "messages/menu_principale.wav",
    "ASCOLTA_MESSAGGI": "messages/messaggi.wav",
    "METEO": "messages/meteo.wav",
    "CASA": "messages/casa.wav",
    "NUMERO_NON_VALIDO": "messages/numero_non_valido.wav",
}
NAVIGATION_PROMPTS = {
    "MENU_SERVIZI": "Per ascoltare i messaggi, digita 1; per il meteo, digita 2; "
                    "per tornare al menu principale, digita 0.",
    "MENU_PRINCIPALE": "Per accedere ai servizi, digita 10.",
    "ASCOLTA_MESSAGGI": "Ascolto dei messaggi.",
    "METEO": "Informazioni sul meteo.",
    "CASA": "Hai chiamato casa.",
    "NUMERO_NON_VALIDO": "Numero non valido per il menu corrente. Riprova.",
}


@dataclass(frozen=True)
class NavigationResponse:
    action: str
    prompt: str
    audio_file: str


class Navigation:
    """Keep menu choices scoped to the current call."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.menu = "PRINCIPALE"

    def handle_number(self, number: str) -> str:
        if self.menu == "PRINCIPALE":
            if number == "10":
                self.menu = "SERVIZI"
                return "MENU_SERVIZI"
            if number == "011351789":
                return "CASA"
            return "NUMERO_NON_VALIDO"

        if number == "1":
            return "ASCOLTA_MESSAGGI"
        if number == "2":
            return "METEO"
        if number == "0":
            self.reset()
            return "MENU_PRINCIPALE"
        return "NUMERO_NON_VALIDO"

def on_number_composed(number: str, navigation: Navigation) -> NavigationResponse:
    action = navigation.handle_number(str(number))
    print(f"Menu {navigation.menu}: {action}")
    return NavigationResponse(
        action=action,
        prompt=NAVIGATION_PROMPTS[action],
        audio_file=NAVIGATION_AUDIO[action],
    )

if __name__ == "__main__":
    from keypad import keypad

    navigation = Navigation()
    keypad(lambda number: on_number_composed(number, navigation))
