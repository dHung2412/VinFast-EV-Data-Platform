from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Cities — 8 tỉnh/thành phố
# ---------------------------------------------------------------------------
CITIES = {
    "HN": {"name": "Ha Noi", "lat": 21.0285, "lon": 105.8542},
    "SG": {"name": "Ho Chi Minh", "lat": 10.7769, "lon": 106.7009},
    "DN": {"name": "Da Nang", "lat": 16.0544, "lon": 108.2022},
    "TH": {"name": "Thanh Hoa", "lat": 19.8071, "lon": 105.7764},
    "TN": {"name": "Thai Nguyen", "lat": 21.5925, "lon": 105.8442},
    "NA": {"name": "Nghe An", "lat": 18.6736, "lon": 105.6814},
    "HT": {"name": "Ha Tinh", "lat": 18.3431, "lon": 105.9016},
    "QN": {"name": "Quang Ninh", "lat": 20.40, "lon": 106.26},
}

AMBIENT_BY_CITY = {
    "HN": {"mean": 31.5, "amp": 4.2},
    "SG": {"mean": 30.2, "amp": 3.0},
    "DN": {"mean": 30.5, "amp": 3.6},
    "TH": {"mean": 30.8, "amp": 3.8},
    "TN": {"mean": 29.5, "amp": 4.5},
    "NA": {"mean": 30.8, "amp": 3.8},
    "HT": {"mean": 30.6, "amp": 3.7},
    "QN": {"mean": 30.0, "amp": 3.2},
}

# ---------------------------------------------------------------------------
# Vehicle models — 7 ô tô + 3 xe máy điện với physics params
# ---------------------------------------------------------------------------
VEHICLE_MODELS: dict[str, dict] = {
    # --- ô tô ---
    "VF 3": {
        "battery_kwh": 18.64, "wh_per_km": 78.0,
        "mass_kg": 1750, "Cd": 0.31, "A_frontal_m2": 2.45,
        "r_wheel_m": 0.305, "gear_ratio": 9.3,
        "V_pack_nom_v": 350, "R_int_base_ohm": 0.080,
        "type": "car",
    },
    "VF 5": {
        "battery_kwh": 37.23, "wh_per_km": 110.0,
        "mass_kg": 1900, "Cd": 0.30, "A_frontal_m2": 2.55,
        "r_wheel_m": 0.318, "gear_ratio": 9.5,
        "V_pack_nom_v": 360, "R_int_base_ohm": 0.060,
        "type": "car",
    },
    "VF e34": {
        "battery_kwh": 42.00, "wh_per_km": 125.0,
        "mass_kg": 1950, "Cd": 0.30, "A_frontal_m2": 2.55,
        "r_wheel_m": 0.318, "gear_ratio": 9.5,
        "V_pack_nom_v": 370, "R_int_base_ohm": 0.055,
        "type": "car",
    },
    "VF 6": {
        "battery_kwh": 59.68, "wh_per_km": 130.0,
        "mass_kg": 2150, "Cd": 0.29, "A_frontal_m2": 2.62,
        "r_wheel_m": 0.330, "gear_ratio": 10.0,
        "V_pack_nom_v": 380, "R_int_base_ohm": 0.045,
        "type": "car",
    },
    "VF 7": {
        "battery_kwh": 75.30, "wh_per_km": 140.0,
        "mass_kg": 2350, "Cd": 0.28, "A_frontal_m2": 2.65,
        "r_wheel_m": 0.335, "gear_ratio": 10.2,
        "V_pack_nom_v": 400, "R_int_base_ohm": 0.040,
        "type": "car",
    },
    "VF 8": {
        "battery_kwh": 87.70, "wh_per_km": 150.0,
        "mass_kg": 2600, "Cd": 0.28, "A_frontal_m2": 2.70,
        "r_wheel_m": 0.345, "gear_ratio": 10.5,
        "V_pack_nom_v": 400, "R_int_base_ohm": 0.038,
        "type": "car",
    },
    "VF 9": {
        "battery_kwh": 92.30, "wh_per_km": 155.0,
        "mass_kg": 2750, "Cd": 0.30, "A_frontal_m2": 2.85,
        "r_wheel_m": 0.345, "gear_ratio": 10.5,
        "V_pack_nom_v": 400, "R_int_base_ohm": 0.036,
        "type": "car",
    },
    # --- xe máy điện ---
    "VF Amio S": {
        "battery_kwh": 1.10, "wh_per_km": 15.75,
        "mass_kg": 75, "Cd": 0.90, "A_frontal_m2": 0.55,
        "r_wheel_m": 0.20, "gear_ratio": 6.5,
        "V_pack_nom_v": 48, "R_int_base_ohm": 0.120,
        "type": "motorbike",
    },
    "VF Evo Lite S": {
        "battery_kwh": 1.50, "wh_per_km": 17.65,
        "mass_kg": 85, "Cd": 0.90, "A_frontal_m2": 0.55,
        "r_wheel_m": 0.20, "gear_ratio": 6.5,
        "V_pack_nom_v": 52, "R_int_base_ohm": 0.100,
        "type": "motorbike",
    },
    "VF Flazz S": {
        "battery_kwh": 1.20, "wh_per_km": 17.14,
        "mass_kg": 80, "Cd": 0.90, "A_frontal_m2": 0.55,
        "r_wheel_m": 0.20, "gear_ratio": 6.5,
        "V_pack_nom_v": 48, "R_int_base_ohm": 0.110,
        "type": "motorbike",
    },
}

