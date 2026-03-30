from flask import Flask
from config import Config
from routes.main import main

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Registrar rutas
    app.register_blueprint(main)

    return app

app = create_app()