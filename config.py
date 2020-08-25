import os


class Config:

    LINE_PAY_ID = os.environ['LINE_PAY_ID']
    LINE_PAY_SECRET = os.environ['LINE_PAY_SECRET']

    CHANNEL_ACCESS_TOKEN = os.environ['CHANNEL_ACCESS_TOKEN']
    CHANNEL_SECRET = os.environ['CHANNEL_SECRET']

    STORE_IMAGE_URL = 'https://i.imgur.com/HvJQ4qL.png'

    LIFF_URL = 'line://app/1588414308-wRy8rOnK'

    BASE_ID = '@351tkdba'
