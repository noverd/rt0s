import math

# Константы, используемые в формуле
# Rз (Радиус Земли, км)
R_EARTH_KM = 6371.0
# Количество секунд в одном году
SEC_PER_YEAR = 31536000
# Коэффициент для расчета страховой премии (150%)
INSURANCE_COEFFICIENT = 1.5

RISK_CLASS_DESCRIPTIONS = {
    "F (Extremely High)": "Вероятность столкновения чрезвычайно высока (>1%). Требуются срочные меры по снижению риска или пересмотр миссии.",
    "E (Very High)": "Очень высокая вероятность столкновения (>0.1%). Миссия подвержена значительному риску.",
    "D (High)": "Высокая вероятность столкновения (>0.01%). Рекомендуется детальный анализ и возможная коррекция орбиты.",
    "C (Moderate)": "Умеренная вероятность столкновения (>0.001%). Стандартный уровень риска для многих орбит, требует мониторинга.",
    "B (Low)": "Низкая вероятность столкновения (>0.0001%). Считается приемлемым для большинства миссий.",
    "A (Very Low)": "Очень низкая вероятность столкновения (>0.00001%). Орбита считается безопасной.",
    "A+ (Minimal)": "Минимальная вероятность столкновения. Риск практически отсутствует.",
}


def assign_risk_class(collision_probability: float) -> str:
    """
    Присваивает класс риска на основе вероятности столкновения.
    """
    if collision_probability > 1e-2:  # > 1%
        return "F (Extremely High)"
    if collision_probability > 1e-3:  # > 0.1%
        return "E (Very High)"
    if collision_probability > 1e-4:  # > 0.01%
        return "D (High)"
    if collision_probability > 1e-5:  # > 0.001%
        return "C (Moderate)"
    if collision_probability > 1e-6:  # > 0.0001%
        return "B (Low)"
    if collision_probability > 1e-7:  # > 0.00001%
        return "A (Very Low)"
    return "A+ (Minimal)"


def calculate_collision_financial_risk(
    N_objects: float,
    H_upper: float,
    H_lower: float,
    V_rel: float,
    A_effective: float,
    T_years: float,
    C_full: float,
    D_lost: float,
) -> dict:
    """
    Рассчитывает ожидаемый финансовый риск (ФР) из-за столкновения
    космического аппарата с мусором за весь срок миссии.
    """
    R_upper = R_EARTH_KM + H_upper
    R_lower = R_EARTH_KM + H_lower
    V_shell = (4 / 3) * math.pi * (R_upper**3 - R_lower**3)

    if V_shell <= 0:
        return {"error": "Invalid altitude range, shell volume is zero or negative."}

    density = N_objects / V_shell
    T_seconds = T_years * SEC_PER_YEAR
    A_effective_km2 = A_effective / 1_000_000

    expected_collisions = density * V_rel * A_effective_km2 * T_seconds
    P_collision = 1.0 - math.exp(-expected_collisions)

    total_cost_at_risk = C_full + D_lost
    financial_risk = P_collision * total_cost_at_risk

    # --- НОВЫЕ РАСЧЕТЫ ---
    insurance_premium = financial_risk * INSURANCE_COEFFICIENT
    risk_class = assign_risk_class(P_collision)

    return {
        "financial_risk": round(financial_risk, 2),
        "collision_risk": P_collision,
        "insurance_premium": round(insurance_premium, 2),
        "risk_class": risk_class,
        "risk_class_description": RISK_CLASS_DESCRIPTIONS.get(risk_class, "Описание не найдено."),
        "object_count": N_objects,
    }


def calculate_launch_collision_risk(
    N_conjunctions: int,
    launch_cylinder_radius_m: int,
    A_rocket: float,
    C_total_loss: float,
) -> dict:
    """
    Рассчитывает ожидаемый финансовый риск из-за столкновения
    на основе прямого подсчета опасных сближений (конъюнкций).
    """
    if launch_cylinder_radius_m <= 0:
        return {"error": "Launch corridor radius must be positive."}

    # Вероятность столкновения для одного объекта, проходящего через коридор
    A_rocket_m2 = A_rocket
    corridor_cross_section_m2 = math.pi * (launch_cylinder_radius_m**2)

    # Чтобы избежать деления на ноль
    if corridor_cross_section_m2 == 0:
        p_one_conjunction = 1.0 if N_conjunctions > 0 else 0.0
    else:
        p_one_conjunction = A_rocket_m2 / corridor_cross_section_m2

    # Защита от физически невозможных сценариев
    p_one_conjunction = min(p_one_conjunction, 1.0)

    # Общая вероятность столкновения: P_total = 1 - (1 - p_one)^N
    P_collision = 1.0 - (1.0 - p_one_conjunction)**N_conjunctions

    financial_risk = P_collision * C_total_loss
    insurance_premium = financial_risk * INSURANCE_COEFFICIENT
    risk_class = assign_risk_class(P_collision)

    return {
        "financial_risk": round(financial_risk, 2),
        "collision_risk": P_collision,
        "insurance_premium": round(insurance_premium, 2),
        "risk_class": risk_class,
        "risk_class_description": RISK_CLASS_DESCRIPTIONS.get(
            risk_class, "Описание не найдено."
        ),
        "object_count": N_conjunctions,
    }

