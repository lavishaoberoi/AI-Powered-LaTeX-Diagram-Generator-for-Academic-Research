"""
WSGI entry point for production deployment (Gunicorn / IBM Code Engine).
"""
from app import app

if __name__ == "__main__":
    app.run()
