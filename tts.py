import datetime
from gtts import gTTS

def text_to_speech(input_text):
    # Convert the input text into speech
    speech = gTTS(text = input_text, lang = 'en', slow = False)
    
    # Save the speech audio into a file
    speech.save("today.mp3")

text_to_speech("Accadde oggi")