CAR_MODELS = ["VF 3", "VF 5", "VF e34", "VF 6", "VF 7", "VF 8", "VF 9"]
MOTORBIKE_MODELS = ["VF Amio S", "VF Evo Lite S", "VF Flazz S"]

MODEL_WEIGHTS_CAR = [0.12, 0.16, 0.08, 0.20, 0.20, 0.14, 0.10]
MODEL_WEIGHTS_BIKE = [0.35, 0.40, 0.25]

# ---------------------------------------------------------------------------
# User generation helpers
# ---------------------------------------------------------------------------
_VIET_SURNAMES = [
    "Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Dang", "Bui", "Do",
    "Ho", "Ngo", "Duong", "Ly", "Truong", "Dinh", "Vo", "Mai", "Cao", "Ha",
]
_VIET_MIDDLENAMES = ["Van", "Thi", "Minh", "Ngoc", "Duc", "Huu", "Quang", "Thanh", "Xuan", "Kim", "Anh", "Bao", ""]
_VIET_GIVEN = [
    "An", "Binh", "Cuong", "Dung", "Dat", "Hai", "Huy", "Khoa", "Lam", "Long",
    "Minh", "Nam", "Phuc", "Quang", "Son", "Tuan", "Viet", "Hung", "Linh", "Huong",
    "Lan", "Mai", "Hoa", "Thao", "Trang", "Ngoc", "Phuong", "Ha", "Giang", "Thu",
]

_PHONE_PREFIXES = ["090", "091", "092", "093", "094", "096", "097", "098", "086", "038", "032", "033", "034", "035", "036", "037", "039", "089", "088", "087"]


def _random_viet_name(rng: np.random.Generator) -> str:
    surname = str(rng.choice(_VIET_SURNAMES))
    mid = str(rng.choice(_VIET_MIDDLENAMES))
    given = str(rng.choice(_VIET_GIVEN))
    return f"{surname} {mid} {given}".replace("  ", " ").strip()


def _random_phone(rng: np.random.Generator) -> str:
    prefix = str(rng.choice(_PHONE_PREFIXES))
    suffix = "".join(str(rng.integers(0, 10)) for _ in range(7))
    return prefix + suffix


def build_users(n_users: int, rng: np.random.Generator) -> list[dict]:
    return [
        {
            "u_id": f"USR-{i:05d}",
            "name": _random_viet_name(rng),
            "phone": _random_phone(rng),
        }
        for i in range(1, n_users + 1)
    ]


def _pick_model(rng: np.random.Generator) -> str:
    if rng.random() < 0.65:
        return str(rng.choice(CAR_MODELS, p=MODEL_WEIGHTS_CAR))
    return str(rng.choice(MOTORBIKE_MODELS, p=MODEL_WEIGHTS_BIKE))


