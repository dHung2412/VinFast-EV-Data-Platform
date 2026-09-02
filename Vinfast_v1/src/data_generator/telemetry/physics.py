from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Hằng số môi trường (Environment constants)
# ---------------------------------------------------------------------------
RHO_AIR = 1.184         # Mật độ không khí (kg/m3) ở 25C
G = 9.81                # Gia tốc trọng trường Trái Đất (m/s2)
CP_AIR = 1005           # Nhiệt dung riêng của không khí (J/kg/K)

# Hiệu suất hệ thống truyền động (Efficiencies)
ETA_MOTOR = 0.93        # Hiệu suất biến đổi điện năng thành cơ năng của động cơ điện
ETA_INVERTER = 0.96     # Hiệu suất bộ biến tần Inverter (DC -> AC)
ETA_TRANS = 0.95        # Hiệu suất truyền động của hộp số giảm tốc
ETA_FD = 0.98           # Hiệu suất bộ vi sai / truyền động cuối (Final Drive)
ETA_REGEN = 0.65        # Hiệu suất thu hồi điện năng khi phanh tái sinh
ETA_CHARGE = 0.92       # Hiệu suất sạc pin (lượng điện nạp thực tế vào pin)

# Hệ số ma sát & Hiệu suất nhiệt (Coefficients)
C_RR = 0.010            # Hệ số cản lăn của lốp xe trên mặt đường tiêu chuẩn
COP_AC = 3.0            # Hệ số hiệu quả năng lượng (COP) của điều hòa làm mát
COP_HEAT = 1.0          # Hệ số hiệu quả năng lượng của hệ thống sưởi ấm

# Thông số nhiệt & Khối lượng ô tô (Thermal masses - Car)
M_MOTOR_CAR = 65.0      # Khối lượng động cơ ô tô (kg)
CP_MOTOR = 460.0        # Nhiệt dung riêng của động cơ (J/kg/K)
R_TH_MOTOR_CAR = 0.045  # Nhiệt trở tản nhiệt động cơ ô tô ra môi trường (K/W)

M_INV = 12.0            # Khối lượng bộ Inverter (kg)
CP_INV = 900.0          # Nhiệt dung riêng bộ Inverter (J/kg/K)
R_TH_INV = 0.10         # Nhiệt trở tản nhiệt bộ Inverter (K/W)

CP_CELL = 1040.0        # Nhiệt dung riêng cell pin Lithium-ion (J/kg/K)
CELL_MASS_PER_KWH = 6.0 # Khối lượng cell pin trên mỗi kWh dung lượng (kg/kWh)
R_TH_PACK_CAR = 0.025   # Nhiệt trở tản nhiệt bộ pin ô tô (K/W)

M_CABIN = 40.0          # Khối lượng quy đổi không khí và nội thất cabin (kg)
R_TH_CABIN = 0.020      # Nhiệt trở truyền nhiệt qua vỏ cabin (K/W)
CP_CABIN = 1000.0       # Nhiệt dung riêng không gian cabin (J/kg/K)

# Thông số nhiệt xe máy điện (Thermal masses - Motorbike, Air Cooled)
M_MOTOR_BIKE = 8.0      # Khối lượng động cơ xe máy điện (kg)
R_TH_MOTOR_BIKE = 0.20  # Nhiệt trở tản nhiệt bằng không khí của động cơ xe máy (K/W)
R_TH_PACK_BIKE = 0.15   # Nhiệt trở tản nhiệt bộ pin xe máy điện (K/W)

# Phụ tải & Nhiệt bức xạ mặt trời (Auxiliary & Solar Heat)
P_AUX_BASE_W = 200.0    # Công suất tiêu thụ điện nền của hệ thống phụ trợ (W)
ALPHA_SOLAR = 0.85      # Hệ số hấp thụ bức xạ mặt trời của nóc xe
A_ROOF = 2.5            # Diện tích bề mặt nóc xe (m2)
K_HEAT = 80.0           # Hệ số truyền nhiệt tổng hợp vào cabin (W/K)

