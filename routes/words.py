import base64
import json
import uuid

import requests

from flask import Blueprint, current_app, jsonify, request


words = Blueprint("words", __name__)


# ============================================================
# CONFIGURACIÓN DE GITHUB
# ============================================================

def github_config():
    token = current_app.config.get("GITHUB_TOKEN")
    owner = current_app.config.get("GITHUB_OWNER")
    repo = current_app.config.get("GITHUB_REPO")
    file_path = current_app.config.get("GITHUB_FILE_PATH")

    if not token:
        raise RuntimeError("Falta GITHUB_TOKEN")

    if not owner:
        raise RuntimeError("Falta GITHUB_OWNER")

    if not repo:
        raise RuntimeError("Falta GITHUB_REPO")

    return token, owner, repo, file_path


def github_headers():
    token, _, _, _ = github_config()

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def github_url():
    _, owner, repo, file_path = github_config()

    return (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{file_path}"
    )


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalize_word(value):
    """
    Normaliza una palabra para comparar duplicados.

    Ejemplos:

    House
    house
    HOUSE
     House

    -> house
    """

    if value is None:
        return ""

    return " ".join(
        str(value).strip().lower().split()
    )


# ============================================================
# OBTENER WORDS.JSON
# ============================================================

def get_github_file():

    response = requests.get(
        github_url(),
        headers=github_headers(),
        timeout=15
    )

    if response.status_code == 404:

        # Si todavía no existe, comenzamos con una lista vacía.
        return [], None

    if not response.ok:

        raise RuntimeError(
            f"GitHub respondió {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    encoded_content = data.get("content", "")
    sha = data.get("sha")

    # GitHub puede devolver saltos de línea dentro del base64
    encoded_content = encoded_content.replace("\n", "")

    if not encoded_content:
        return [], sha

    decoded_content = base64.b64decode(
        encoded_content
    ).decode("utf-8")

    try:
        words_data = json.loads(decoded_content)
    except json.JSONDecodeError:

        raise RuntimeError(
            "El archivo words.json no contiene JSON válido."
        )

    if not isinstance(words_data, list):

        raise RuntimeError(
            "words.json debe contener una lista."
        )

    return words_data, sha


# ============================================================
# GUARDAR WORDS.JSON EN GITHUB
# ============================================================

def save_github_file(words_data, sha, message):

    content = json.dumps(
        words_data,
        ensure_ascii=False,
        indent=2
    )

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded_content,
    }

    # Si el archivo ya existe, GitHub requiere el SHA.
    if sha:
        payload["sha"] = sha

    response = requests.put(
        github_url(),
        headers=github_headers(),
        json=payload,
        timeout=15
    )

    if not response.ok:

        # Conflicto típico cuando alguien modificó
        # el archivo mientras nosotros trabajábamos.
        if response.status_code == 409:

            raise RuntimeError(
                "El glosario fue modificado por otra persona. "
                "Volvé a intentarlo."
            )

        raise RuntimeError(
            f"No se pudo guardar en GitHub "
            f"({response.status_code}): "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# GET /api/words
# ============================================================

@words.get("/words")
def get_words():

    try:

        words_data, _ = get_github_file()

        # Ordenar alfabéticamente
        words_data.sort(
            key=lambda word:
            normalize_word(word.get("english", ""))
        )

        return jsonify(words_data)

    except Exception as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": "No se pudo cargar el glosario."
        }), 500


# ============================================================
# POST /api/words
# ============================================================

