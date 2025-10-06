import logging
import time
from datetime import datetime, timezone, timedelta

from sanic import Blueprint
from sanic.response import json

from satellite_tracker import (
    get_all_trackable_objects,
    calculate_orbit_congestion_by_altitude,
    calculate_satellite_position,
)
import numpy as np

from utils.cpa_calculator import calculate_cpa
from utils.risk_calculator import (
    calculate_collision_financial_risk,
    calculate_launch_collision_risk,
)
from utils.trajectory import generate_simplified_trajectory

logger = logging.getLogger(__name__)

bp = Blueprint("risks", url_prefix="/api")


@bp.get("/orbit_risk")
async def orbit_collision_risk(request):
    """
    Рассчет риска при нахождении на орбите.
    openapi:
    parameters:
      - name: height
        in: query
        description: Высота на орбите (км)
        required: true
        schema:
          type: integer
          example: 550
      - name: A_effective
        in: query
        description: Эффективная площадь поперечного сечения (м^2)
        required: true
        schema:
          type: number
          format: float
          example: 1.5
      - name: T_years
        in: query
        description:  Срок службы миссии в годах
        required: true
        schema:
          type: integer
          example: 5
      - name: C_full
        in: query
        description: Полная стоимость миссии
        required: true
        schema:
          type: integer
          example: 50000000
      - name: D_lost
        in: query
        description:  Упущенный доход в случае потери спутника
        required: true
        schema:
          type: integer
          example: 100000000
      - name: V_rel
        in: query
        description: Средняя относительная скорость столкновения (км/c)
        required: false
        schema:
          type: number
          format: float
          example: 12.5
    """
    request_start_time = time.time()
    logger.info(f"Начало обработки запроса /orbit_risk с параметрами: {request.args}")

    try:
        height = float(request.args["height"][0])
        a_effective = float(request.args["A_effective"][0])
        t_years = float(request.args["T_years"][0])
        c_full = float(request.args["C_full"][0])
        d_lost = float(request.args["D_lost"][0])
        v_rel = (
            float(request.args.get("V_rel")[0]) if request.args.get("V_rel") else 12.5
        )

        # Этап 1: Получение всех отслеживаемых объектов
        step_start_time = time.time()
        all_objects = get_all_trackable_objects()
        logger.info(
            f"Шаг 1: get_all_trackable_objects завершен за {time.time() - step_start_time:.4f} сек. "
            f"Получено {len(all_objects)} объектов."
        )

        # Этап 2: Расчет плотности объектов на орбите
        step_start_time = time.time()
        congestion_map, _ = calculate_orbit_congestion_by_altitude(
            all_objects, height - 50, height + 50, 0, 180
        )
        total_objects_in_layer = sum(data["count"] for data in congestion_map.values())
        logger.info(
            f"Шаг 2: calculate_orbit_congestion_by_altitude завершен за {time.time() - step_start_time:.4f} сек. "
            f"Объектов в целевом слое: {total_objects_in_layer}."
        )

        # Этап 3: Расчет финансового риска
        step_start_time = time.time()
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
        logger.info(
            f"Шаг 3: calculate_collision_financial_risk завершен за {time.time() - step_start_time:.4f} сек."
        )

        logger.info(f"Итоговые данные по риску: {orbit_risk_data}")
        total_time = time.time() - request_start_time
        logger.info(f"Запрос /orbit_risk успешно обработан за {total_time:.4f} сек.")

        return json(orbit_risk_data)

    except KeyError as e:
        logger.error(f"Ошибка в /orbit_risk: отсутствует обязательный параметр {e}", exc_info=True)
        return json({"message": f"Missing required parameter: {e.args[0]}"}, status=400)
    except (ValueError, TypeError):
        logger.error("Ошибка в /orbit_risk: неверный тип параметра", exc_info=True)
        return json(
            {"message": "Invalid parameter type. Please provide valid numbers."},
            status=400,
        )


