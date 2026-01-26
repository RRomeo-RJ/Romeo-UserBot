from os import getenv

API_ID = int(getenv("API_ID", "29849573"))
API_HASH = getenv("API_HASH", "33fe6934ad1872ce3eee24079bbbbace")
BOT_TOKEN = getenv("BOT_TOKEN", "7509519225:AAFni78bLSiM-wiIo484UjMYWSa8fK6_nLo")
OWNER_ID = int(getenv("OWNER_ID", "5174683280"))
STRING_SESSION = getenv("STRING_SESSION", "")
SUDO_USERS = list(map(int, getenv("SUDO_USERS", "5392070730").split()))
ALIVE_PIC = getenv("ALIVE_PIC", "https://telegra.ph/file/a62b9c7d9848afde0569e.jpg")
REPO_URL = getenv("REPO_URL", "https://github.com/RRomeo-RJ/Romeo-UserBot")
BRANCH = getenv("BRANCH", "main")
