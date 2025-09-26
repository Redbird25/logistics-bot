from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API ID: "))
api_hash = input("API hash: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("TG_SESSION_STRING =", client.session.save())