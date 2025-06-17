from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Edge()
driver.get('https://onesait-engine-col.apps.clusteriot.coll.opencs.servizi.prv/onesait-portal/things/terna.digilv2:112154_0001')

# Manually log in on the browser OPENED BY SELENIUM!
input("Manually log in, then press Enter here in the Python console...")

# From here on, Selenium can navigate and perform other actions already authenticated
print("Login completed! Now Selenium can work on the already authenticated page.")
# Example: scroll the page
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
# ... other automations

input("Press Enter to close")
driver.quit()