def _assign_vehicles_per_user(n_users: int, rng: np.random.Generator) -> list[list[str]]:
    """Phân bổ ngẫu nhiên số xe (1-3 xe) và mẫu xe cho từng người dùng."""
    counts = rng.choice([1, 2, 3], size=n_users, p=[0.80, 0.15, 0.05])
    return [[_pick_model(rng) for _ in range(cnt)] for cnt in counts]


def _soh_init(odometer_km: float, rng: np.random.Generator) -> float:
    # Suy hao của pin theo quãng đường
    soh = 100.0 - (odometer_km / 10000.0) * 0.7 + float(rng.normal(0, 0.05))
    return float(np.clip(soh, 85.0, 100.0))


def _create_vehicle_dict(vid: int, u_id: str, model: str, city_code: str, rng: np.random.Generator) -> dict:
    """Tạo cấu trúc dict thông số chi tiết cho một phương tiện."""
    spec = VEHICLE_MODELS[model]
    center = CITIES[city_code]
    is_car = spec["type"] == "car"

    if is_car:
        odo = float(rng.uniform(1000, 60000))
        tire_base = float(rng.uniform(2.25, 2.45))
    else:
        odo = float(rng.uniform(500, 25000))
        tire_base = float(rng.uniform(2.0, 2.4))

    years_old = float(rng.uniform(0.2, 5.0))
    soh = _soh_init(odo, rng)

    return {
        "vehicle_id": f"VFS-{vid:05d}",
        "u_id": u_id,
        "model": model,
        "type": spec["type"],
        "city_code": city_code,
        "home_lat": float(center["lat"] + rng.normal(0, 0.035)),
        "home_lon": float(center["lon"] + rng.normal(0, 0.035)),
        "work_lat": float(center["lat"] + rng.normal(0, 0.02)),
        "work_lon": float(center["lon"] + rng.normal(0, 0.02)),
        "battery_kwh": float(spec["battery_kwh"]),
        "wh_per_km": float(spec["wh_per_km"]),
        "mass_kg": float(spec["mass_kg"]),
        "Cd": float(spec["Cd"]),
        "A_frontal_m2": float(spec["A_frontal_m2"]),
        "r_wheel_m": float(spec["r_wheel_m"]),
        "gear_ratio": float(spec["gear_ratio"]),
        "V_pack_nom_v": float(spec["V_pack_nom_v"]),
        "R_int_base_ohm": float(spec["R_int_base_ohm"]),
        "odometer_start_km": odo,
        "tire_pressure_base_bar": tire_base,
        "battery_soh_pct": soh,
        "years_old": years_old,
    }


def build_fleet_with_users(users: list[dict], rng: np.random.Generator) -> list[dict]:
    city_codes = list(CITIES)
    fleet: list[dict] = []
    user_vehicles = _assign_vehicles_per_user(len(users), rng)
    vid = 1

    for user, models in zip(users, user_vehicles):
        for model in models:
            city_code = str(rng.choice(city_codes))
            vehicle = _create_vehicle_dict(vid, user["u_id"], model, city_code, rng)
            fleet.append(vehicle)
            vid += 1

    return fleet


def build_stations(rng: np.random.Generator) -> list[dict]:
    per_city = {"HN": 12, "SG": 12, "DN": 8, "TH": 6, "TN": 5, "NA": 6, "HT": 5}
    stations: list[dict] = []
    idx = 1

    for city, count in per_city.items():
        center = CITIES[city]
        for _ in range(count):
            charger_type = str(rng.choice(["AC_TYPE2", "CCS2_DC"], p=[0.55, 0.45]))
            power = float(rng.choice([11.0, 22.0])) if charger_type == "AC_TYPE2" else float(rng.choice([120.0, 150.0, 250.0]))
            stations.append({
                "station_id": f"CS-{city}-{idx:03d}",
                "city_code": city,
                "charger_type": charger_type,
                "max_power_kw": power,
                "num_chargers": int(rng.integers(2, 13)),
                "lat": float(center["lat"] + rng.normal(0, 0.04)),
                "lon": float(center["lon"] + rng.normal(0, 0.04)),
            })
            idx += 1

    return stations