# Thông số lão hóa pin (State of Health - SoH Aging)
EA = 24500.0            # Năng lượng kích hoạt phương trình Arrhenius (J/mol)
R_GAS = 8.314           # Hằng số khí lý tưởng (J/mol/K)
K_CAL_REF = 0.0033      # Tốc độ suy giảm dung lượng pin tự nhiên ở 25C (%/ngày)
K_CYC = 0.012           # Tốc độ suy giảm dung lượng pin trên mỗi chu kỳ sạc-xả (%/chu kỳ)


# ---------------------------------------------------------------------------
# Lực và công suất (Forces & Power)
# ---------------------------------------------------------------------------
def drag_force(v_ms: np.ndarray | float, rho: float = RHO_AIR, Cd: float = 0.30, A: float = 2.6) -> np.ndarray | float:
    """Tính lực cản khí động học: F_drag = 0.5 * rho * Cd * A * v^2 [N]."""
    v = np.asarray(v_ms)
    return 0.5 * rho * Cd * A * v * v


def rolling_resistance(v_kmh: np.ndarray | float, m: float, Crr: float = C_RR, g: float = G) -> np.ndarray | float:
    """Tính lực cản lăn của lốp xe: F_roll = Crr * m * g * (1 + 0.04*(v_kmh/100)^2) [N] (theo SAE J2452)."""
    v = np.asarray(v_kmh)
    return Crr * m * g * (1.0 + 0.04 * (v / 100.0) ** 2)


def grade_force(m: float, g: float = G, theta_rad: float | np.ndarray = 0.0) -> float | np.ndarray:
    """Tính lực cản độ dốc mặt đường: F_grade = m * g * sin(theta) [N]."""
    return m * g * np.sin(np.asarray(theta_rad))


def inertia_force(a_ms2: np.ndarray | float, m: float, rot_factor: float = 1.03) -> np.ndarray | float:
    """Tính lực quán tính khi xe gia tốc: F_inertia = m * rot_factor * a [N]."""
    return m * rot_factor * np.asarray(a_ms2)


def total_tractive_power(F_total: np.ndarray | float, v_ms: np.ndarray | float) -> np.ndarray | float:
    """Tính tổng công suất kéo tại bánh xe: P_wheel = F_total * v [W]."""
    return np.asarray(F_total) * np.asarray(v_ms)


# ---------------------------------------------------------------------------
# Hệ thống truyền động (Powertrain)
# ---------------------------------------------------------------------------
def compute_motor_rpm(v_ms: np.ndarray | float, r_wheel: float, gear_ratio: float) -> np.ndarray | float:
    """Tính tốc độ quay của động cơ điện (RPM): motor_rpm = v / r_wheel * gear_ratio * 60 / (2*pi)."""
    omega_wheel = np.asarray(v_ms) / r_wheel
    omega_motor = omega_wheel * gear_ratio
    return omega_motor * 60.0 / (2.0 * np.pi)


def motor_torque(P_motor_w: np.ndarray | float, omega_motor: np.ndarray | float, omega_idle: float = 10.0) -> np.ndarray | float:
    """Tính mô-men xoắn động cơ điện (Nm): T = P / max(omega, omega_idle)."""
    om = np.maximum(np.asarray(omega_motor), omega_idle)
    return np.asarray(P_motor_w) / om


