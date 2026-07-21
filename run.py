"""Ponto de entrada de desenvolvimento. Em produção, usar gunicorn/uwsgi."""
import os

from dotenv import load_dotenv

load_dotenv()  # carrega .env antes de instanciar a app (config lê os.environ)

from app import create_app

app = create_app()

if __name__ == "__main__":
    # HOST=0.0.0.0 no .env expõe na rede (ex.: acesso por http://10.0.0.212:5000).
    # Default seguro = 127.0.0.1 (só local). DEBUG=0 desliga o reloader/debugger.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
