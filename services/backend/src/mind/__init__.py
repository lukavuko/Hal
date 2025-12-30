from flask import Blueprint

mind_bp = Blueprint("mind", __name__, url_prefix="/mind")

from . import routes  # noqa: E402, F401
