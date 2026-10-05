"""Entry point for Hugging Face Spaces (Gradio SDK, free CPU hardware).

Spaces runs `python app.py` and serves whatever listens on port 7860, so the Flask
site runs here directly. Data is kept in /tmp because the Space disk is temporary.
"""
import os

if os.environ.get("SPACE_ID") or os.environ.get("VERCEL"):  # Hugging Face Spaces or Vercel
    os.environ.setdefault("INSTANCE_DIR", "/tmp/smartagri")

from agri import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7860)), threaded=True)
