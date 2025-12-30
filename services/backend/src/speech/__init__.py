from flask import Blueprint

speech_bp = Blueprint("speech", __name__, url_prefix="/speech")

from . import routes  # noqa: E402, F401
