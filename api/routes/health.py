from sanic import Blueprint
from sanic.response import json

bp = Blueprint("health", url_prefix="/api")


@bp.get("/health")
async def health(request):
    """
    Проверка работоспособности сервиса.
    openapi:
    summary: Health Check
    description: Этот эндпоинт можно использовать для проверки, что сервис запущен и отвечает.
    responses:
      '200':
        description: Сервис работает нормально.
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: OK
    """
    return json({"status": "OK"})
