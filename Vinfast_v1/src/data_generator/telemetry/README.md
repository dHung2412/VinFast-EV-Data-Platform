# Mô Phỏng Dữ Liệu Telemetry Xe Điện VinFast

Mô tả chi tiết tập dữ liệu mô phỏng thực thể (Entities) và các mô hình tính toán vật lý (Physics Dynamics) thuộc module `src/data_generator/telemetry`. Tài liệu tập trung làm rõ bản chất các đại lượng dữ liệu và cơ chế tác động qua lại giữa chúng trong quá trình mô phỏng.

---

## 1. Cấu Trúc Thực Thể Dữ Liệu (Entity Data Models)

Tệp `entities.py` định nghĩa các thực thể tĩnh và thông số khởi tạo ban đầu cho hệ thống mô phỏng:

### 1.1. Thực thể Người dùng (`users`)
| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `u_id` | `str` | Mã định danh người dùng (dạng `USR-XXXXX`). |
| `name` | `str` | Họ và tên người dùng. |
| `phone` | `str` | Số điện thoại liên hệ. |

* **Tác động:** Mỗi người dùng sở hữu ngẫu nhiên từ 1 đến 3 phương tiện (theo phân phối xác suất 80% có 1 xe, 15% có 2 xe, 5% có 3 xe).

### 1.2. Thực thể Phương tiện (`fleet`)
| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `vehicle_id` | `str` | Mã định danh phương tiện (dạng `VFS-XXXXX`). |
| `u_id` | `str` | Mã người dùng sở hữu phương tiện. |
| `model` | `str` | Tên mẫu xe (Ô tô: VF 3 - VF 9; Xe máy điện: VF Amio S, VF Evo Lite S, VF Flazz S). |
| `type` | `str` | Phân loại phương tiện (`car` hoặc `motorbike`). |
| `city_code` | `str` | Mã tỉnh/thành phố hoạt động chính (`HN`, `SG`, `DN`, `TH`, `TN`, `NA`, `HT`, `QN`). |
| `home_lat`, `home_lon` | `float` | Tọa độ địa lý vị trí nhà riêng của chủ xe. |
| `work_lat`, `work_lon` | `float` | Tọa độ địa lý vị trí nơi làm việc. |
| `battery_kwh` | `float` | Dung lượng thiết kế của bộ pin (kWh). |
| `wh_per_km` | `float` | Mức tiêu thụ điện năng tiêu chuẩn (Wh/km). |
| `mass_kg` | `float` | Tổng khối lượng bản thân của xe (kg). |
| `Cd` | `float` | Hệ số cản khí động học của xe. |
| `A_frontal_m2` | `float` | Diện tích cản gió mặt trước xe ($m^2$). |
| `r_wheel_m` | `float` | Bán kính bán nguyệt của bánh xe (m). |
| `gear_ratio` | `float` | Tỷ số truyền của hộp số giảm tốc. |
| `V_pack_nom_v` | `float` | Điện áp danh định của bộ pin (V). |
| `R_int_base_ohm` | `float` | Điện trở trong cơ sở của bộ pin ($\Omega$). |
| `odometer_start_km` | `float` | Quãng đường tích lũy ban đầu (km). |
| `tire_pressure_base_bar` | `float` | Áp suất lốp xe tiêu chuẩn ở trạng thái nguội (bar). |
| `battery_soh_pct` | `float` | Mức độ khỏe của pin khởi tạo (% SOH), suy giảm theo quãng đường ODO. |
| `years_old` | `float` | Tuổi đời sử dụng của xe (năm). |

### 1.3. Thực thể Môi trường Thành phố (`CITIES` & `AMBIENT_BY_CITY`)
| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `lat`, `lon` | `float` | Tọa độ tâm địa lý của tỉnh/thành phố. |
| `mean` | `float` | Nhiệt độ môi trường trung bình ngày ($^\circ C$). |
| `amp` | `float` | Biên độ dao động nhiệt độ giữa ngày và đêm ($^\circ C$). |

