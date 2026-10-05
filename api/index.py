"""Vercel entry point (serverless Python function).

Vercel's file system is read-only except /tmp, so the database and uploads live
there. /tmp is temporary: data can reset when Vercel starts a fresh instance.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("INSTANCE_DIR", "/tmp/smartagri")
os.environ.setdefault("SMARTAGRI_BACKEND", "onnx")

from agri import create_app  # noqa: E402

app = create_app()
