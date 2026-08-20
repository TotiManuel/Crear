from flask import Flask
from config import Config
from dotenv import load_dotenv

from routes.main import main
from routes.words import words


load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    app.register_blueprint(main)
    app.register_blueprint(words, url_prefix="/api")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)