### 1.4. Thực thể Trạm sạc (`stations`)
| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `station_id` | `str` | Mã định danh trạm sạc (dạng `CS-{CITY}-{IDX}`). |
| `city_code` | `str` | Mã tỉnh/thành phố đặt trạm sạc. |
| `charger_type` | `str` | Chuẩn sạc (`AC_TYPE2` hoặc `CCS2_DC`). |
| `max_power_kw` | `float` | Công suất sạc tối đa của trạm (kW). |
| `num_chargers` | `int` | Số lượng cổng sạc tại trạm. |
| `lat`, `lon` | `float` | Tọa độ địa lý của trạm sạc. |

---

## 2. Mô Hình Tác Động Qua Lại Giữa Các Đại Lượng (Physics Inter-dependencies)

Tệp `physics.py` chứa các công thức toán học - vật lý mô tả mối quan hệ phụ thuộc lẫn nhau giữa các đại lượng trạng thái trong quá trình vận hành xe.

```
+-----------------------------------------------------------------------------------+
|                                 Môi Trường & Vận Hành                              |
|   Vận tốc (v), Gia tốc (a), Độ dốc (theta), Giờ trong ngày (h), Nhiệt độ môi trường  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               Hệ Thống Lực Kháng Cơ Học                           |
|   F_drag (Khí động học) + F_roll (Ma sát lăn) + F_grade (Độ dốc) + F_inertia (Quán tính)|
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               Công Suất Bánh Xe (P_wheel)                          |
|                          P_wheel = F_total * v  (Phanh / Phát động)               |
+-----------------------------------------------------------------------------------+
                                          |
                       +------------------+------------------+
                       |                                     |
                       v (Chạy phát động)                    v (Phanh tái sinh)
+---------------------------------------------+   +---------------------------------+
|   P_motor = P_wheel / (eta_trans * eta_fd)  |   | P_motor = P_wheel * eta_regen.. |
|   P_inv   = P_motor / eta_motor             |   | P_inv   = P_motor * eta_motor   |
|   P_batt  = P_inv / eta_inv (P_batt > 0)    |   | P_batt  = P_inv * eta_inv (< 0) |
+---------------------------------------------+   +---------------------------------+
                       |                                     |
                       +------------------+------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                Quản Lý Năng Lượng & Trạng Thái                     |
|  1. Mức pin SoC(t+dt) = SoC(t) - (P_batt * dt / E_cap)                            |
|  2. Dòng điện I = P_batt / V_ocv                                                  |
|  3. Nhiệt Joule Q_joule = I^2 * R_int                                             |
|  4. Tải nhiệt HVAC P_hvac -> Tiêu thụ thêm P_batt                                 |
|  5. Lão hóa pin Delta_SoH = f(Nhiệt độ, Dòng sạc, Số chu kỳ sạc-xả)                |
|  6. Áp suất lốp P_tire = f(Nhiệt độ lốp, Vận tốc xe, Tuổi lốp)                    |
+-----------------------------------------------------------------------------------+
```

---

### 2.1. Từ Vận tốc & Môi trường đến Tổng lực kéo ($F_{\text{total}}$)

1. **Lực cản khí động học ($F_{\text{drag}}$):**
   $$F_{\text{drag}} = \frac{1}{2} \cdot \rho_{\text{air}} \cdot C_d \cdot A \cdot v^2$$
   * **Tác động:** Vận tốc $v$ tăng làm lực cản không khí tăng theo bình phương vận tốc. Xe có diện tích cản $A$ và hệ số cản $C_d$ lớn (như ô tô so với xe máy điện) chịu lực cản cao hơn.

2. **Lực cản lăn ($F_{\text{roll}}$):**
   $$F_{\text{roll}} = C_{rr} \cdot m \cdot g \cdot \left(1 + 0.04 \cdot \left(\frac{v_{\text{kmh}}}{100}\right)^2\right)$$
   * **Tác động:** Phụ thuộc vào khối lượng bản thân của xe $m$ và vận tốc di chuyển. Xe có khối lượng lớn làm tăng lực ma sát lăn của lốp xe trên mặt đường.

