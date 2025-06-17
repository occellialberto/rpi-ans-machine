import datetime
import wikipedia
import os, glob
from gtts import gTTS
import yaml
import logging
from pydub import AudioSegment
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_day_events():
    wikipedia.set_lang("it")
    today = datetime.datetime.now()
    day = today.day
    month = today.strftime("%B").lower()
    italian_months = {
        'january': 'gennaio', 'february': 'febbraio', 'march': 'marzo', 'april': 'aprile',
        'may': 'maggio', 'june': 'giugno', 'july': 'luglio', 'august': 'agosto',
        'september': 'settembre', 'october': 'ottobre', 'november': 'novembre', 'december': 'dicembre'
    }
    page_title = f"{day}_{italian_months[month]}"
    
    try:
        content = wikipedia.page(page_title).content
        start_events = content.find("== Eventi ==")
        end_events = content.find("== Nati ==")
        events = content[start_events + 12:end_events].strip()
        events = events.split("\n")
        year = 0
        events_year = {}
        for e in events:
            try:
                year = int(e[:4])
                event = e[7:]
            except ValueError:
                event = e
            if len(e) > 5:
                if year in events_year:
                    events_year[year].append(event)
                else:
                    events_year[year] = [event]
        # Generate speeches
        for y in tqdm(events_year.keys(), desc="Generating audio", unit="audio"):
            speech = f"Nel {y} "
            for e in events_year[y]:
                speech+=f"{e}. "
            logging.info(speech)
            tts = gTTS(text=speech, lang='it')
            tts.save(f"events/{y}_{month}_{day}.mp3")
            sound = AudioSegment.from_mp3(f"events/{y}_{month}_{day}.mp3")
            sound = sound.set_frame_rate(16000)
            sound.export(f"events/{y}_{month}_{day}.mp3", format="mp3")
        with open("events/date.yaml", "w") as f:
            yaml.dump({'day': day, 'month': month}, f)
    except Exception as e:
        logging.error("❌ Error:", str(e))

date_rec = {'day': 1, 'month': 'january'}
try:
    with open("events/date.yaml", "r") as f:
        date_rec = yaml.safe_load(f)
except FileNotFoundError:
    logging.warning("File not found, using default date")

if date_rec != {'day': datetime.datetime.now().day, 'month': datetime.datetime.now().strftime("%B").lower()}:
    logging.info("Missing recording of the day. Generating it...")
    files = glob.glob('events/*.mp3')
    for f in files:
        os.remove(f)
    generate_day_events()
else:
    logging.info("Recordings already taken")
