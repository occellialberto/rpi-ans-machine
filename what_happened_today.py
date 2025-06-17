import datetime
import wikipedia

def eventi_del_giorno():
    wikipedia.set_lang("it")
    today = datetime.datetime.now()
    day = today.day
    month = today.strftime("%B").lower()
    italian_months = {
        'january': 'gennaio', 'february': 'febbraio', 'march': 'marzo', 'april': 'aprile',
        'may': 'maggio', 'june': 'giugno', 'july': 'luglio', 'august': 'agosto',
        'september': 'settembre', 'october': 'ottobre', 'november': 'novembre', 'december': 'dicembre'
    }
    month = italian_months[month]
    page_title = f"{day}_{month}"
    
    try:
        content = wikipedia.page(page_title).content
        start_events = content.find("== Eventi ==")
        end_events = content.find("== Nati ==")
        events = content[start_events + 12:end_events].strip()
        events = events.split("\n")
        year = 0
        for e in events:
            try:
                year = int(e[:4])
                event = e[7:]
            except ValueError:
                event.append(e)
                print("(Same year as before)")
            print(f"Nel {year}... {event}")
            
        '''      for e in events:
            try:
                year = int(e[:4])
                if year not in year_events:
                    year_events[year] = []
            except ValueError:
                year = p_year
            if len(e) > 2:
                year_events[year].append(e)
            p_year = year
        for year, events in year_events.items():
            for e in events:
                print(f"Nel {year}... {events}")
                print(e)
                response = openai.audio.speech.create(
                    model="gpt-4o-mini-tts",  # or "tts-1-hd"
                    voice="alloy",  # others: alloy, nova, echo, fable
                    input=e
                )
                with open(f"events/{year}.mp3", "ab") as f:
                    f.write(response.content)'''

        '''        
        start_births = content.find("== Nati ==")
        end_births = content.find("== Morti ==")
        births = content[start_births + 11:end_births].strip()
        births = births.split("\n")
        print(births)

        start_deaths = content.find("== Morti ==")
        end_deaths = content.find("== Celebrità ==")
        deaths = content[start_deaths + 11:end_deaths].strip()
        deaths = deaths.split("\n")
        print(deaths)'''
        #text = f"Eventi del {day} {month}: {events[:1500]}"  # max 4096 characters

        #print("📅 Events of the day:")
        #print(text)
        '''
        # 🔊 Generate audio with OpenAI TTS
        response = openai.audio.speech.create(
            model="tts-1",  # or "tts-1-hd"
            voice="shimmer",  # others: alloy, nova, echo, fable
            input=text
        )

        with open("events.mp3", "wb") as f:
            f.write(response.content)

        print("▶️ Playing the audio...")
        import platform
        import subprocess
        if platform.system() == "Darwin":
            subprocess.run(["afplay", "events.mp3"])
        elif platform.system() == "Windows":
            subprocess.run(["start", "events.mp3"], shell=True)
        else:  # Linux
            subprocess.run(["mpg123", "events.mp3"])'''

    except Exception as e:
        print("❌ Error:", str(e))

eventi_del_giorno()
