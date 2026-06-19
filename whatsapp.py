import os
from twilio.rest import Client

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")

def send_message(to_phone: str, body: str):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(
        from_=f'whatsapp:{TWILIO_NUMBER}',
        to=f'whatsapp:{to_phone}',
        body=body
    )

def send_image(to_phone: str, image_url: str, caption: str = ""):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{to_phone}',
        media_url=[image_url],
        body=caption
    )