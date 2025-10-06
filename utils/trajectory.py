import math
import numpy as np
from datetime import timedelta
from skyfield.api import load
from skyfield.toposlib import wgs84

# Загрузка таймскейла Skyfield, глобальный объект для производительности
ts = load.timescale()

R_EARTH_KM = 6371.0

def get_point_at_distance(lat1, lon1, distance_km, bearing_deg):
    """
    Рассчитывает координаты точки, находящейся на заданном расстоянии и азимуте от исходной точки.

    :param lat1: Широта исходной точки в градусах.
    :param lon1: Долгота исходной точки в градусах.
    :param distance_km: Расстояние в километрах.
    :param bearing_deg: Азимут в градусах (0=Север, 90=Восток).
    :return: Кортеж (широта, долгота) новой точки в градусах.
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    bearing_rad = math.radians(bearing_deg)

    lat2_rad = math.asin(
        math.sin(lat1_rad) * math.cos(distance_km / R_EARTH_KM)
        + math.cos(lat1_rad) * math.sin(distance_km / R_EARTH_KM) * math.cos(bearing_rad)
    )

    lon2_rad = lon1_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_km / R_EARTH_KM) * math.cos(lat1_rad),
        math.cos(distance_km / R_EARTH_KM) - math.sin(lat1_rad) * math.sin(lat2_rad),
    )

    return math.degrees(lat2_rad), math.degrees(lon2_rad)


def generate_simplified_trajectory(
    launch_lat,
    launch_lon,
    target_altitude_km,
    ascent_time_s,
    inclination_deg,
    launch_date,
):
    """
    Генерирует упрощенную траекторию в виде векторов состояния (положение и скорость).

    Сначала генерируется путь в географических координатах, затем он преобразуется
    в геоцентрические инерциальные векторы (GCRS) для каждого временного шага.
    Скорость вычисляется как разница векторов положения между шагами.

    Возвращает:
        Список словарей, где каждый словарь представляет точку траектории с ключами
        'time_obj', 'position' (np.ndarray) и 'velocity' (np.ndarray).
    """
    time_step_s = 10
    launch_azimuth_deg = 90.0 if inclination_deg < 90 else 0.0
    avg_horizontal_speed_km_s = 4.0
    total_downrange_distance_km = avg_horizontal_speed_km_s * ascent_time_s

    # Шаг 1: Сгенерировать географические точки
    geo_points = []
    for time_s in range(0, int(ascent_time_s) + time_step_s, time_step_s):
        progress = time_s / ascent_time_s if ascent_time_s > 0 else 0
        progress = min(progress, 1.0)

        current_altitude_km = progress * target_altitude_km
        current_distance_km = progress * total_downrange_distance_km
        current_lat, current_lon = get_point_at_distance(
            launch_lat, launch_lon, current_distance_km, launch_azimuth_deg
        )
        geo_points.append(
            {
                "time_s": time_s,
                "lat": current_lat,
                "lon": current_lon,
                "alt": current_altitude_km,
            }
        )

    # Шаг 2: Преобразовать географические точки в векторы состояния
    trajectory = []
    if len(geo_points) < 2:
        return [] # Невозможно вычислить скорость для одной точки

    for i in range(len(geo_points) - 1):
        p1_geo = geo_points[i]
        p2_geo = geo_points[i+1]

        time1 = launch_date + timedelta(seconds=p1_geo["time_s"])
        time2 = launch_date + timedelta(seconds=p2_geo["time_s"])

        # Преобразование в объекты времени Skyfield
        t1_sky = ts.from_datetime(time1)
        t2_sky = ts.from_datetime(time2)

        # Создание геопозиций Skyfield
        pos1_wgs84 = wgs84.latlon(p1_geo["lat"], p1_geo["lon"], elevation_m=p1_geo["alt"] * 1000)
        pos2_wgs84 = wgs84.latlon(p2_geo["lat"], p2_geo["lon"], elevation_m=p2_geo["alt"] * 1000)

        # Получение векторов положения в GCRS
        pos1_vec = pos1_wgs84.at(t1_sky).position.km
        pos2_vec = pos2_wgs84.at(t2_sky).position.km

        # Вычисление вектора скорости
        velocity_vec = (pos2_vec - pos1_vec) / time_step_s

        trajectory.append(
            {"time_obj": time1, "position": pos1_vec, "velocity": velocity_vec}
        )

    # Добавляем последнюю точку, используя скорость предпоследнего сегмента
    if trajectory:
        last_geo_point = geo_points[-1]
        last_time = launch_date + timedelta(seconds=last_geo_point["time_s"])
        last_sky_time = ts.from_datetime(last_time)
        last_pos_wgs84 = wgs84.latlon(
            last_geo_point['lat'], last_geo_point['lon'], elevation_m=last_geo_point['alt'] * 1000
        )
        last_pos_vec = last_pos_wgs84.at(last_sky_time).position.km

        trajectory.append(
            {
                "time_obj": last_time,
                "position": last_pos_vec,
                "velocity": trajectory[-1]['velocity'] # Используем предыдущую скорость
            }
        )

    return trajectory