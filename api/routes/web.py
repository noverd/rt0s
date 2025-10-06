from sanic import Blueprint, response

web_bp = Blueprint("web", url_prefix="/")

@web_bp.get("/")
async def serve_index(request):
    """Serves the index.html file."""
    return await response.file("index.html")