@bp.get("/takeoff_risk")
async def takeoff_collision_risk(request):
    """
    Рассчет риска при подъеме объекта по всей траектории до целевой орбиты.
    openapi:
    parameters:
        - name: lat
          in: query
          description: Широта места запуска.
          required: true
          schema:
            type: number
            format: float
            example: 45.96
        - name: lon
          in: query
          description: Долгота места запуска.
          required: true
          schema:
            type: number
            format: float
            example: 63.30
        - name: date
          in: query
          description: Дата и время запуска (UTC) в формате YYYY-MM-DDTHH:MM:SS.
          required: true
          schema:
            type: string
            example: "2025-10-04T12:00:00"
        - name: altitude
          in: query
          description: Целевая высота орбиты (км).
          required: true
          schema:
            type: number
            format: float
            example: 550
        - name: inclination
          in: query
          description: Целевое наклонение орбиты (градусы).
          required: true
          schema:
            type: number
            format: float
            example: 98.7
        - name: T_seconds
          in: query
          description: Продолжительность (секунды) активного участка полета.
          required: true
          schema:
            type: integer
            example: 540
        - name: A_rocket
          in: query
          description: Эффективная площадь поперечного сечения ракеты (м²).
          required: true
          schema:
            type: number
            format: float
            example: 15.8
        - name: C_total_loss
          in: query
          description: Суммарные потери при неудачном запуске.
          required: true
          schema:
            type: number
            format: float
            example: 50000000
        - name: launch_radius_meters
          in: query
          description: Радиус (в метрах) коридора запуска для обнаружения объектов.
          required: false
          schema:
            type: integer
            example: 25000
    """
    request_start_time = time.time()
    logger.info(f"Начало обработки запроса /takeoff_risk с параметрами: {request.args}")

    try:
        # Параметры
        launch_lat = float(request.args["lat"][0])
        launch_lon = float(request.args["lon"][0])
        target_altitude = float(request.args["altitude"][0])
        ascent_time_s = int(request.args["T_seconds"][0])
        inclination = float(request.args["inclination"][0])
        date_str = request.args["date"][0]
        a_rocket = float(request.args["A_rocket"][0])
        c_total_loss = float(request.args["C_total_loss"][0])
        # Преобразуем метры в км для CPA
        launch_corridor_km = (
            int(request.args.get("launch_radius_meters", ["25000"])[0]) / 1000.0
        )
        time_step_s = 10  # Шаг времени, используемый в генераторе траектории

        # Этап 1: Определение времени запуска
        step_start_time = time.time()
        launch_date = None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                launch_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                pass
        if launch_date is None:
            logger.error(f"Неверный формат даты: '{date_str}'")
            return json(
                {"message": f"Invalid date format for '{date_str}'."}, status=400
            )
        if launch_date.tzinfo is None:
            launch_date = launch_date.replace(tzinfo=timezone.utc)
        logger.info(
            f"Шаг 1: Определение времени запуска завершено за {time.time() - step_start_time:.4f} сек. "
            f"Время запуска: {launch_date}"
        )

        # Этап 2: Генерируем траекторию полета в виде векторов состояния
        step_start_time = time.time()
        trajectory = generate_simplified_trajectory(
            launch_lat,
            launch_lon,
            target_altitude,
            ascent_time_s,
            inclination,
            launch_date,
        )
        logger.info(
            f"Шаг 2: generate_simplified_trajectory завершен за {time.time() - step_start_time:.4f} сек. "
            f"Сгенерировано {len(trajectory)} векторов состояния."
        )

        # Этап 3: Получение и фильтрация спутников
        step_start_time = time.time()
        altitude_tolerance_km = 50  # Увеличим допуск, т.к. CPA может быть дальше
        inclination_tolerance = 15.0
        min_inclination = max(0, inclination - inclination_tolerance)
        max_inclination = min(180, inclination + inclination_tolerance)

        _, all_satellites_in_path = calculate_orbit_congestion_by_altitude(
            get_all_trackable_objects(),
            0,
            target_altitude + altitude_tolerance_km,
            min_inclination,
            max_inclination,
        )
        logger.info(
            f"Шаг 3: Фильтрация спутников завершена за {time.time() - step_start_time:.4f} сек. "
            f"Найдено {len(all_satellites_in_path)} объектов для проверки."
        )

        # Этап 4: Проверка конъюнкций с использованием CPA
        step_start_time = time.time()
        logger.info("Шаг 4: Начало проверки конъюнкций методом CPA...")
        dangerous_conjunctions = 0
        processed_satellites = set()

        for i in range(len(trajectory) - 1):
            rocket_segment = trajectory[i]
            # Векторы состояния ракеты в начале сегмента
            rocket_pos1 = rocket_segment["position"]
            rocket_vel1 = rocket_segment["velocity"]

            for sat_data in all_satellites_in_path:
                sat_id = sat_data.get("number")
                if (sat_id, i) in processed_satellites:
                    continue
                try:
                    # Векторы состояния спутника в начале того же сегмента
                    sat_state = calculate_satellite_position(
                        sat_data, rocket_segment["time_obj"]
                    )
                    sat_pos1 = sat_state["position"]
                    sat_vel1 = sat_state["velocity"]

                    # Расчет CPA
                    cpa_result = calculate_cpa(
                        rocket_pos1, rocket_vel1, sat_pos1, sat_vel1
                    )
                    t_cpa = cpa_result["time"]
                    dist_cpa = cpa_result["distance"]

                    # Проверяем, что сближение происходит внутри нашего временного окна
                    # и на опасном расстоянии
                    if 0 <= t_cpa <= time_step_s and dist_cpa < launch_corridor_km:
                        dangerous_conjunctions += 1
                        logger.info(
                            f"Найдено сближение! №{dangerous_conjunctions}. "
                            f"Спутник: {sat_data.get('name', 'N/A')} ({sat_id}), "
                            f"Сегмент траектории: {i}, "
                            f"Время до CPA: {t_cpa:.2f} сек, "
                            f"Дистанция: {dist_cpa * 1000:.2f} м."
                        )
                        processed_satellites.add((sat_id, i))

                except Exception as e:
                    logger.warning(
                        f"Ошибка при обработке CPA для спутника {sat_data.get('name')}: {e}"
                    )
                    continue

        logger.info(
            f"Шаг 4: Проверка конъюнкций CPA завершена за {time.time() - step_start_time:.4f} сек. "
            f"Всего найдено опасных сближений: {dangerous_conjunctions}."
        )

        # Этап 5: Расчет финансового риска
        step_start_time = time.time()
        takeoff_risk_data = calculate_launch_collision_risk(
            N_conjunctions=dangerous_conjunctions,
            launch_cylinder_radius_m=launch_corridor_km * 1000,
            A_rocket=a_rocket,
            C_total_loss=c_total_loss,
        )
        logger.info(
            f"Шаг 5: calculate_launch_collision_risk завершен за {time.time() - step_start_time:.4f} сек."
        )

        takeoff_risk_data["launch_corridor_radius_km"] = launch_corridor_km

        logger.info(f"Итоговые данные по риску: {takeoff_risk_data}")
        total_time = time.time() - request_start_time
        logger.info(f"Запрос /takeoff_risk успешно обработан за {total_time:.4f} сек.")

        return json(takeoff_risk_data)

    except KeyError as e:
        logger.error(
            f"Ошибка в /takeoff_risk: отсутствует обязательный параметр {e}",
            exc_info=True,
        )
        return json({"message": f"Missing required parameter: {e.args[0]}"}, status=400)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Ошибка в /takeoff_risk: неверный или отсутствующий тип параметра: {e}",
            exc_info=True,
        )
        return json(
            {
                "message": f"Invalid or missing parameter type. Please provide valid numbers. Error: {e}"
            },
            status=400,
        )