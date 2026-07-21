"""Ponto de entrada de desenvolvimento. Em produção, usar gunicorn/uwsgi."""
from dotenv import load_dotenv

load_dotenv()  # carrega .env antes de instanciar a app (config lê os.environ)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
