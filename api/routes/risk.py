import logging
import math
import time
from datetime import datetime, timezone, timedelta

import numpy as np
from sanic import Blueprint
from sanic.response import json
from skyfield.api import EarthSatellite

from satellite_tracker import (
    get_all_trackable_objects,
    calculate_orbit_congestion_by_altitude,
)
from utils.risk_calculator import (
    calculate_collision_financial_risk,
)
from utils.trajectory import generate_simplified_trajectory, ts

logger = logging.getLogger(__name__)

bp = Blueprint("risks", url_prefix="/api")


@bp.get("/orbit_risk")
async def orbit_collision_risk(request):
    """
    Рассчет риска при нахождении на орбите.
    """
    request_start_time = time.time()
    try:
        height = float(request.args["height"][0])
        a_effective = float(request.args["A_effective"][0])
        t_years = float(request.args["T_years"][0])
        c_full = float(request.args["C_full"][0])
        d_lost = float(request.args["D_lost"][0])
        v_rel = (
            float(request.args.get("V_rel")[0]) if request.args.get("V_rel") else 12.5
        )

        all_objects = get_all_trackable_objects()

        _, filtered_sats = calculate_orbit_congestion_by_altitude(
            all_objects, height - 50, height + 50, 0, 180
        )
        total_objects_in_layer = len(filtered_sats)

        orbit_risk_data = calculate_collision_financial_risk(
            total_objects_in_layer,
            height + 50,
            height - 50,
            v_rel,
            a_effective,
            t_years,
            c_full,
            d_lost,
        )

        logger.info(f"Запрос /orbit_risk успешно обработан за {time.time() - request_start_time:.4f} сек.")
        return json(orbit_risk_data)

    except Exception as e:
        logger.error(f"Ошибка в /orbit_risk: {e}", exc_info=True)
        return json({"message": "An error occurred"}, status=500)


@bp.get("/takeoff_risk")
async def takeoff_collision_risk(request):
    """
    Рассчитывает ОБЩИЙ УСРЕДНЕННЫЙ риск при запуске, используя гибридный статистический метод.
    """
    request_start_time = time.time()
    logger.info(f"Начало обработки запроса /takeoff_risk (гибридный метод) с параметрами: {request.args}")

    try:
        launch_lat = float(request.args["lat"][0])
        launch_lon = float(request.args["lon"][0])
        target_altitude = float(request.args["altitude"][0])
        inclination = float(request.args["inclination"][0])
        a_rocket = float(request.args["A_rocket"][0])
        c_total_loss = float(request.args["C_total_loss"][0])

        # Шаг 1: Генерируем эталонную траекторию
        trajectory = generate_simplified_trajectory(
            launch_lat, launch_lon, target_altitude, inclination
        )
        if not trajectory or len(trajectory) < 2:
            return json({"message": "Failed to generate trajectory."}, status=500)

        ascent_time_s = len(trajectory) * 10
        logger.info(f"Шаг 1: Траектория сгенерирована. Расчетное время полета: {ascent_time_s} сек.")

        # Шаг 2: Создаем габаритный контейнер (bounding box) вокруг траектории
        all_pos = np.array([p['position'] for p in trajectory])
        min_coords = np.min(all_pos, axis=0) - 200  # Запас 200 км
        max_coords = np.max(all_pos, axis=0) + 200  # Запас 200 км
        logger.info("Шаг 2: Габаритный контейнер для траектории создан.")

        # Шаг 3: Находим все объекты, чьи орбиты пересекают наш контейнер
        all_objects = get_all_trackable_objects()
        intersecting_sats = []

        for sat_data in all_objects:
            try:
                satellite = EarthSatellite(sat_data['line1'], sat_data['line2'], 'sat', ts)
                # Рассчитываем одну точку на орбите, чтобы проверить, не слишком ли она далеко
                t = ts.now()
                pos = satellite.at(t).position.km
                # Грубая проверка - если объект сейчас очень далеко, его орбита вряд ли пересечет контейнер
                if np.linalg.norm(pos) > 15000: continue

                # Проверяем пересечение с контейнером (упрощенная проверка)
                # Берем несколько точек с орбиты и смотрим, попадает ли хоть одна в контейнер
                period_minutes = (1 / (satellite.model.no_kozai * (1440.0 / (2 * np.pi)))) * 1440
                if period_minutes == 0: continue

                times = ts.utc(t.utc.year, t.utc.month, t.utc.day, t.utc.hour,
                               np.arange(0, period_minutes, 5) * 60 / 3600)
                sat_path = satellite.at(times).position.km.T

                inside = np.any(np.all((sat_path >= min_coords) & (sat_path <= max_coords), axis=1))
                if inside:
                    intersecting_sats.append(sat_data)

            except Exception:
                continue

        N_objects = len(intersecting_sats)
        logger.info(f"Шаг 3: Найдено {N_objects} объектов, чьи орбиты пересекают коридор запуска.")

        # Шаг 4: Расчет статистического риска
        avg_radius_km = 75  # Средний радиус для расчета объема
        trajectory_length_km = sum(np.linalg.norm(trajectory[i + 1]['position'] - trajectory[i]['position']) for i in
                                   range(len(trajectory) - 1))
        corridor_volume_km3 = np.pi * (avg_radius_km ** 2) * trajectory_length_km

        if corridor_volume_km3 == 0:
            return json({"message": "Corridor volume is zero."}, status=500)

        density = N_objects / corridor_volume_km3
        V_rel_km_s = 10.0
        A_effective_km2 = a_rocket / 1_000_000

        expected_collisions = density * V_rel_km_s * A_effective_km2 * ascent_time_s
        P_collision = 1.0 - math.exp(-expected_collisions)
        financial_risk = P_collision * c_total_loss

        takeoff_risk_data = {
            "financial_risk": round(financial_risk, 2),
            "collision_risk": P_collision,
            "insurance_premium": round(financial_risk * 1.5, 2),
            "risk_class": "A+ (Minimal)" if P_collision < 1e-7 else "A (Very Low)" if P_collision < 1e-6 else "B (Low)" if P_collision < 1e-5 else "C (Moderate)" if P_collision < 1e-4 else "D (High)" if P_collision < 1e-3 else "E (Very High)" if P_collision < 1e-2 else "F (Extremely High)",
            "risk_class_description": "...",
            "object_count": N_objects,
            "launch_corridor_radius_km": avg_radius_km
        }

        total_time = time.time() - request_start_time
        logger.info(f"Запрос /takeoff_risk (гибридный) успешно обработан за {total_time:.4f} сек.")

        return json(takeoff_risk_data)

    except Exception as e:
        logger.error(f"Критическая ошибка в /takeoff_risk: {e}", exc_info=True)
        return json({"message": f"An internal error occurred: {e}"}, status=500)