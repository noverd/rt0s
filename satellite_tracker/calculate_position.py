import numpy as np
from skyfield.api import load, EarthSatellite
from skyfield.timelib import Time
from datetime import datetime, timezone
from typing import Dict, Any

from skyfield.toposlib import wgs84

# Загрузка таймскейла Skyfield
ts = load.timescale()


def calculate_satellite_position(
    sat_data: Dict[str, Any], target_time: datetime
) -> Dict[str, np.ndarray]:
    """
    Рассчитывает вектор состояния спутника (положение и скорость) в заданный
    момент времени в геоцентрической инерциальной системе координат (GCRS).

    Аргументы:
        sat_data (Dict[str, Any]): Словарь с данными спутника, включая 'line1' и 'line2'.
        target_time (datetime): Момент времени для расчета (объект datetime.datetime).

    Возвращает:
        Dict[str, np.ndarray]: Словарь, содержащий:
            'position' (np.ndarray): Вектор положения [x, y, z] в км.
            'velocity' (np.ndarray): Вектор скорости [vx, vy, vz] в км/с.
    """

    name = sat_data.get("name", "UNKNOWN")
    line1 = sat_data.get("line1")
    line2 = sat_data.get("line2")

    if not line1 or not line2:
        raise ValueError(
            "В данных спутника отсутствуют обязательные TLE-строки ('line1' или 'line2')."
        )

    try:
        satellite = EarthSatellite(line1, line2, name, ts)

        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        else:
            target_time = target_time.astimezone(timezone.utc)

        t: Time = ts.utc(
            target_time.year,
            target_time.month,
            target_time.day,
            target_time.hour,
            target_time.minute,
            target_time.second + target_time.microsecond / 1_000_000.0,
        )

        # Расчет геоцентрического положения и скорости
        geocentric = satellite.at(t)

        # Извлечение векторов положения и скорости
        position_vector = geocentric.position.km
        velocity_vector = geocentric.velocity.km_per_s

        return {"position": position_vector, "velocity": velocity_vector}

    except ValueError as e:
        raise ValueError(
            f"Ошибка при обработке TLE или расчете положения для {name}: {e}"
        )
    except Exception as e:
        raise Exception(f"Непредвиденная ошибка: {e}")
