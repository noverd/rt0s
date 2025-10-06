import requests
import json
from urllib.parse import quote

# --- ВАШИ УЧЕТНЫЕ ДАННЫЕ SPACE-TRACK.ORG ---
# !!! Замените 'YOUR_USERNAME' и 'YOUR_PASSWORD' на свои данные !!!
SPACE_TRACK_USERNAME = "pahomovbogdan099@gmail.com"
SPACE_TRACK_PASSWORD = "463576Spacetrack!"


def get_debris_filtered_satcat_final(
    min_inclination: float,
    max_inclination: float,
    min_altitude_km: float,
    max_altitude_km: float,
    limit: int = 10,
) -> list | str:
    """
    Получает данные о космическом мусоре (DEBRIS) с Space-Track.org,
    используя класс 'satcat' и исправленное поле для сортировки 'LAUNCH'.
    """

    BASE_URL = "https://www.space-track.org/basicspacedata/query"

    # 1. Построение предиката (фильтра)
    # ***********************************

    filters = [
        "class/satcat",
        "OBJECT_TYPE/DEBRIS",
        # Фильтры
        f"INCLINATION/{min_inclination}--{max_inclination}",
        f"PERIGEE/{min_altitude_km}--{max_altitude_km}",
        f"APOGEE/{min_altitude_km}--{max_altitude_km}",
        # Дополнительные параметры
        f"limit/{limit}",
        # ИСПРАВЛЕНО: используем поле LAUNCH для сортировки
        "orderby/LAUNCH%20desc",
        "format/json",
    ]

    # Объединяем фильтры и кодируем URL
    predicate = "/".join(filters)
    full_query_url = f"{BASE_URL}/{quote(predicate)}"

    print(f"URL запроса: {full_query_url}")

    # 2. Выполнение запроса с аутентификацией
    # ***************************************
    try:
        # Аутентификация через сессию
        session = requests.Session()
        login_url = "https://www.space-track.org/ajaxauth/login"

        login_response = session.post(
            login_url,
            data={"identity": SPACE_TRACK_USERNAME, "password": SPACE_TRACK_PASSWORD},
            timeout=15,
        )
        login_response.raise_for_status()

        # Выполняем запрос
        response = session.get(full_query_url, timeout=30)
        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict) and ("error" in data or "ERROR" in data):
            return (
                f"❌ Ошибка API Space-Track: {data.get('error') or data.get('ERROR')}"
            )

        # API возвращает пустой список, если ничего не найдено
        if not data:
            return "Объекты, соответствующие заданным критериям, не найдены."

        return data

    except requests.exceptions.RequestException as err:
        return f"❌ Общая ошибка запроса: {err}"
    except json.JSONDecodeError:
        return f"❌ Ошибка декодирования JSON. Текст ответа: {response.text[:200]}..."
