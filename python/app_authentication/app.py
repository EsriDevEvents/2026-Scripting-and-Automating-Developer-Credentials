import os
import json

from pathlib import Path
from datetime import timedelta

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_session import Session

from dotenv import load_dotenv

import auth


def is_client_authorized(req) -> bool:
    """
    Mirrors Node.js isClientAuthorized(request):
      const nonce = request.body.nonce
      return nonce == "1234"
    """
    data = req.get_json(silent=True) or {}
    return data.get("nonce") == 1234


### server application setup ###
def create_app():
    #
    load_dotenv()

    app = Flask(__name__)
    CORS(app)

    # Load configuration from server-configuration.json, which should be in the same directory as this app.py
    config_path = (Path(__file__).resolve().parent) / "server-configuration.json"

    # Load your server-configuration.json (same as Node)
    with config_path.open("r", encoding="utf-8") as f:
        configuration = json.load(f)

    token_exp_minutes = int(configuration.get("tokenExpirationMinutes", 60))

    # Session config:
    # Node uses express-session + session-file-store persisted to disk with TTL.
    # Flask equivalent: Flask-Session using filesystem backend.
    app.config["SECRET_KEY"] = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_sessions")
    app.config["SESSION_PERMANENT"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=token_exp_minutes)

    # Optional: keep sessions more similar to your cookie maxAge behavior
    app.config["SESSION_COOKIE_NAME"] = "arcgis-client-session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    Session(app)

    @app.get("/test")
    def test():
        return "<h1>I'm alive</h1>"

    @app.post("/auth")
    def auth_route():
        if not is_client_authorized(request):
            # Node: response.send(esriAppAuth.errorResponse(403, "Unauthorized."))
            return jsonify(auth.error_response(403, "Unauthorized.")), 403

        data = request.get_json(silent=True) or {}
        force_refresh = str(data.get("force", "0")) == "1"

        try:
            token = auth.get_token(force_refresh)
            referer = request.headers.get("Referer", "")
            if referer:
                app.logger.info("Giving a token to %s", referer)
            return jsonify(token)
        except Exception as e:
            # Node: response.json(error)
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()

    port = int(os.getenv("PORT", "3080"))

    cert_path = os.getenv("SSL_CERT", "/Users/mark4582/ssl/local3.crt")
    key_path = os.getenv("SSL_KEY", "/Users/mark4582/ssl/local3.key")

    app.run(host="0.0.0.0", port=port, ssl_context=(cert_path, key_path))
