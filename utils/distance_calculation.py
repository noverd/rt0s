from math import cos, sqrt


def quick_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    x = lat2 - lat1
    y = (lng2 - lng1) * cos((lat2 + lat1) * 0.00872664626)
    return int(111138 * sqrt(x * x + y * y))