3. **Lực cản độ dốc ($F_{\text{grade}}$) & Lực quán tính ($F_{\text{inertia}}$):**
   $$F_{\text{grade}} = m \cdot g \cdot \sin(\theta)$$
   $$F_{\text{inertia}} = m \cdot k_{\text{rot}} \cdot a$$
   * **Tác động:** Khối lượng xe $m$, độ dốc mặt đường $\theta$ và gia tốc $a$ quyết định lực cản bổ sung khi leo dốc hoặc tăng tốc.

4. **Tổng lực kéo tại bánh xe ($F_{\text{total}}$):**
   $$F_{\text{total}} = F_{\text{drag}} + F_{\text{roll}} + F_{\text{grade}} + F_{\text{inertia}}$$

---

### 2.2. Từ Công suất bánh xe ($P_{\text{wheel}}$) đến Công suất Pin ($P_{\text{batt}}$)

Công suất tại bánh xe được tính bằng $P_{\text{wheel}} = F_{\text{total}} \cdot v$. Luồng truyền công suất phân làm 2 chế độ:

* **Chế độ phát động xả pin (khi $P_{\text{wheel}} > 0$ và không phanh):**
  Năng lượng truyền từ Pin $\rightarrow$ Inverter $\rightarrow$ Động cơ $\rightarrow$ Bánh xe. Hiệu suất ở mỗi tầng khiến công suất xả ở tầng trước cao hơn tầng sau:
  $$P_{\text{motor}} = \frac{P_{\text{wheel}}}{\eta_{\text{trans}} \cdot \eta_{\text{fd}}}$$
  $$P_{\text{inv\_in}} = \frac{P_{\text{motor}}}{\eta_{\text{motor}}}$$
  $$P_{\text{batt}} = \frac{P_{\text{inv\_in}}}{\eta_{\text{inv}}} \quad (P_{\text{batt}} > 0)$$

* **Chế độ phanh tái sinh nạp pin (khi phanh $is\_braking = True$):**
  Động cơ chuyển thành máy phát, chuyển cơ năng từ Bánh xe $\rightarrow$ Động cơ $\rightarrow$ Inverter $\rightarrow$ Pin. Tổn hao hiệu suất làm giảm công suất điện nạp thực tế vào pin:
  $$P_{\text{motor}} = P_{\text{wheel}} \cdot \eta_{\text{trans}} \cdot \eta_{\text{fd}} \cdot \eta_{\text{regen}}$$
  $$P_{\text{inv\_in}} = P_{\text{motor}} \cdot \eta_{\text{motor}}$$
  $$P_{\text{batt}} = P_{\text{inv\_in}} \cdot \eta_{\text{inv}} \quad (P_{\text{batt}} < 0)$$

---

### 2.3. Tác động đến Dung lượng Pin ($\text{SoC}$) và Dòng điện ($I$)

1. **Phần trăm dung lượng pin ($\text{SoC}$):**
   $$\text{SoC}(t+dt) = \text{SoC}(t) - \frac{P_{\text{batt}} \cdot dt}{E_{\text{cap}}} \cdot \frac{100\%}{3600}$$
   * **Tác động:** Công suất xả $P_{\text{batt}} > 0$ làm giảm $\text{SoC}$. Công suất nạp $P_{\text{batt}} < 0$ (phanh tái sinh hoặc sạc tại trạm) làm tăng $\text{SoC}$.

2. **Điện áp hở mạch ($V_{\text{ocv}}$) & Dòng điện pin ($I$):**
   $$V_{\text{ocv}} = V_{\text{nom}} \cdot \left(0.9 + 0.1 \cdot \frac{\text{SoC}}{100}\right)$$
   $$I = \frac{P_{\text{batt}}}{V_{\text{ocv}}}$$
   * **Tác động:** Mức $\text{SoC}$ giảm làm giảm điện áp $V_{\text{ocv}}$. Để duy trì cùng công suất $P_{\text{batt}}$, dòng điện $I$ phải tăng lên.

---

### 2.4. Nhiệt độ, Điện trở trong ($R_{\text{int}}$) & Tổn hao Nhiệt Joule

