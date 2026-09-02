from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_generator.telemetry.physics import (
    ALPHA_SOLAR,
    A_ROOF,
    COP_AC,
    COP_HEAT,
    CP_CABIN,
    CP_CELL,
    CP_INV,
    CP_MOTOR,
    CELL_MASS_PER_KWH,
    K_HEAT,
    M_CABIN,
    M_INV,
    M_MOTOR_BIKE,
    M_MOTOR_CAR,
    R_TH_CABIN,
    R_TH_INV,
    R_TH_MOTOR_BIKE,
    R_TH_MOTOR_CAR,
    R_TH_PACK_BIKE,
    R_TH_PACK_CAR,
    drag_force,
    soh_decrement,
    rolling_resistance,
    inertia_force,
    grade_force,
    compute_motor_rpm,
    powertrain_power,
    pack_ocv,
    pack_current,
    internal_resistance,
    joule_heating,
    thermal_step,
    solar_irradiance,
    cabin_heat_load,
    hvac_power as hvac_power_fn,
    charge_curve_power,
    tire_pressure as tire_p_fn,
    tire_temp_from_ambient,
)

# ---------------------------------------------------------------------------
# Hằng số cấu hình mô phỏng (Simulation Constants)
# ---------------------------------------------------------------------------
SAMPLE_SECONDS_DRIVING = 10     # Tần số lấy mẫu dữ liệu khi lái xe (10 giây / mẫu)
SAMPLE_SECONDS_CHARGING = 60    # Tần số lấy mẫu dữ liệu khi sạc pin (60 giây / mẫu)
MINUTES_PER_DAY = 1440          # Tổng số phút trong một ngày (24 giờ * 60 phút)
TIRE_POSITIONS = ["fl", "fr", "rl", "rr"]  # Vị trí các lốp xe (trước-trái, trước-phải, sau-trái, sau-phải)


def ambient_curve(minutes: np.ndarray, mean: float, amp: float) -> np.ndarray:
    """Tính mảng nhiệt độ môi trường (C) biến thiên dạng hình cosin trong ngày (cực đại lúc 14h, cực tiểu lúc 2h sáng)."""
    hours = minutes / 60.0
    return mean + amp * np.cos(2 * np.pi * (hours - 14.0) / 24.0)


def empty_activity(day_start_iso: str, vehicle_id: str) -> pd.DataFrame:
    """Tạo DataFrame rỗng chuẩn lược đồ đại diện cho ngày xe không hoạt động."""
    df = pd.DataFrame(
        {
            "day_start": pd.Series([day_start_iso], dtype="object"),
            "_off_min": pd.Series([-1], dtype="int64"),
            "vehicle_id": pd.Series([vehicle_id], dtype="object"),
            "model": pd.Series([""], dtype="object"),
        }
    )
    return df.iloc[0:0]