@words.post("/words")
def add_word():

    try:

        data = request.get_json(silent=True)

        if not data:

            return jsonify({
                "error": "No se recibieron datos."
            }), 400


        english = str(
            data.get("english", "")
        ).strip()

        spanish = str(
            data.get("spanish", "")
        ).strip()

        meaning = str(
            data.get("meaning", "")
        ).strip()


        # Validación
        if not english or not spanish or not meaning:

            return jsonify({
                "error": "Todos los campos son obligatorios."
            }), 400


        # Obtener datos actuales
        words_data, sha = get_github_file()


        # Comprobar duplicados
        normalized_english = normalize_word(
            english
        )

        duplicate = any(
            normalize_word(
                word.get("english", "")
            ) == normalized_english
            for word in words_data
        )


        if duplicate:

            return jsonify({
                "error": "Esta palabra ya existe en el glosario."
            }), 409


        # Crear nueva palabra
        new_word = {
            "id": str(uuid.uuid4()),
            "english": english,
            "spanish": spanish,
            "meaning": meaning
        }


        words_data.append(new_word)


        # Ordenar
        words_data.sort(
            key=lambda word:
            normalize_word(
                word.get("english", "")
            )
        )


        # Guardar
        save_github_file(
            words_data,
            sha,
            f"Agregar palabra: {english}"
        )


        return jsonify(new_word), 201


    except RuntimeError as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": str(error)
        }), 500


    except Exception as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": "No se pudo agregar la palabra."
        }), 500


# ============================================================
# PUT /api/words/<id>
# ============================================================

@words.put("/words/<word_id>")
def update_word(word_id):

    try:

        data = request.get_json(silent=True)

        if not data:

            return jsonify({
                "error": "No se recibieron datos."
            }), 400


        english = str(
            data.get("english", "")
        ).strip()

        spanish = str(
            data.get("spanish", "")
        ).strip()

        meaning = str(
            data.get("meaning", "")
        ).strip()


        if not english or not spanish or not meaning:

            return jsonify({
                "error": "Todos los campos son obligatorios."
            }), 400


        # Obtener datos actuales
        words_data, sha = get_github_file()


        # Buscar palabra
        word_index = next(
            (
                index
                for index, word
                in enumerate(words_data)
                if str(word.get("id")) == str(word_id)
            ),
            None
        )


        if word_index is None:

            return jsonify({
                "error": "La palabra no existe."
            }), 404


        # Comprobar duplicados
        normalized_english = normalize_word(
            english
        )


        duplicate = any(
            index != word_index
            and normalize_word(
                word.get("english", "")
            ) == normalized_english
            for index, word
            in enumerate(words_data)
        )


        if duplicate:

            return jsonify({
                "error": "Esta palabra ya existe en el glosario."
            }), 409


        # Actualizar
        updated_word = {
            "id": words_data[word_index]["id"],
            "english": english,
            "spanish": spanish,
            "meaning": meaning
        }


        words_data[word_index] = updated_word


        # Ordenar
        words_data.sort(
            key=lambda word:
            normalize_word(
                word.get("english", "")
            )
        )


        # Guardar
        save_github_file(
            words_data,
            sha,
            f"Modificar palabra: {english}"
        )


        return jsonify(updated_word)


    except RuntimeError as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": str(error)
        }), 500


    except Exception as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": "No se pudo modificar la palabra."
        }), 500


# ============================================================
# DELETE /api/words/<id>
# ============================================================

@words.delete("/words/<word_id>")
def delete_word(word_id):

    try:

        # Obtener datos actuales
        words_data, sha = get_github_file()


        # Buscar palabra
        word_index = next(
            (
                index
                for index, word
                in enumerate(words_data)
                if str(word.get("id")) == str(word_id)
            ),
            None
        )


        if word_index is None:

            return jsonify({
                "error": "La palabra no existe."
            }), 404


        deleted_word = words_data[word_index]


        # Eliminar
        words_data.pop(word_index)


        # Guardar
        save_github_file(
            words_data,
            sha,
            f"Eliminar palabra: "
            f"{deleted_word.get('english', '')}"
        )


        return jsonify({
            "message": "Palabra eliminada correctamente.",
            "word": deleted_word
        })


    except RuntimeError as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": str(error)
        }), 500


    except Exception as error:

        current_app.logger.exception(error)

        return jsonify({
            "error": "No se pudo eliminar la palabra."
        }), 500