1. **Điện trở trong của bộ pin ($R_{\text{int}}$):**
   $$R_{\text{int}} = R_{\text{base}} \cdot f(T_{\text{batt}}) \cdot f(\text{SoC}) \cdot f(\text{SoH})$$
   * **Tác động:** Điện trở trong $R_{\text{int}}$ tăng lên khi:
     * Nhiệt độ pin lạnh ($T_{\text{batt}} < 15^\circ C$).
     * Mức pin thấp ($\text{SoC} < 20\%$).
     * Pin bị chai lão hóa ($\text{SoH}$ giảm).

2. **Nhiệt Joule tổn hao ($Q_{\text{joule}}$):**
   $$Q_{\text{joule}} = I^2 \cdot R_{\text{int}}$$
   * **Tác động:** Dòng điện $I$ cao hoặc điện trở trong $R_{\text{int}}$ lớn sẽ tăng nhiệt lượng tỏa ra trong bộ pin, gây tăng nhiệt độ pin $T_{\text{batt}}$ ở các bước thời gian tiếp theo.

---

### 2.5. Bức xạ Mặt trời, Cabin & Phụ tải Điều hòa (HVAC)

1. **Bức xạ mặt trời ($G_{\text{solar}}$):** Biến đổi theo thời gian trong ngày $h \in [0, 24)$:
   $$G_{\text{solar}} = G_{\text{max}} \cdot \max\left(0, \sin\left(\frac{\pi \cdot (h - 6)}{12}\right)\right)$$
2. **Tải nhiệt cabin ($Q_{\text{load}}$):**
   $$Q_{\text{load}} = Q_{\text{solar}} + \frac{T_{\text{amb}} - T_{\text{cabin}}}{R_{\text{th\_cabin}}} + Q_{\text{hành\_khách}}$$
3. **Công suất điều hòa ($P_{\text{hvac}}$):**
   $$P_{\text{hvac}} = \frac{Q_{\text{load}}}{\text{COP}_{\text{ac}}}$$
   * **Tác động:** Nhiệt độ môi trường $T_{\text{amb}}$ cao hoặc nắng gắt giữa trưa làm tăng công suất điều hòa $P_{\text{hvac}}$. Công suất này cộng trực tiếp vào phụ tải nền $P_{\text{aux}}$, làm tăng lượng công suất xả $P_{\text{batt}}$ từ pin.

---

### 2.6. Lão hóa Pin ($\text{SoH}$)

Mức giảm độ khỏe của pin ($\Delta\text{SoH}$) gồm 2 thành phần chính:
$$\Delta\text{SoH} = d_{\text{cyc}} + d_{\text{cal}}$$

* **Suy hao chu kỳ sạc-xả ($d_{\text{cyc}}$):** Tỉ lệ thuận với dung lượng điện năng luân chuyển qua pin (Throughput kWh), nhiệt độ vận hành $T_{\text{avg}}$, độ sâu xả (DoD) và dòng sạc (C-rate).
* **Suy hao tự nhiên ($d_{\text{cal}}$):** Suy hao theo thời gian $dt$, tuân theo phương trình động hóa học Arrhenius dựa trên nhiệt độ lưu trữ trung bình.
* **Tác động ngược:** $\Delta\text{SoH}$ làm giảm dung lượng thực tế $E_{\text{cap}}$ và tăng điện trở trong $R_{\text{int}}$ của pin trong các chu kỳ vận hành sau.

---

### 2.7. Nhiệt độ & Áp suất Lốp xe

1. **Nhiệt độ lốp xe ($T_{\text{tire}}$):**
   $$T_{\text{tire}} = T_{\text{amb}} + 5 + \frac{v_{\text{kmh}}}{100} \cdot 8$$
2. **Áp suất lốp xe ($P_{\text{tire}}$):**
   $$P_{\text{tire}} = P_{\text{cold}} \cdot \frac{T_{\text{tire}}}{T_{\text{cold}}} + k_{\text{wear}} \cdot t_{\text{age}}$$
   * **Tác động:** Xe chạy vận tốc cao $v_{\text{kmh}}$ hoặc nhiệt độ môi trường $T_{\text{amb}}$ cao làm tăng nhiệt độ lốp $T_{\text{tire}}$, dẫn đến làm tăng áp suất lốp xe thực tế $P_{\text{tire}}$.