def build_frame(
    vehicle: dict,
    day_start_iso: str,
    off_min: np.ndarray,
    off_seconds: np.ndarray | None,
    speed: np.ndarray,
    soc: np.ndarray,
    soh: np.ndarray,
    battery_temp: np.ndarray,
    battery_temp_avg: np.ndarray,
    battery_temp_max: np.ndarray,
    charging_status: np.ndarray,
    motor_rpm_arr: np.ndarray,
    motor_temp: np.ndarray,
    inverter_temp: np.ndarray,
    gear_mode: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
    acc_x: np.ndarray,
    acc_y: np.ndarray,
    acc_z: np.ndarray,
    lock_status: np.ndarray,
    cabin_temp: np.ndarray,
    hvac_kw: np.ndarray,
    airbag: np.ndarray,
    odometer: np.ndarray,
    is_charging: bool,
    charging_power_kw: np.ndarray,
    ignition_on: bool,
    ambient: np.ndarray,
    tire_pressures: dict[str, np.ndarray],
) -> pd.DataFrame:
    n = len(off_min)
    if off_seconds is None:
        off_seconds = off_min.astype(float) * 60.0

    is_car = vehicle.get("type", "car") == "car"

    data: dict[str, np.ndarray | list] = {
        "day_start": [day_start_iso] * n,
        "_off_min": off_min.astype(np.int64),
        "_off_seconds": off_seconds.astype(np.int64),
        "vehicle_id": [vehicle["vehicle_id"]] * n,
        "u_id": [vehicle.get("u_id", "")] * n,
        "model": [vehicle["model"]] * n,
        "type": [vehicle.get("type", "car")] * n,
        "speed_kmh": np.round(speed, 1),
        "battery_soc_pct": np.round(soc, 2),
        "battery_soh_pct": np.round(soh, 2),
        "battery_temp_c": np.round(battery_temp, 1),
        "battery_temp_avg_c": np.round(battery_temp_avg, 1),
        "battery_temp_max_c": np.round(battery_temp_max, 1),
        "charging_status": charging_status.astype(object),
        "motor_rpm": np.round(motor_rpm_arr, 0).astype(int),
        "motor_temp_c": np.round(motor_temp, 1),
        "inverter_temp_c": np.round(inverter_temp, 1),
        "gear_mode": gear_mode.astype(object),
        "latitude": latitude,
        "longitude": longitude,
        "acceleration_x": np.round(acc_x, 2),
        "acceleration_y": np.round(acc_y, 2),
        "acceleration_z": np.round(acc_z, 2),
        "lock_status": lock_status.astype(object),
        "cabin_temp_c": np.round(cabin_temp, 1) if is_car else np.full(n, np.nan),
        "hvac_power_kw": np.round(hvac_kw, 2),
        "airbag_deployed": airbag.astype(bool),
        "odometer_km": np.round(odometer, 2),
        "tire_pressure_fl_bar": np.round(tire_pressures["fl"], 2),
        "tire_pressure_fr_bar": np.round(tire_pressures["fr"], 2),
        "tire_pressure_rl_bar": np.round(tire_pressures["rl"], 2) if is_car else np.full(n, np.nan),
        "tire_pressure_rr_bar": np.round(tire_pressures["rr"], 2) if is_car else np.full(n, np.nan),
        "ambient_temp_c": np.round(ambient, 1),
        "is_charging": np.full(n, is_charging, dtype=bool),
        "charging_power_kw": np.round(charging_power_kw, 2),
        "ignition_on": np.full(n, ignition_on, dtype=bool),
    }
    return pd.DataFrame(data)


def _driver_speed_profile(
    rng: np.random.Generator,
    n: int,
    dt_s: float,
    distance_km: float,
    is_bike: bool,
) -> np.ndarray:
    """Sinh chuỗi tốc độ di chuyển mượt mà của người lái có giới hạn gia tốc và điều chỉnh theo khoảng cách chuyến đi."""
    v_max = 70.0 if is_bike else 115.0
    base = float(rng.uniform(22.0, 42.0) if not is_bike else rng.uniform(18.0, 32.0))

    a_accel = 1.5 if is_bike else 2.5
    a_brake = -3.0 if not is_bike else -2.0
    a_hard = -6.5 if not is_bike else -4.0

    speeds = np.empty(n, dtype=float)
    v = float(rng.uniform(0, 8.0))

    for i in range(n):
        mu = (base - v) * 0.08
        a = float(rng.normal(mu, 0.9 if not is_bike else 0.6))

        # Phanh gấp ngẫu nhiên
        if rng.random() < 0.02:
            a = float(rng.uniform(a_hard, a_brake))
        a = float(np.clip(a, a_brake if rng.random() > 0.02 else a_hard, a_accel))

        # Giảm tốc do giao thông
        if rng.random() < 0.04:
            a = float(np.clip(a - 1.5, a_hard, a_accel))

        v = float(np.clip(v + a * dt_s, 0.0, v_max))

        # Dừng hẳn ngẫu nhiên
        if rng.random() < 0.015 and 5 < i < n - 5:
            v = 0.0

        speeds[i] = v

    # Điền chỉnh tỷ lệ tốc độ để tổng quãng đường khớp khoảng cách quy định (distance_km)
    dist_total = speeds.sum() * dt_s / 3600.0
    if dist_total <= 0.01:
        speeds[:] = float(rng.uniform(18.0, 32.0, 1)[0])
        dist_total = speeds.sum() * dt_s / 3600.0

    if dist_total > 0.01:
        speeds *= distance_km / dist_total
        speeds = np.clip(speeds, 0.0, v_max)
        dist2 = speeds.sum() * dt_s / 3600.0
        if abs(dist2 - distance_km) > 0.05:
            mask = speeds > 0.5
            if mask.sum() > 0:
                scale = distance_km / dist2
                speeds[mask] = np.clip(speeds[mask] * scale, 0.0, v_max)

    return speeds


