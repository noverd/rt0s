import math
import numpy as np
from datetime import timedelta, timezone, datetime
from skyfield.api import load, EarthSatellite
from skyfield.toposlib import wgs84

ts = load.timescale()
R_EARTH_KM = 6371.0
MU_KM3_PER_S2 = 398600.4418  # Гравитационный параметр Земли


def generate_simplified_trajectory(
        launch_lat,
        launch_lon,
        target_altitude_km,
        inclination_deg,
):
    """
    Генерирует эталонную траекторию запуска для определения ее геометрии.
    Использует фиксированную дату, так как нам важен путь, а не точное время.
    """
    time_step_s = 10
    max_flight_time_s = 1500
    launch_date = datetime.now(timezone.utc)  # Дата нужна только для расчетов skyfield

    t_launch = ts.from_datetime(launch_date)
    launch_site = wgs84.latlon(launch_lat, launch_lon, elevation_m=0)
    launch_site_gcrs = launch_site.at(t_launch)

    inclination_rad = math.radians(inclination_deg)
    lat_rad = math.radians(launch_lat)

    try:
        cos_azimuth_arg = math.cos(inclination_rad) / math.cos(lat_rad)
        azimuth_rad = math.acos(np.clip(cos_azimuth_arg, -1.0, 1.0))
    except ValueError:
        azimuth_rad = 0.0

    thrust_local = np.array([math.sin(azimuth_rad), math.cos(azimuth_rad), 0.35])
    thrust_local /= np.linalg.norm(thrust_local)

    trajectory = []

    current_pos_gcrs = launch_site_gcrs.position.km
    current_vel_gcrs = launch_site_gcrs.velocity.km_per_s

    target_orbital_radius = R_EARTH_KM + target_altitude_km
    target_orbital_speed = math.sqrt(MU_KM3_PER_S2 / target_orbital_radius)

    estimated_ascent_time = 600
    required_delta_v = target_orbital_speed - np.linalg.norm(current_vel_gcrs)
    thrust_acceleration_scalar = (required_delta_v / estimated_ascent_time) * 1.8

    time_s = 0
    current_altitude = 0
    current_speed = 0

    while not (
            current_altitude >= target_altitude_km and current_speed >= target_orbital_speed) and time_s < max_flight_time_s:
        dist_from_center = np.linalg.norm(current_pos_gcrs)
        current_altitude = dist_from_center - R_EARTH_KM
        current_speed = np.linalg.norm(current_vel_gcrs)

        z_axis_gcrs = np.array([0, 0, 1])
        up_vec = current_pos_gcrs / dist_from_center
        east_vec = np.cross(z_axis_gcrs, up_vec)
        east_vec /= np.linalg.norm(east_vec)
        north_vec = np.cross(up_vec, east_vec)
        local_to_gcrs_matrix = np.column_stack((east_vec, north_vec, up_vec))
        thrust_vector_gcrs = local_to_gcrs_matrix @ thrust_local

        gravity_accel_scalar = -MU_KM3_PER_S2 / (dist_from_center ** 2)
        gravity_vector = up_vec * gravity_accel_scalar

        thrust_acceleration_vector = thrust_vector_gcrs * thrust_acceleration_scalar
        total_acceleration_vector = thrust_acceleration_vector + gravity_vector

        current_vel_gcrs += total_acceleration_vector * time_step_s
        current_pos_gcrs += current_vel_gcrs * time_step_s

        trajectory.append({
            "position": current_pos_gcrs.copy(),
            "velocity": current_vel_gcrs.copy()
        })
        time_s += time_step_s

    return trajectory