def powertrain_power(
    P_wheel: np.ndarray | float,
    is_braking: np.ndarray | bool,
    eta_trans: float = ETA_TRANS,
    eta_fd: float = ETA_FD,
    eta_motor: float = ETA_MOTOR,
    eta_inv: float = ETA_INVERTER,
    eta_regen: float = ETA_REGEN,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Tính toán luồng công suất qua từng tầng của hệ thống truyền động (P_motor, P_inv_in, P_batt) tính theo Watt.
    
    Quy ước dấu công suất pin:
    - P_batt > 0: Xả pin (chế độ phát động/chạy bình thường)
    - P_batt < 0: Nạp pin (chế độ phanh tái sinh)
    """
    Pw = np.asarray(P_wheel, dtype=float)
    brk = np.asarray(is_braking, dtype=bool)

    # Mở rộng chiều của mảng trạng thái phanh nếu ở dạng vô hướng
    if brk.ndim == 0 and Pw.ndim > 0:
        brk = np.broadcast_to(brk, Pw.shape)

    P_motor = np.empty_like(Pw, dtype=float)
    P_inv_in = np.empty_like(Pw, dtype=float)
    P_batt = np.empty_like(Pw, dtype=float)

    # Chế độ chạy phát động xả pin (khi không phanh)
    drive = ~brk
    P_motor[drive] = Pw[drive] / (eta_trans * eta_fd)                    # Công suất đầu ra động cơ
    P_inv_in[drive] = P_motor[drive] / eta_motor                         # Công suất đầu vào Inverter
    P_batt[drive] = P_inv_in[drive] / eta_inv                            # Công suất xả từ bộ pin

    # Chế độ phanh tái sinh nạp pin (khi phanh)
    brk_idx = brk
    P_motor[brk_idx] = Pw[brk_idx] * eta_trans * eta_fd * eta_regen      # Công suất cơ thu hồi tại động cơ
    P_inv_in[brk_idx] = P_motor[brk_idx] * eta_motor                     # Công suất điện thu hồi tại Inverter
    P_batt[brk_idx] = P_inv_in[brk_idx] * eta_inv                        # Công suất nạp thực tế vào bộ pin

    return P_motor, P_inv_in, P_batt


# ---------------------------------------------------------------------------
# Bộ pin & Lão hóa (Battery & SoH Aging)
# ---------------------------------------------------------------------------
def pack_ocv(V_nom: float, soc_pct: np.ndarray | float) -> np.ndarray | float:
    """Tính điện áp hở mạch OCV (Open Circuit Voltage): V_ocv = V_nom * (0.9 + 0.1 * SoC/100)."""
    s = np.asarray(soc_pct)
    return V_nom * (0.9 + 0.1 * s / 100.0)


def pack_current(P_batt_w: np.ndarray | float, V_ocv: np.ndarray | float) -> np.ndarray | float:
    """Tính cường độ dòng điện pin I = P_batt / V_ocv (Ampe). Giới hạn V >= 1.0V để an toàn."""
    V = np.asarray(V_ocv)
    V_safe = np.where(V < 1.0, 1.0, V)
    return np.asarray(P_batt_w) / V_safe


def internal_resistance(R_base: float, T_batt: np.ndarray | float, soc_pct: np.ndarray | float, soh_pct: np.ndarray | float) -> np.ndarray | float:
    """Tính điện trở trong R_int (Ohm) phụ thuộc nhiệt độ T, dung lượng SoC và độ chai SoH."""
    T = np.asarray(T_batt, dtype=float)
    soc = np.asarray(soc_pct, dtype=float)
    soh = np.asarray(soh_pct, dtype=float)

    # Hệ số điều chỉnh theo nhiệt độ (tăng điện trở khi nhiệt độ lạnh < 15C)
    f_T = 1.0 + 0.4 * np.maximum(0.0, 15.0 - T) / 15.0
    # Hệ số điều chỉnh theo SoC (tăng điện trở khi pin yếu < 20%)
    f_SoC = 1.0 + 0.5 * np.maximum(0.0, 20.0 - soc) / 20.0
    # Hệ số điều chỉnh theo SoH (tăng điện trở khi pin bị lão hóa)
    f_SoH = 1.0 + 0.6 * (1.0 - soh / 100.0)

    return R_base * f_T * f_SoC * f_SoH


def joule_heating(I: np.ndarray | float, R_int: np.ndarray | float) -> np.ndarray | float:
    """Tính nhiệt lượng Joule tỏa ra trong khối pin: Q = I^2 * R_int [Watt]."""
    return np.asarray(I) ** 2 * np.asarray(R_int)


def motor_heat(P_motor: np.ndarray | float, eta_motor: float = ETA_MOTOR) -> np.ndarray | float:
    """Tính nhiệt lượng tỏa ra từ động cơ điện quy đổi truyền vào dung dịch làm mát [Watt]."""
    P = np.asarray(P_motor, dtype=float)
    return np.abs(P) * (1.0 - eta_motor) * 0.5


def _motor_heat_full(P_motor: np.ndarray | float, eta_motor: float = ETA_MOTOR) -> np.ndarray | float:
    """Tính tổn hao nhiệt toàn phần của động cơ điện (không giảm chấn) dùng tính nhiệt độ [Watt]."""
    return np.abs(np.asarray(P_motor, dtype=float)) * (1.0 - eta_motor)


def inverter_heat(P_inv_in: np.ndarray | float, eta_inv: float = ETA_INVERTER) -> np.ndarray | float:
    """Tính nhiệt lượng tổn hao tỏa ra từ bộ Inverter: Q_inv = |P_inv_in| * (1 - eta_inv) [Watt]."""
    return np.abs(np.asarray(P_inv_in, dtype=float)) * (1.0 - eta_inv)


def soc_step(soc_pct: np.ndarray | float, P_batt_w: np.ndarray | float, E_cap_wh: float, dt_s: float) -> np.ndarray | float:
    """Tính mức pin SoC (%) ở bước thời gian t + dt: SoC(t+dt) = SoC(t) - (P_batt * dt / E_cap) * 100 / 3600."""
    return np.asarray(soc_pct) - np.asarray(P_batt_w) * dt_s / E_cap_wh * 100.0 / 3600.0


def soc_cumsum(soc0: float, P_batt_arr: np.ndarray, E_cap_wh: float, dt_s: float) -> np.ndarray:
    """Tính mảng SoC (%) lũy thừa theo chuỗi thời gian từ mảng công suất pin P_batt."""
    d_soc = -P_batt_arr * dt_s / E_cap_wh * 100.0 / 3600.0
    return soc0 + np.cumsum(d_soc)


def soh_decrement(throughput_kwh: float, battery_kwh: float, T_avg: float, dt_days: float, DoD: float = 0.5, C_rate: float = 0.5) -> float:
    """
    Tính mức giảm độ khỏe pin (ΔSoH %) trong khoảng thời gian dt_days.
    
    Gồm 2 thành phần:
    - d_cyc: Suy hao chu kỳ sạc-xả (phụ thuộc nhiệt độ T_avg, độ sâu xả DoD, dòng sạc C_rate).
    - d_cal: Suy hao tự nhiên theo thời gian và nhiệt độ (phương trình Arrhenius).
    """
    n_eq = throughput_kwh / (2.0 * battery_kwh) if battery_kwh > 0 else 0.0
    alpha_T = 0.02
    alpha_DoD = 0.5
    alpha_I = 0.1

    # Suy hao chu kỳ sạc xả
    d_cyc = K_CYC * n_eq * (1.0 + alpha_T * (T_avg - 25.0) + alpha_DoD * DoD + alpha_I * C_rate)

    # Suy hao tự nhiên theo thời gian (Calendar degradation)
    T_k = T_avg + 273.15
    d_cal = K_CAL_REF * np.exp(EA / R_GAS * (1.0 / 298.15 - 1.0 / T_k)) * dt_days

    return float(d_cyc + d_cal)


# ---------------------------------------------------------------------------
# Nhiệt học (Thermal Dynamics)
# ---------------------------------------------------------------------------
def thermal_step(T_prev: np.ndarray | float, T_amb: np.ndarray | float, Q_gen: np.ndarray | float, tau_s: float | np.ndarray, R_th: float, dt_s: float) -> np.ndarray | float:
    """
    Tính bước cập nhật nhiệt độ tại thời điểm t + dt theo phương trình truyền nhiệt suy giảm mũ:
    T(t+dt) = T_amb + (T_prev - T_amb)*exp(-dt/tau) + Q_gen*R_th*(1 - exp(-dt/tau)).
    """
    exp_term = np.exp(-dt_s / np.asarray(tau_s))
    return np.asarray(T_amb) + (np.asarray(T_prev) - np.asarray(T_amb)) * exp_term + np.asarray(Q_gen) * R_th * (1.0 - exp_term)


def thermal_trace(T0: float, T_amb_arr: np.ndarray, Q_gen_arr: np.ndarray, tau_s: float, R_th: float, dt_s: float) -> np.ndarray:
    """Tính mảng diễn biến nhiệt độ theo thời gian bằng cách lặp hàm thermal_step qua các mảng dữ liệu."""
    n = len(Q_gen_arr)
    out = np.empty(n, dtype=float)
    T = T0
    exp_term = np.exp(-dt_s / tau_s)
    one_minus = 1.0 - exp_term

    for i in range(n):
        T = T_amb_arr[i] + (T - T_amb_arr[i]) * exp_term + Q_gen_arr[i] * R_th * one_minus
        out[i] = T

    return out


def tau_for(mass: float, cp: float, R_th: float) -> float:
    """Tính hằng số thời gian nhiệt tau (giây): tau = mass * cp * R_th."""
    return mass * cp * R_th


# ---------------------------------------------------------------------------
# Cabin & Điều hòa HVAC (Cabin & HVAC)
# ---------------------------------------------------------------------------
def solar_irradiance(hour: np.ndarray | float, G_max: float = 1000.0) -> np.ndarray | float:
    """Tính công suất bức xạ nhiệt mặt trời (W/m2) theo giờ trong ngày h: G_solar = G_max * max(0, sin(pi*(h-6)/12))."""
    h = np.asarray(hour, dtype=float)
    return G_max * np.maximum(0.0, np.sin(np.pi * (h - 6.0) / 12.0))


def cabin_heat_load(G_solar: np.ndarray | float, T_amb: np.ndarray | float, T_cabin: np.ndarray | float, R_th_cabin: float = R_TH_CABIN, n_occupants: int = 1) -> np.ndarray | float:
    """Tính tổng nhiệt lượng tải cần làm mát/sưởi của cabin: Q_load = Q_solar + Q_dẫn_nhiệt + Q_hành_khách."""
    Q_solar = ALPHA_SOLAR * A_ROOF * np.asarray(G_solar)
    Q_cond = (np.asarray(T_amb) - np.asarray(T_cabin)) / R_th_cabin
    Q_occ = 100.0 * n_occupants
    return Q_solar + Q_cond + Q_occ


def hvac_power(T_cabin: np.ndarray | float, T_setpoint: float = 24.0, Q_load: np.ndarray | float = 0.0, COP_ac: float = COP_AC, COP_heat: float = COP_HEAT, k_heat: float = K_HEAT) -> np.ndarray | float:
    """
    Tính công suất tiêu thụ của hệ thống điều hòa HVAC (Watt).
    - Chế độ làm mát (khi T_cabin > T_setpoint + 1): giới hạn tối đa 3500W.
    - Chế độ sưởi (khi T_cabin < T_setpoint - 1): giới hạn tối đa 5000W.
    """
    Tc = np.asarray(T_cabin, dtype=float)
    Ql = np.asarray(Q_load, dtype=float)
    P = np.zeros_like(Tc, dtype=float)

    cool_mask = Tc > (T_setpoint + 1.0)
    heat_mask = Tc < (T_setpoint - 1.0)

    # Làm mát
    P[cool_mask] = np.maximum(0.0, Ql[cool_mask]) / COP_ac
    P[cool_mask] = np.clip(P[cool_mask], 0, 3500)

    # Sưởi ấm
    P[heat_mask] = (T_setpoint - Tc[heat_mask]) * k_heat / COP_heat
    P[heat_mask] = np.clip(P[heat_mask], 0, 5000)

    return P


# ---------------------------------------------------------------------------
# Cảm biến đo lường quán tính (IMU Acceleration)
# ---------------------------------------------------------------------------
def acceleration_components(
    dv_dt: np.ndarray | float,
    v_ms: np.ndarray | float,
    curvature_inv_m: np.ndarray | float = 0.0,
    bump_std: float = 0.0,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray | float, np.ndarray | float, np.ndarray | float]:
    """
    Tính toán 3 thành phần gia tốc (a_x, a_y, a_z) theo m/s2:
    - a_x: Gia tốc dọc (tăng/giảm tốc dv/dt)
    - a_y: Gia tốc ngang hướng tâm (v^2 * curvature)
    - a_z: Gia tốc đứng (trọng lực 9.81 m/s2 + nhiễu xóc mặt đường bump_std)
    """
    a_x = np.asarray(dv_dt, dtype=float)
    v = np.asarray(v_ms, dtype=float)
    curv = np.asarray(curvature_inv_m, dtype=float)

    a_y = v * v * curv

    if bump_std > 0 and rng is not None:
        noise = rng.normal(0.0, bump_std, size=np.shape(a_x) if np.shape(a_x) else 1)
        if np.shape(a_x) == ():
            a_z = 9.81 + float(noise)
        else:
            a_z = 9.81 + noise
            moving = np.abs(v) > 0.5
            a_z = np.where(moving, a_z, 9.81 + rng.normal(0, 0.05, size=a_z.shape))
    else:
        if np.shape(a_x) == ():
            a_z = 9.81
        else:
            a_z = np.full_like(a_x, 9.81, dtype=float)

    return a_x, a_y, a_z


# ---------------------------------------------------------------------------
# Đường cong sạc pin (Charging Curve)
# ---------------------------------------------------------------------------
def charge_curve_power(soc_pct: np.ndarray | float, P_max_kw: float, charger_type: str) -> np.ndarray | float:
    """
    Tính công suất sạc thực tế (kW) suy giảm theo phần trăm dung lượng pin SoC:
    - Sạc nhanh DC (CCS2_DC): Công suất tối đa đến 80% SoC, sau đó giảm dần về 10%.
    - Sạc chậm AC (AC_TYPE2): Công suất giữ nguyên đến 95% SoC, sau đó giảm dần.
    """
    s = np.asarray(soc_pct, dtype=float)
    if charger_type == "CCS2_DC":
        taper = np.where(s <= 80.0, 1.0, np.maximum(0.1, 1.0 - (s - 80.0) / 20.0))
        return P_max_kw * taper
    else:
        taper = np.where(s <= 95.0, 1.0, np.maximum(0.15, 1.0 - (s - 95.0) / 5.0 * 0.7))
        return P_max_kw * taper


# ---------------------------------------------------------------------------
# Lốp xe (Tire Dynamics)
# ---------------------------------------------------------------------------
def tire_pressure(P_cold_bar: float, T_tire_K: np.ndarray | float, T_cold_K: float = 298.15, t_age_steps: np.ndarray | float = 0, k_wear: float = 0.0008) -> np.ndarray | float:
    """Tính áp suất lốp xe (bar) theo nhiệt độ lốp (Kelvin) và độ hao mòn theo thời gian."""
    Tt = np.asarray(T_tire_K, dtype=float)
    age = np.asarray(t_age_steps, dtype=float)
    return P_cold_bar * Tt / T_cold_K + k_wear * age


def tire_temp_from_ambient(T_amb: np.ndarray | float, v_kmh: np.ndarray | float) -> np.ndarray | float:
    """Tính nhiệt độ lốp xe (độ C) dựa trên nhiệt độ môi trường và vận tốc xe (km/h): T_tire = T_amb + 5 + v/100*8."""
    return np.asarray(T_amb) + 5.0 + np.asarray(v_kmh) / 100.0 * 8.0