def simulate_trip(
    rng: np.random.Generator,
    vehicle: dict,
    day_start_iso: str,
    *,
    start_off_min: int,
    distance_km: float,
    origin: dict,
    dest: dict,
    soc: float,
    soh: float,
    odometer: float,
    tire_base: float,
    puncture_tire: str | None,
    ambient_mean: float,
    ambient_amp: float,
) -> dict:
    """Mô phỏng chuỗi dữ liệu telemetry của một chuyến đi (di chuyển từ điểm A đến B)."""
    is_bike = vehicle.get("type", "car") == "motorbike"
    dt_s = SAMPLE_SECONDS_DRIVING

    avg_kmh = float(rng.uniform(18.0, 34.0)) if not is_bike else float(rng.uniform(14.0, 28.0))
    est_minutes = distance_km / max(avg_kmh, 5.0) * 60.0
    n_est = int(est_minutes * 60.0 / dt_s)
    n = int(np.clip(n_est, 6, 600))

    speeds = _driver_speed_profile(rng, n, dt_s, distance_km, is_bike)

    t_steps = np.arange(n)
    off_seconds = (start_off_min * 60 + t_steps * dt_s).astype(int)
    off_min = (off_seconds // 60).astype(int)
    minutes_float = off_seconds / 60.0
    hours_float = minutes_float / 60.0

    ambient = ambient_curve(minutes_float, ambient_mean, ambient_amp)

    v_ms = speeds / 3.6
    v_kmh = speeds
    dv = np.diff(v_ms, prepend=v_ms[0])
    a = dv / dt_s

    motor_rpm_arr = compute_motor_rpm(v_ms, vehicle["r_wheel_m"], vehicle["gear_ratio"])

    # Tính toán các lực cơ học
    F_drag = drag_force(v_ms, rho=1.184, Cd=vehicle["Cd"], A=vehicle["A_frontal_m2"])
    F_roll = rolling_resistance(v_kmh, vehicle["mass_kg"])
    F_inertia = inertia_force(a, vehicle["mass_kg"])

    is_hilly_city = vehicle["city_code"] in ("DN", "TN")
    if is_hilly_city and rng.random() < 0.18:
        grade_deg = float(rng.uniform(3.0, 6.0))
        half = n // 2
        grade_rad = np.deg2rad(grade_deg)
        F_grade_arr = np.empty(n)
        F_grade_arr[:half] = grade_force(vehicle["mass_kg"], theta_rad=grade_rad)
        F_grade_arr[half:] = grade_force(vehicle["mass_kg"], theta_rad=-grade_rad)
    else:
        F_grade_arr = np.zeros(n)

    # Ước tính nhiệt độ cabin và công suất phụ tải điều hòa (HVAC)
    n_occ = 1 if rng.random() < 0.7 else 2
    if is_bike:
        R_th_motor = R_TH_MOTOR_BIKE
        R_th_pack = R_TH_PACK_BIKE
        tau_motor = M_MOTOR_BIKE * CP_MOTOR * R_th_motor
        m_pack = vehicle["battery_kwh"] * CELL_MASS_PER_KWH
        tau_pack = m_pack * CP_CELL * R_th_pack
        tau_inv = M_INV * CP_INV * R_TH_INV
    else:
        R_th_motor = R_TH_MOTOR_CAR
        R_th_pack = R_TH_PACK_CAR
        tau_motor = M_MOTOR_CAR * CP_MOTOR * R_th_motor
        m_pack = vehicle["battery_kwh"] * CELL_MASS_PER_KWH
        tau_pack = m_pack * CP_CELL * R_th_pack
        tau_inv = M_INV * CP_INV * R_TH_INV

    T_cabin_prev = ambient[0]
    m_cabin_eq = M_CABIN + 3.0
    tau_cabin = m_cabin_eq * CP_CABIN * R_TH_CABIN
    cabin_temps_iter = []
    hvac_ws = []

    for i in range(n):
        hr = (hours_float[i] % 24)
        Gsol = solar_irradiance(hr)
        Qload = cabin_heat_load(Gsol, ambient[i], T_cabin_prev, R_TH_CABIN, n_occ)
        Phvac = hvac_power_fn(np.array([T_cabin_prev]), 24.0, np.array([Qload]), COP_AC, COP_HEAT, K_HEAT)[0] if not is_bike else 0.0

        if is_bike:
            Phvac = 0.0
            T_cabin_next = np.nan
        else:
            if T_cabin_prev > 25:
                Q_cool = Phvac * COP_AC
                Q_heat = 0.0
            elif T_cabin_prev < 23:
                Q_cool = 0.0
                Q_heat = Phvac * COP_HEAT
            else:
                Q_cool = 0.0
                Q_heat = 0.0

            Q_net = Qload - Q_cool + Q_heat
            exp_c = np.exp(-dt_s / tau_cabin)
            T_cabin_next = ambient[i] + (T_cabin_prev - ambient[i]) * exp_c + Q_net * R_TH_CABIN * (1 - exp_c)
            T_cabin_next = float(np.clip(T_cabin_next, 15.0, 55.0))

        cabin_temps_iter.append(T_cabin_next if not is_bike else np.nan)
        hvac_ws.append(Phvac)
        T_cabin_prev = T_cabin_next if not is_bike else ambient[i]

    cabin_temps = np.array(cabin_temps_iter, dtype=float)
    hvac_ws = np.array(hvac_ws, dtype=float)
    hvac_kw_arr = hvac_ws / 1000.0
    P_aux_arr = 200.0 + hvac_ws

    F_aux = P_aux_arr / np.maximum(v_ms, 1.0)
    F_total = F_drag + F_roll + F_grade_arr + F_inertia + F_aux

    P_wheel = F_total * v_ms
    is_braking = (P_wheel < 0) | (a < -0.5)
    P_motor, P_inv_in, P_batt = powertrain_power(P_wheel, is_braking)

    # Tính toán diễn biến dung lượng pin (SoC)
    E_cap_wh = vehicle["battery_kwh"] * 1000.0 * (soh / 100.0)
    soc_arr = soc + np.cumsum(-P_batt * dt_s / E_cap_wh * 100.0 / 3600.0)

    # Cắt ngắn chuyến đi nếu SoC xuống dưới 5%
    low_mask = soc_arr <= 5.0
    if low_mask.any():
        cut = max(int(np.argmax(low_mask)) + 1, 2)
        def trunc(arr):
            return arr[:cut]

        speeds = trunc(speeds); v_ms = trunc(v_ms); a = trunc(a)
        motor_rpm_arr = trunc(motor_rpm_arr); P_motor = trunc(P_motor)
        P_inv_in = trunc(P_inv_in); P_batt = trunc(P_batt)
        soc_arr = trunc(soc_arr); ambient = trunc(ambient)
        off_seconds = trunc(off_seconds); off_min = trunc(off_min)
        cabin_temps = trunc(cabin_temps); hvac_kw_arr = trunc(hvac_kw_arr)
        hours_float = trunc(hours_float); minutes_float = trunc(minutes_float)
        n = cut

    # Tính toán diễn biến nhiệt độ động cơ, Inverter và bộ pin
    Q_motor_arr = np.abs(P_motor) * (1.0 - 0.93)
    Q_inv_arr = np.abs(P_inv_in) * (1.0 - 0.96)

    battery_temps = np.empty(n)
    motor_temps = np.empty(n)
    inverter_temps = np.empty(n)

    T_motor_prev = ambient[0] + 8.0
    T_inv_prev = ambient[0] + 5.0
    T_batt_prev = ambient[0] + 5.0

    for i in range(n):
        V_oc = pack_ocv(vehicle["V_pack_nom_v"], soc_arr[i])
        I = pack_current(P_batt[i], V_oc)
        R_int = internal_resistance(vehicle["R_int_base_ohm"], T_batt_prev, soc_arr[i], soh)
        Q_batt = joule_heating(I, R_int)

        T_motor_prev = thermal_step(T_motor_prev, ambient[i], Q_motor_arr[i], tau_motor, R_th_motor, dt_s)
        T_inv_prev = thermal_step(T_inv_prev, ambient[i], Q_inv_arr[i], tau_inv, R_TH_INV, dt_s)
        T_batt_prev = thermal_step(T_batt_prev, ambient[i], Q_batt, tau_pack, R_th_pack, dt_s)

        motor_temps[i] = T_motor_prev + float(rng.normal(0, 0.4))
        inverter_temps[i] = T_inv_prev + float(rng.normal(0, 0.3))
        battery_temps[i] = T_batt_prev + float(rng.normal(0, 0.2))

    batt_avg = pd.Series(battery_temps).rolling(5, min_periods=1).mean().to_numpy()
    batt_max = pd.Series(battery_temps).rolling(5, min_periods=1).max().to_numpy()

    # Tính các thành phần gia tốc IMU
    curv = rng.normal(0, 0.003, n)
    curv[np.abs(v_ms) < 3.0] = 0.0
    a_x = a
    a_y = v_ms * v_ms * curv

    bump = rng.normal(0, 0.25, n)
    bump[np.abs(v_ms) < 0.5] = rng.normal(0, 0.05, size=int((np.abs(v_ms) < 0.5).sum()))
    a_z = 9.81 + bump

    # Kiểm tra kích hoạt túi khí khi va chạm mạnh (|a_x| > 35 m/s2 kéo dài 2 mẫu)
    airbag_arr = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if abs(a_x[i]) > 35.0 and abs(a_x[i - 1]) > 35.0:
            airbag_arr[i:] = True
            break

    if airbag_arr.any():
        trig = int(np.argmax(airbag_arr))
        keep = trig + 1
        speeds = speeds[:keep]; soc_arr = soc_arr[:keep]; off_seconds = off_seconds[:keep]
        off_min = off_min[:keep]; ambient = ambient[:keep]; motor_rpm_arr = motor_rpm_arr[:keep]
        motor_temps = motor_temps[:keep]; inverter_temps = inverter_temps[:keep]
        battery_temps = battery_temps[:keep]; batt_avg = batt_avg[:keep]; batt_max = batt_max[:keep]
        a_x = a_x[:keep]; a_y = a_y[:keep]; a_z = a_z[:keep]
        cabin_temps = cabin_temps[:keep]; hvac_kw_arr = hvac_kw_arr[:keep]
        airbag_arr = airbag_arr[:keep]
        P_batt = P_batt[:keep]
        n = keep

    # Cập nhật số ODO
    step_km = speeds * dt_s / 3600.0
    odometer_arr = odometer + np.concatenate([[0.0], np.cumsum(step_km[:-1])]) if n > 1 else np.array([odometer])

    # Nội suy tọa độ GPS theo quãng đường di chuyển
    cum_km = np.concatenate([[0.0], np.cumsum(step_km[:-1])])
    total_km = step_km.sum()
    frac = cum_km / total_km if total_km > 0.01 else (np.linspace(0.0, 1.0, n) if n > 1 else np.array([0.0]))

    lat = origin["lat"] + (dest["lat"] - origin["lat"]) * frac + rng.normal(0, 0.00030, n)
    lon = origin["lon"] + (dest["lon"] - origin["lon"]) * frac + rng.normal(0, 0.00030, n)

    # Chế độ số, trạng thái khóa cửa và trạng thái sạc
    gear_state = np.where(speeds > 0.5, "D", "P").astype(object)
    regen_mask = is_braking[:n] & (speeds > 5)
    gear_state[regen_mask] = "B"

    lock_status = np.full(n, "unlocked", dtype=object)
    charging_status = np.full(n, "disconnected", dtype=object)

    # Áp suất lốp
    T_cold_K = 298.15
    tires: dict[str, np.ndarray] = {}
    T_tire = tire_temp_from_ambient(ambient, speeds)
    T_tire_K = T_tire + 273.15

    for pos in TIRE_POSITIONS:
        pres = tire_p_fn(tire_base, T_tire_K, T_cold_K, 0, 0.0) + rng.normal(0.0, 0.015, n)
        tires[pos] = pres

    if puncture_tire is not None and puncture_tire in tires:
        leak = np.linspace(0.05, 0.55, n)
        tires[puncture_tire] = tires[puncture_tire] - leak

    charge_kw = np.zeros(n)

    # Tính mức suy hao sức khỏe pin (SoH) cho chuyến đi
    throughput = float(np.sum(np.abs(P_batt) * dt_s / 3600.0 / 1000.0))
    avg_T = float(np.mean(battery_temps)) if n else float(ambient_mean)
    DoD = float((np.max(soc_arr) - np.min(soc_arr)) / 100.0) if n else 0.0
    I_avg = float(np.mean(np.abs(P_batt) / max(vehicle["V_pack_nom_v"], 1))) if n else 0.0
    I_1C = vehicle["battery_kwh"] * 1000.0 / vehicle["V_pack_nom_v"]
    C_rate = float(I_avg / max(I_1C, 1.0))

    d_soh = soh_decrement(throughput, vehicle["battery_kwh"], avg_T, n * dt_s / 86400.0, DoD, C_rate)
    soh_end = float(max(75.0, soh - d_soh))
    soh_arr = np.linspace(soh, soh_end, n) if n > 1 else np.array([soh])

    frame = build_frame(
        vehicle, day_start_iso, off_min, off_seconds, speeds, soc_arr, soh_arr,
        battery_temps, batt_avg, batt_max, charging_status, motor_rpm_arr,
        motor_temps, inverter_temps, gear_state, lat, lon, a_x, a_y, a_z,
        lock_status, cabin_temps, hvac_kw_arr, airbag_arr, odometer_arr,
        is_charging=False, charging_power_kw=charge_kw, ignition_on=True,
        ambient=ambient, tire_pressures=tires,
    )
    return {
        "frame": frame,
        "soc_end": float(soc_arr[-1]) if n else soc,
        "soh_end": float(soh_end),
        "odometer_end": odometer + float(step_km.sum()),
        "end_off_min": int(off_min[-1]) if n else start_off_min,
        "end_off_seconds": int(off_seconds[-1]) if n else start_off_min * 60,
        "throughput_kwh": throughput,
    }


def simulate_charge(
    rng: np.random.Generator,
    vehicle: dict,
    day_start_iso: str,
    *,
    start_off_min: int,
    soc_start: float,
    soh: float,
    target_soc: float,
    power_kw: float,
    charger_type: str,
    odometer: float,
    tire_base: float,
    lat: float,
    lon: float,
    ambient_mean: float,
    ambient_amp: float,
) -> dict | None:
    """Mô phỏng quá trình sạc pin của xe tại trạm sạc (AC hoặc DC)."""
    dt_s = SAMPLE_SECONDS_CHARGING
    is_bike = vehicle.get("type", "car") == "motorbike"

    if is_bike and charger_type == "CCS2_DC":
        charger_type = "AC_TYPE2"
        power_kw = min(power_kw, 3.0)

    soc = soc_start
    T_batt = ambient_mean + 5.0
    T_motor = ambient_mean + 5.0
    T_inv = ambient_mean + 5.0
    T_cabin = ambient_mean

    if is_bike:
        R_th_motor = R_TH_MOTOR_BIKE
        R_th_pack = R_TH_PACK_BIKE
        tau_motor = M_MOTOR_BIKE * CP_MOTOR * R_th_motor
        m_pack = vehicle["battery_kwh"] * CELL_MASS_PER_KWH
        tau_pack = m_pack * CP_CELL * R_th_pack
        tau_inv = M_INV * CP_INV * R_TH_INV
        tau_cabin = M_CABIN * CP_CABIN * R_TH_CABIN
    else:
        R_th_motor = R_TH_MOTOR_CAR
        R_th_pack = R_TH_PACK_CAR
        tau_motor = M_MOTOR_CAR * CP_MOTOR * R_th_motor
        m_pack = vehicle["battery_kwh"] * CELL_MASS_PER_KWH
        tau_pack = m_pack * CP_CELL * R_th_pack
        tau_inv = M_INV * CP_INV * R_TH_INV
        tau_cabin = (M_CABIN + 3.0) * CP_CABIN * R_TH_CABIN

    E_cap_wh = vehicle["battery_kwh"] * 1000.0 * (soh / 100.0)

    max_samples = int(8 * 3600 / dt_s)
    remaining_day_s = (MINUTES_PER_DAY - start_off_min) * 60 - 120
    max_samples = min(max_samples, int(remaining_day_s / dt_s))

    if max_samples < 3:
        return None

    speeds = []
    socs = []
    ambients = []
    off_seconds_list = []
    motor_temps = []
    inverter_temps = []
    battery_temps = []
    charge_powers = []
    cabin_temps_list = []
    hvac_kws = []

    off_s = start_off_min * 60
    t_idx = 0
    throughput = 0.0

    # Vòng lặp sạc từng bước thời gian
    while soc < target_soc - 0.05 and t_idx < max_samples:
        minute = off_s / 60.0
        amb = float(ambient_curve(np.array([minute]), ambient_mean, ambient_amp)[0])

        P_derated = float(charge_curve_power(soc, power_kw, charger_type))
        P_batt_w = -P_derated * 1000.0 * 0.92
        d_soc = -P_batt_w * dt_s / E_cap_wh * 100.0 / 3600.0
        soc = float(np.clip(soc + d_soc, soc_start, 100.0))

        V_oc = pack_ocv(vehicle["V_pack_nom_v"], soc)
        I = pack_current(P_batt_w, V_oc)
        R_int = internal_resistance(vehicle["R_int_base_ohm"], T_batt, soc, soh)
        Q_batt = joule_heating(I, R_int)

        T_batt = float(thermal_step(T_batt, amb, Q_batt, tau_pack, R_th_pack, dt_s) + rng.normal(0, 0.15))
        T_motor = float(thermal_step(T_motor, amb, 0.0, tau_motor, R_th_motor, dt_s))
        T_inv = float(thermal_step(T_inv, amb, abs(P_derated * 1000 * (1 - 0.96)) * 0.3, tau_inv, R_TH_INV, dt_s))

        if is_bike:
            T_cabin_next = np.nan
            Phvac = 0.0
        else:
            hr = (minute / 60.0) % 24
            Gsol = solar_irradiance(hr)
            Qload = cabin_heat_load(Gsol, amb, T_cabin, R_TH_CABIN, 1)
            Phvac = float(hvac_power_fn(np.array([T_cabin]), 24.0, np.array([Qload]), COP_AC, COP_HEAT, K_HEAT)[0])

            if T_cabin > 25:
                Q_cool = Phvac * COP_AC
                Q_heat = 0.0
            elif T_cabin < 23:
                Q_cool = 0.0
                Q_heat = Phvac * COP_HEAT
            else:
                Q_cool = 0.0
                Q_heat = 0.0

            Qnet = Qload - Q_cool + Q_heat
            exp_c = np.exp(-dt_s / tau_cabin)
            T_cabin_next = amb + (T_cabin - amb) * exp_c + Qnet * R_TH_CABIN * (1 - exp_c)
            T_cabin_next = float(np.clip(T_cabin_next, 15.0, 55.0))
            T_cabin = T_cabin_next

        speeds.append(0.0)
        socs.append(soc)
        ambients.append(amb)
        off_seconds_list.append(off_s)
        motor_temps.append(T_motor)
        inverter_temps.append(T_inv)
        battery_temps.append(T_batt)
        charge_powers.append(P_derated)
        cabin_temps_list.append(T_cabin_next if not is_bike else np.nan)
        hvac_kws.append(Phvac / 1000.0 if not is_bike else 0.0)

        throughput += abs(P_derated * dt_s / 3600.0)
        off_s += dt_s
        t_idx += 1

        if P_derated < 0.5:
            break

    n = len(socs)
    if n < 3:
        return None

    off_seconds = np.array(off_seconds_list, dtype=int)
    off_min = (off_seconds // 60).astype(int)
    soc_arr = np.array(socs)
    battery_temps = np.array(battery_temps)
    motor_temps = np.array(motor_temps)
    inverter_temps = np.array(inverter_temps)
    ambients = np.array(ambients)
    speeds_arr = np.array(speeds)
    motor_rpm_arr = np.zeros(n)
    cabin_temps_arr = np.array(cabin_temps_list, dtype=float)
    hvac_kw_arr = np.array(hvac_kws)
    charge_kw_arr = np.array(charge_powers)

    batt_avg = pd.Series(battery_temps).rolling(5, min_periods=1).mean().to_numpy()
    batt_max = pd.Series(battery_temps).rolling(5, min_periods=1).max().to_numpy()

    a_x = np.full(n, 0.0)
    a_y = np.full(n, 0.0)
    a_z = np.full(n, 9.81) + rng.normal(0, 0.05, n)

    gear_state = np.full(n, "P", dtype=object)
    lock_status = np.full(n, "locked", dtype=object)

    if charger_type == "CCS2_DC":
        cstat = "charging_dc_fast"
    elif soc_arr[-1] >= 99.5:
        cstat = "fully_charged"
    else:
        cstat = "charging_ac"

    charging_status = np.full(n, cstat, dtype=object)
    if charger_type != "CCS2_DC":
        fully_mask = soc_arr >= 99.5
        charging_status[fully_mask] = "fully_charged"

    airbag_arr = np.zeros(n, dtype=bool)
    lat_arr = np.full(n, lat) + rng.normal(0, 0.00002, n)
    lon_arr = np.full(n, lon) + rng.normal(0, 0.00002, n)
    odometer_arr = np.full(n, odometer)
    tires = {pos: np.full(n, tire_base) + rng.normal(0.0, 0.01, n) for pos in TIRE_POSITIONS}

    if is_bike:
        tires["rl"] = np.full(n, np.nan)
        tires["rr"] = np.full(n, np.nan)

    soh_arr = np.full(n, soh)

    frame = build_frame(
        vehicle, day_start_iso, off_min, off_seconds, speeds_arr, soc_arr, soh_arr,
        battery_temps, batt_avg, batt_max, charging_status, motor_rpm_arr,
        motor_temps, inverter_temps, gear_state, lat_arr, lon_arr, a_x, a_y, a_z,
        lock_status, cabin_temps_arr, hvac_kw_arr, airbag_arr, odometer_arr,
        is_charging=True, charging_power_kw=charge_kw_arr, ignition_on=False,
        ambient=ambients, tire_pressures=tires,
    )

    avg_T = float(np.mean(battery_temps))
    d_soh = soh_decrement(throughput, vehicle["battery_kwh"], avg_T, n * dt_s / 86400.0, DoD=0.6, C_rate=power_kw / max(vehicle["battery_kwh"], 1))
    soh_end = float(max(75.0, soh - d_soh))

    return {
        "frame": frame,
        "soc_end": float(soc_arr[-1]),
        "soh_end": soh_end,
        "end_off_min": int(off_min[-1]),
        "end_off_seconds": int(off_seconds[-1]),
        "throughput_kwh": throughput,
    }
