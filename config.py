import os


class Config:

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "supersecretkey"
    )

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    GITHUB_OWNER = os.getenv("GITHUB_OWNER")

    GITHUB_REPO = os.getenv("GITHUB_REPO")

    GITHUB_FILE_PATH = os.getenv(
        "GITHUB_FILE_PATH",
        "data/words.json"
    )