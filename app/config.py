import os
from dotenv import load_dotenv

load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


MAX_MESSAGE_LENGTH = 200
HTTP_TIMEOUT = 20.0
