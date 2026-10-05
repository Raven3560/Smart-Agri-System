"""Production entry point:  gunicorn wsgi:app"""
from agri import create_app

app = create_app()
