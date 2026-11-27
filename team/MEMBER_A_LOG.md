# NHẬT KÝ CÔNG VIỆC — THÀNH VIÊN A (ZONE & VAV)

---

## 📚 Cơ sở lý thuyết & Công thức nhiệt động lực học VAV

**Căn cứ mã nguồn:** Lấy từ mô phỏng vật lý của ban tổ chức tại `smart_buildings/smart_control/simulator/vav.py` 

### 1. Cấu tạo & Mô hình hoạt động ("Nguyên lý máy sấy tóc")
Mỗi phòng (Zone) được điều hòa bằng một hộp **VAV (Variable Air Volume)** gồm 2 thành phần nối tiếp:
1. **Van gió (`damper`):** Nhận luồng khí lạnh từ máy tổng ($T_{supply\_air} \approx 13^\circ\text{C} - 15^\circ\text{C}$). Độ mở van gió quyết định lưu lượng khí $\dot{m}_{air}$ thổi vào phòng (sàn tối thiểu 10% theo quy chuẩn thông gió).
2. **Cuộn sưởi nước nóng (`reheat coil`):** Nằm ngay phía sau van gió, dùng nước nóng từ lò sưởi để hơ nóng luồng khí trước khi xả vào phòng. Độ mở van sưởi (`reheat_valve`) quyết định lượng nhiệt bổ sung $\dot{Q}_{reheat}$.

---

### 2. Phương trình cân bằng nhiệt lượng nạp vào phòng (`vav.py`, dòng 443–452)

Tổng nhiệt lượng ròng $\dot{Q}_{net}$ nạp vào phòng trong mỗi bước thời gian được tính bằng:

$$\dot{Q}_{net} = \underbrace{\dot{m}_{air} \cdot C_p \cdot (T_{supply\_air} - T_{zone})}_{\text{Thành phần khí lạnh máy tổng}} + \underbrace{\dot{Q}_{reheat}}_{\text{Thành phần sưởi nước nóng}}$$

Trong đó:
- $\dot{m}_{air}$: Lưu lượng khối không khí ($kg/s$), tỉ lệ thuận với độ mở van gió `damper` và căn bậc hai áp suất tĩnh.
- $C_p$: Nhiệt dung riêng của không khí ($1005\ J/kg\cdot K$).
- $(T_{supply\_air} - T_{zone})$: Do máy tổng chỉ làm lạnh nên luôn có $T_{supply\_air} < T_{zone}$. Vì vậy, số hạng này **LUÔN MANG DẤU ÂM (tức là luôn có tác dụng làm lạnh phòng)**.
- $\dot{Q}_{reheat}$: Nhiệt lượng do cuộn nước nóng truyền vào luồng khí ($W$), luôn $\ge 0$.

---

### 3. Nguyên tắc điều khiển phối hợp 2 van (tự rút ra)

1. **Khi phòng BỊ LẠNH (Cần sưởi):**
   - Van gió `damper` giảm về 10% để ngăn dòng khí lạnh tràn vào.
   - Chỉ mở van sưởi `reheat_valve` để nung ấm lượng khí nhỏ đó lên dải nhiệt dễ chịu (giới hạn tối đa 35°C theo quy chuẩn thiết kế).
2. **Khi phòng BỊ NÓNG (Cần làm mát):**
   - Van sưởi `reheat_valve` đóng.
   - Van gió `damper` mở to tỉ lệ thuận với zone_error để đón nhiều khí lạnh từ máy tổng.
3. **Khi phòng VỪA VẶN (Vùng Deadband):**
   - Cả 2 van đều giữ ở mức tối thiểu (`damper` = 10%, `reheat` = 0%) để tối ưu hóa năng lượng.

---

## 📝 Nhật ký các phiên làm việc chi tiết

### Ngày 20/11/2026
- **Phiên 1**
- **Thời gian:** 23:45 (19/11/2026) – 01:34 (20/11/2026) (Tổng phiên 1: 1 tiếng 50p)
- **Công việc đã làm:**
  - Nhận và đọc tài liệu dự án để hiểu bối cảnh cuộc thi HVAC và phân chia vai trò 3 thành viên.
  - Clone code từ GitHub nhóm https://github.com/24021368-DucAnh/smart-buildings-hvac-2026.git về local (`smart-buliding-2026`).
  - Cài đặt depency trên máy
  - `Run python -m smart_buildings.evaluate --policies transfer pid --buildings building_train_1 --weathers fairbanks_1` để check xem `tranfer` (ko thay đổi các van hay gì cả) và `pid` (thay đổi các van theo nguyên lý nóng thì mở van to, lạnh thì mở sưởi)
  - So sánh điểm số thấy tranfer trả về reward = -43818.80 và pid trả về reward=-1362.92 -> thấy chỉ với policy cơ bản đã giảm số điểm phạt đi rất nhiều lần.
  - Đọc và phân tích hàm `_command_zones` trong `smart_buildings/baselines/pid.py` (line 182-212)
  -> Cơ chế còn đơn giản: Van gió damper mở theo tỉ lệ sai số nhiệt độ (và lệch 2 độ thì max công suất), van nhiệt (reheat) chạy theo dạng bật/tắt (Chỉ cần lạnh một chút là bật 100%, hết là đóng)
  - Xác định hướng cải tiến: Làm mịn van sưởi, và bổ sung tích phân (I) kèm chống kẹt van (anti-windup) -> không dùng công thức đơn giản như cũ

---

- **Phiên 2**
- **Thời gian:** 01:40 (20/11/2026) – 02:31 (20/11/2026) (Tổng phiên 2: 50p)
- **Công việc đã làm:**
  - Tách riêng toàn bộ logic điều khiển các van ra một file độc lập 
  (`team/policy/zone_controller.py`) để có thể tự test mà không ảnh hưởng đến code chung của nhóm.
  - Kiểm tra xem module có tương tự với code base của ban tổ chức không bằng cách Tạo script chạy thử nghiệm riêng (`team/evaluate_a.py`) và cho chạy so sánh trực tiếp giữa bản mới của A (`member_a`) và bản mẫu (`pid`)  
  --> kết quả đo điểm trên tòa nhà 1 thời tiết lạnh:
  - `member_a`: -1362.92
  - `pid`: -1362.92
  - Kết luận: Hai kết quả bằng nhau -> việc tách module riêng hoàn thành, đường truyền dữ liệu thông suốt, và có thể bắt đầu thay đổi công thức van để diều chỉnh điểm.

---

- **Phiên 3**
- **Thời gian:** 12:21 (20/11/2026) – 15:43 (20/11/2026) (Tổng phiên 3: 3h20p)
- **Công việc đã làm:**
  - Thử nghiệm: Làm mịn van sưởi nước nóng (reheat_valve) trong `zone_controller.py` (chuyển từ bật/tắt sang mở tỉ lệ theo độ lệch nhiệt độ).
  - Chạy đo điểm kiểm chứng trên kịch bản thời tiết lạnh: `building_train_1` / `fairbanks_1`.
- **Minh chứng & Kết quả thực tế:**
  - pid (bản gốc của BTC): -1362.92
  - member_a (sau khi làm mịn van sưởi): -1521.09
  - Kết quả: Điểm số bị tụt ~158 điểm.
  - Nguyên nhân: do trong kịch bản fairbanks cực kỳ lạnh, nhiệt độ phòng giảm rất nhanh, khi làm mịn van sưởi (lệch ít chỉ mở 20-30%) lượng nước nóng cấp vào ko đủ mạnh để bù nhiệt mất
  --> Phòng sẽ bị ấm lên rất chậm -> điểm phạt comfort tích lũy làm tổng điểm kém đi nhiều.
- **Rút ra:**
  - Với thời tiết lạnh, sưởi cần dứt khoát như thuật toán pid của btc (tức là đóng mở 100% công suất)
  - Hướng khắc phục: rút ngắn ngưỡng mở sưởi max công suất từ 2 -> 0.4 - 0.5 hoặc có thể đổi sang điều chỉnh van gió mát(damper)

---

- **Phiên 4**
- **Thời gian:** 16:30 – 19:11 (20/11/2026) (Tổng phiên 4: 2h40p)
- **Công việc đã làm:**
  - Chạy đo đạc mở rộng trên toàn bộ 5 vùng khí hậu của `building_train_1` để đánh giá toàn diện thuật toán van sưởi mới. (`python team/evaluate_a.py --policies member_a pid --buildings building_train_1`)
  - Lập bảng so sánh điểm số chi tiết giữa `member_a` và bản mẫu `pid`.
  - Thiết lập bảng điểm đối chứng các khí hậu để làm mốc phát triển cho các tính năng tiếp theo.
  - Xem lại công thức tính nhiệt độ ròng được nạp vào phòng mỗi một khoảng thời gian (`vav.py`)

- **Bảng điểm thực nghiệm đa khí hậu (Base Benchmark):**

| Kịch bản (Tòa nhà 1) | Kiểu thời tiết | Điểm PID (Cũ) | Điểm Member A (Mới) | Chênh lệch (Cải thiện) | Đánh giá |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `atlanta_2` | Ôn hòa ẩm | -226.63 | **-216.27** | **+10.36** |  Tối ưu hơn (Tiết kiệm sưởi) |
| `phoenix_5` | Nóng khô sa mạc | -1353.19 | **-1338.86** | **+14.33** |  Thoải mái hơn (Giảm sốc nhiệt) |
| `denver_7` | Khô mát vùng cao | -268.54 | **-267.09** | **+1.45** |  Thắng nhẹ |
| `singapore_8` | Nóng ẩm xích đạo | **-271.45** | -287.08 | -15.63 |  Thua nhẹ |
| `fairbanks_1` | Băng giá cực đoan | **-1362.92** | -1521.09 | -158.17 |  Thua nặng (Thiếu nhiệt) |

- **Bản chất rút ra:**
  - *Tại sao thắng ở Atlanta, Phoenix, Denver?* Ở các vùng này không quá lạnh, thuật toán cũ chỉ cần lạnh nhẹ là bật 100% sưởi gây sốc nhiệt và tốn điện. Việc A làm mượt van sưởi đã phát huy tác dụng rõ rệt: vừa êm nhiệt, vừa tiết kiệm năng lượng.
  - *Tại sao thua ở Fairbanks?* Xứ băng giá mất nhiệt quá nhanh, van sưởi mở từ tốn làm phòng bị rét kéo dài.
  - *Kết luận:* Không thể dùng một công thức cố định cho mọi thời tiết. Cần cơ chế điều khiển thích ứng (Adaptive) theo nhiệt độ ngoài trời.

---

### Ngày 22/11/2026
- **Phiên 5**
- **Thời gian:** 23:30 – 01:53 (23/11/2026) (Tổng phiên 5: 2h20p)
- **Công việc đã làm:**
  - Phân tích Master Plan và quyết định chốt chọn `pid_water` (`PIDWaterResetPolicy`) làm Base chung chính thức của nhóm (vì `pid_water` có điểm tổng thể 0.054, tốt hơn nhiều so với `pid` cũ 0.067).
  - Cập nhật file `team/policy/member_a_policy.py`: chuyển từ kế thừa `PIDPolicy` sang kế thừa `PIDWaterResetPolicy`.
  - Chạy mô phỏng kiểm tra kết nối (plumbing test) giữa `member_a` và `pid_water` trên kịch bản `building_train_1/fairbanks_1` đủ 8640 bước:
    `python -m team.evaluate_a --policies pid_water member_a --buildings building_train_1 --weathers fairbanks_1 --steps 8640`
- **Minh chứng & Kết quả thực tế:**
  - `pid_water`: -2607.41
  - `member_a`: -2607.41
  - Kết luận: Hai kết quả bằng nhau tuyệt đối -> Việc chuyển Base chung sang `pid_water` oke.

---

### Ngày 23/11/2026
- **Phiên 6**
- **Thời gian:** 05:15 – 06:25 (23/11/2026) (Tổng phiên 6: 1h10p)
- **Công việc đã làm:**
  - Xác định và sửa 2 điểm yếu cốt lõi trong `team/policy/zone_controller.py`:
    1. Đọc dải nhiệt độ chuẩn trực tiếp từ 2 cảm biến setpoint `{vav_id}_zone_air_heating_temperature_setpoint_sensor` và `cooling_temperature_setpoint_sensor` trong `obs` thay vì tự tính giờ trong ngày (giúp khớp 100% với hàm chấm điểm của BTC và không bị lệch ngày nghỉ lễ).
    2. Triển khai nguyên lý điều khiển phối hợp 2 van : Khi phòng bị lạnh (cần sưởi), mở van sưởi theo tỷ lệ nhưng ép van gió ở mức tối thiểu 10% (`-1.0`). Điều này ngăn không cho gió lạnh từ máy tổng thổi làm nguội cuộn sưởi như các phiên trước.
  - Chạy mô phỏng kiểm chứng lại trên kịch bản rét đậm `building_train_1/fairbanks_1` đủ 8640 bước để so sánh trực tiếp với `pid_water`.
- **Minh chứng & Kết quả thực tế:**
  - `pid_water` (base gốc): -2607.41
  - `member_a` (sau khi sửa cảm biến + phối hợp 2 van): **-1270.55**
  - Kết quả: Điểm tăng +1336.86 (giảm 51.3% điểm phạt so với `pid_water`, tốt hơn mức -1362.92 của bản `pid` cũ).
- **Phân tích thành phần điểm (lấy từ `summary.json` của từng policy):**

| Thành phần | `pid_water` | `member_a` | Ghi chú |
| :--- | :---: | :---: | :--- |
| Tiện nghi (productivity regret) | -1345.0 | -1339.4 | Gần như không đổi |
| Chi phí năng lượng | 3550.3 | 860.0 | Giảm khoảng 76% |
| Phát thải carbon | 5451.7 | 1474.7 | Giảm khoảng 73% |
| Nhiệt độ phòng trung bình | 16.87°C | 16.68°C | Cả hai đều dưới dải tiện nghi |

  - Công thức kiểm tra: tổng điểm = 0.6 × tiện nghi − 0.2 × năng lượng − 0.2 × carbon (ví dụ `member_a`: 0.6 × (-1339.4) − 0.2 × 860.0 − 0.2 × 1474.7 = -1270.6).
- **Bản chất rút ra:**
  - Phần điểm tăng gần như toàn bộ đến từ năng lượng và carbon, không phải từ tiện nghi. Khép van gió khi sưởi làm giảm lượng gió lạnh phải hâm nóng, nên tốn ít điện quạt và ít gas cho lò hơn.
  - Phòng vẫn lạnh như trước (trung bình khoảng 16.7°C). Phần tiện nghi bây giờ chiếm khoảng 804 / 1270 điểm phạt, tức là phần lớn điểm phạt còn lại ở Fairbanks nằm ở việc phòng không đủ ấm.

---

### Ngày 24/11/2026
- **Phiên 7**
- **Thời gian:** 23:15 (24/11/2026) – 03:10 (25/11/2026) (Tổng phiên 7: 3h55p)
- **Công việc đã làm:**
  - Sửa lỗi gọi lặp trong `team/policy/member_a_policy.py`: ghi đè `_command_zones` thành `pass` và gọi `self.zone_controller.adjust(obs, action)` đúng 1 lần mỗi bước trong `get_action(obs)` thay vì bị gọi lặp 4 lần theo số AHU
  - Kiểm tra dữ liệu nhiệt độ từng phòng của Phiên 6 (`timeseries.csv`), phát hiện các phòng góc mất nhiệt mạnh (`zone_0`, `zone_3`, `zone_28`, `zone_31`) bị thiếu nhiệt vì khí xả VAV giới hạn tối đa ở 35°C (`308.15 K`), nên khi ép cố định `damper = 10%` thì lưu lượng gió không tải đủ nhiệt vào phòng (`zone_0` chỉ đạt trung bình 13.26°C, lệch 7.74 K > 5 K nên bị phạt bình phương).
  - Cải tiến Bước 1 trong `team/policy/zone_controller.py` — Mở van gió theo 2 nấc khi sưởi (Staged Dual-Maximum):
    - Hạ `zone_reheat_full_k` từ `2.0` xuống `1.0` để van nước nóng mở 100% sớm hơn khi phòng lạnh từ 1.0 K.
    - Nấc 1 (`error_heat <= 1.0 K`): giữ van gió ở mức sàn 10% (`-1.0`), chỉ mở dần van nước nóng.
    - Nấc 2 (`error_heat > 1.0 K`, sau khi van nước nóng đã mở 100% mà phòng vẫn lạnh): mở tăng dần van gió theo phần lạnh vượt ngưỡng `extra_cold = error_heat - 1.0`, nhưng giới hạn trần tối đa ở `max_heating_damper = 0.35` (35% gió, vùng đạt công suất truyền nhiệt cao nhất mà không để gió lạnh lấn át cuộn sưởi).
  - Chạy kiểm chứng lại trên `building_train_1/fairbanks_1` đủ 8640 bước.
- **Minh chứng & Kết quả thực tế:**
  - `pid_water` (base gốc): -2607.41
  - `member_a` (Phiên 6 - ép cứng van gió 10% khi sưởi): -1270.55
  - `member_a` (Phiên 7 - mở van gió 2 nấc khi sưởi, trần 35%): **-950.24**
  - Kết quả: Điểm tổng tăng thêm **+320.31 điểm** so với Phiên 6 (và tăng +1657.17 điểm so với `pid_water`).
- **Phân tích thành phần điểm và nhiệt độ phòng (`summary.json` & `timeseries.csv`):**

| Chỉ số | `pid_water` | `member_a` (Phiên 6) | `member_a` (Phiên 7) | Ghi chú |
| :--- | :---: | :---: | :---: | :--- |
| **Tổng điểm (total reward)** | -2607.41 | -1270.55 | **-950.24** | Giảm 63.6% điểm phạt so với base |
| Tiện nghi (productivity regret) | -1345.0 | -1339.4 | **-759.09** | Giảm 43.3% phạt tiện nghi |
| Chi phí năng lượng | 3550.3 | 860.0 | 878.84 | Chỉ tăng nhẹ ~2% so với Phiên 6 |
| Phát thải carbon | 5451.7 | 1474.7 | 1595.09 | Tăng ~8% để đổi lấy nhiệt sưởi |
| Nhiệt độ TB `zone_0` (phòng tệ nhất) | ~16.5°C | 13.26°C | **17.99°C** | Tăng +4.73°C, thoát vùng phạt > 5 K |
| Số phòng có nhiệt độ TB < 18°C | 15 phòng | 10 phòng | **1 phòng** | Chỉ còn `zone_0` ở mức 17.99°C |

- **Bản chất rút ra:**
  - Mở van gió lên tối đa 35% ở Nấc 2 đã tải thêm nhiệt từ cuộn sưởi vào các phòng góc như `zone_0`, kéo độ lệch trung bình của phòng tệ nhất từ 7.74 K xuống 3.02 K (nằm gọn dưới ngưỡng 5 K nên không còn bị phạt bình phương), trong khi chi phí năng lượng chỉ tăng rất ít (từ 860 lên 878.8).

---

### Ngày 25/11/2026
- **Phiên 8**
- **Thời gian:** 23:13 (25/11/2026) – 00:30 (26/11/2026) (Tổng phiên 8: 1h17p)
- **Công việc đã làm:**
  - Cải tiến Bước 2 trong `team/policy/zone_controller.py`: Thêm khâu tích phân (PI) kèm chống tràn (anti-windup) riêng cho từng phòng (`self.zone_integrals`):
    - Tham số khởi điểm: `ki = 0.05`, `integral_limit = 2.0`, `integral_decay = 0.85`.
    - Cập nhật tích phân theo 3 trạng thái: xả dần (`*= 0.85`) khi phòng đã vào dải tiện nghi (`signed_error == 0`), reset khi đổi chiều nóng/lạnh (`integral * signed_error < 0`), và cộng dồn `ki * signed_error` kèm kẹp biên `[-2.0, +2.0]` khi phòng vẫn lệch.
    - Cộng phần tích phân vào sai số hiện tại (`effort_heat`, `effort_cool`) để điều khiển van sưởi và van gió 2 nấc, nhưng vẫn giữ điều kiện kích hoạt nhánh theo sai số thực (`error_heat > 0` / `error_cool > 0`) để không mở van khi phòng đã vào dải tiện nghi.
  - Chạy kiểm chứng riêng `member_a` trên `building_train_1/fairbanks_1` đủ 8640 bước (`python -m team.evaluate_a --policies member_a --buildings building_train_1 --weathers fairbanks_1 --steps 8640`).
- **Minh chứng & Kết quả thực tế:**
  - `pid_water` (base gốc): -2607.41
  - `member_a` (Phiên 7 - 2 nấc van gió, thuần P): -950.24
  - `member_a` (Phiên 8 - 2 nấc van gió + PI anti-windup): **-852.35**
  - Kết quả: Điểm tổng tăng thêm **+97.89 điểm** (giảm 10.3% tổng điểm phạt so với Phiên 7, và giảm 67.3% so với base `pid_water`).
- **Phân tích thành phần điểm và nhiệt độ phòng (`summary.json` & `timeseries.csv`):**

| Chỉ số | `member_a` (Phiên 7) | `member_a` (Phiên 8) | Thay đổi |
| :--- | :---: | :---: | :--- |
| **Tổng điểm (total reward)** | -950.24 | **-852.35** | Tăng +97.89 điểm (-10.3% phạt) |
| Tiện nghi (productivity regret) | -759.09 | **-613.35** | Giảm 19.2% phạt tiện nghi |
| Chi phí năng lượng | 878.84 | **843.69** | Giảm ~4% (thấp hơn cả Phiên 6) |
| Phát thải carbon | 1595.09 | **1577.99** | Giảm nhẹ ~1% |
| Độ lệch nhiệt độ TB toàn tòa | 1.43 K | **1.16 K** | Giảm 0.27 K |
| Số phòng đạt nhiệt độ TB >= 20.5°C | 6 phòng | **11 phòng** | Tăng thêm 5 phòng |
| Nhiệt độ TB `zone_0` (giờ có người) | 17.99°C | 17.24°C | Giảm nhẹ 0.75°C (vẫn < 5 K lệch) |

- **Bản chất rút ra:**
  - Khâu tích phân (PI) giúp kéo thêm nhiều phòng thoát khỏi sai số tĩnh (số phòng đạt >= 20.5°C tăng từ 6 lên 11 phòng), đồng thời giảm đồng loạt cả 3 thành phần: tiện nghi (-19.2% phạt), năng lượng (-4%), và carbon (-1%).

---

### Ngày 26/11/2026
- **Phiên 9**
- **Thời gian:** 00:34 – 01:03 (26/11/2026) (Tổng phiên 9: 29p)
- **Công việc đã làm:**
  - Phân tích dữ liệu theo giờ trong ngày của Phiên 8 (`fairbanks_1`), thấy khung giờ 6h sáng có điểm phạt tiện nghi cao nhất trong ngày (`-88.88`, gấp hơn 2 lần buổi chiều `-38`) dù số người thấp nhất (`7.55`), do ban đêm phòng giữ ở 16°C rồi 6h sáng mới nhảy mục tiêu lên 21°C.
  - Cải tiến Bước 3 trong `team/policy/zone_controller.py`: Đón đầu 60 phút trước giờ vào ca (Pre-conditioning) dựa trên 2 cờ có sẵn trong `obs` (`comfort_mode_now` và `comfort_mode_soon`, đã tự động tính sẵn cuối tuần và ngày lễ):
    - Khi `comfort_mode_now < 0.5` và `comfort_mode_soon >= 0.5`, thay dải mục tiêu `[low, high]` của phòng bằng `self.comfort_temp_window` sớm hơn 60 phút.
  - Chạy kiểm chứng riêng `member_a` trên `building_train_1/fairbanks_1` đủ 8640 bước.
- **Minh chứng & Kết quả thực tế:**
  - `member_a` (Phiên 8 - chưa đón đầu): -852.35
  - `member_a` (Phiên 9 - có đón đầu 60 phút): **-848.13** (tăng +4.22 điểm; riêng phạt tiện nghi lúc 6h sáng giảm từ -88.88 xuống -81.21; tổng regret cả tháng giảm từ -613.35 xuống -603.94).
- **Bản chất rút ra:**
  - Cơ chế đón đầu ở van phòng hoạt động đúng nhưng chỉ tăng nhẹ (+4.22 điểm) do đụng ranh giới máy tổng AHU: lúc 5h sáng, base `pid_water` vẫn so với ngưỡng đêm 289 K (15.85°C), nên khi van phòng kéo nhiệt độ nhích lên 16.34°C thì AHU tự tắt quạt và bơm nước nóng (tỉ lệ bật AHU giờ 5 giảm từ 38.9% xuống 33.1%).
  - Việc bật AHU đón đầu thuộc phạm vi `AHU/HWS discrete` của Thành viên B; van phòng của A hiện đã sẵn sàng phối hợp khi ghép nối ở mốc G2.

---

- **Phiên 10**
- **Thời gian:** 04:00 – 06:23 (26/11/2026) (Tổng phiên 10: 2h23p)
- **Công việc đã làm:**
  - Chạy kiểm chứng đối chứng `member_a` (bản hoàn thiện Chặng 1: cảm biến setpoint + van gió 2 nấc + PI anti-windup + đón đầu 60 phút) với base `pid_water` trên 4 khí hậu còn lại của `building_train_1` đủ 8640 bước mỗi kịch bản:
    `python -m team.evaluate_a --policies pid_water member_a --buildings building_train_1 --weathers atlanta_2 denver_7 phoenix_5 singapore_8 --steps 8640`
  - Tổng hợp kết quả và tách thành phần điểm (tiện nghi, năng lượng, carbon) từ `summary.json` cho toàn bộ 5 khí hậu của `building_train_1`.
- **Bảng tổng hợp đối chứng 5 khí hậu (`building_train_1`, 8640 bước):**

| Kịch bản | Kiểu khí hậu | `pid_water` | `member_a` (Chặng 1) | Chênh lệch | Giảm phạt (%) | Thành phần cải thiện chính (`summary.json`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `atlanta_2` | Ôn hòa ẩm | -212.35 | **-190.18** | +22.17 | -10.4% | Giảm cả 3: regret -297.4 -> -272.4, energy 93.4 -> 79.2, carbon 76.3 -> 54.5 |
| `denver_7` | Khô mát vùng cao | -267.40 | **-267.09** | +0.31 | -0.1% | Regret tương đương (-434.4 vs -435.8), giảm nhẹ energy & carbon |
| `phoenix_5` | Nóng khô sa mạc | -1092.93 | **-650.24** | **+442.69** | **-40.5%** | Giảm mạnh cả 3: regret -1010.7 -> -570.6 (-43.5%), energy 1807.9 -> 1209.2 (-33.1%), carbon 624.5 -> 330.2 (-47.1%) |
| `singapore_8` | Nóng ẩm xích đạo | -254.55 | **-223.26** | +31.29 | -12.3% | Giảm cả 3: regret -268.3 -> -219.8 (-18.1%), energy 371.1 -> 365.9, carbon 96.8 -> 91.1 |
| `fairbanks_1` | Băng giá cực đoan | -2607.41 | **-848.13** | **+1759.28** | **-67.5%** | Giảm cả 3: regret -1345.0 -> -603.9 (-55.1%), energy 3550.3 -> 846.1 (-76.2%), carbon 5451.7 -> 1582.7 (-71.0%) |
| **Trung bình 5 khí hậu (LB scale)** | — | **0.10265** | **0.05044** | — | **-50.9%** | Tổng loss giảm từ 4434.64 xuống 2178.90 |

- **Bản chất rút ra:**
  - Bộ điều khiển Chặng 1 của A thắng `pid_water` trên **5/5 khí hậu**, không bị đánh đổi giữa xứ lạnh và xứ nóng.
  - Ở xứ nóng (`phoenix_5`, `singapore_8`), khâu tích phân PI giúp kéo nhiệt độ phòng nằm gọn trong dải làm mát (giảm 43.5% phạt tiện nghi ở Phoenix và 18.1% ở Singapore), đồng thời phối hợp 2 van tránh thổi thừa gió lạnh vào sáng sớm sa mạc nên giảm thêm 33% năng lượng và 47% carbon ở Phoenix.

---

### Ngày 26–27/11/2026
- **Phiên 11**
- **Thời gian:** Đợt 1: 26/11/2026 (10:53 – 11:37); Đợt 2: 27/11/2026 (01:35 – 02:39, chốt số liệu tại mốc 26/30 kịch bản)
- **Công việc đã làm:**
  - Chạy mở rộng bản Chặng 1 của `member_a` (đủ 8640 bước mỗi kịch bản) trên các tòa nhà còn lại trong tập 30 kịch bản (`building_train_2`, `building_train_4`, `building_train_5`, `building_train_7`, `building_train_8`).
  - Chia 11 kịch bản còn lại sau Đợt 1 thành 3 luồng chạy song song:
    - Luồng 1: `python -m team.evaluate_a --policies member_a --buildings building_train_2 building_train_4 --weathers singapore_1 atlanta_5 denver_2 fairbanks_4 --steps 8640`
    - Luồng 2: `python -m team.evaluate_a --policies member_a --buildings building_train_4 building_train_5 --weathers phoenix_8 singapore_3 atlanta_6 denver_3 --steps 8640`
    - Luồng 3: `python -m team.evaluate_a --policies member_a --buildings building_train_5 --weathers fairbanks_5 phoenix_1 singapore_4 --steps 8640`
  - Kiểm tra và tổng hợp toàn bộ bảng điểm các vùng đã chạy xong (26/30 kịch bản) từ `summary.json`. Còn 4 kịch bản chưa hoàn thành tại thời điểm chốt bảng: `building_train_4/denver_2`, `building_train_4/fairbanks_4`, `building_train_5/denver_3`, `building_train_5/singapore_4`.
- **Bảng tổng hợp điểm `member_a` (Chặng 1) theo 6 tòa nhà × 5 khí hậu (26/30 kịch bản, 8640 bước):**

| Tòa nhà | Atlanta | Denver | Fairbanks | Phoenix | Singapore | Đã xong | Điểm TB / kịch bản | LB quy đổi |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `building_train_1` | -190.18 (`atlanta_2`) | -267.09 (`denver_7`) | -848.13 (`fairbanks_1`) | -650.24 (`phoenix_5`) | -223.26 (`singapore_8`) | 5/5 | -435.78 | 0.05044 |
| `building_train_2` | -155.40 (`atlanta_3`) | -344.97 (`denver_8`) | -623.74 (`fairbanks_2`) | -396.61 (`phoenix_6`) | -181.81 (`singapore_1`) | 5/5 | -340.51 | 0.03941 |
| `building_train_4` | -230.13 (`atlanta_5`) | *(chưa xong)* | *(chưa xong)* | -246.25 (`phoenix_8`) | -236.05 (`singapore_3`) | 3/5 | -237.48 | 0.02749 |
| `building_train_5` | -269.80 (`atlanta_6`) | *(chưa xong)* | -129.54 (`fairbanks_5`) | -273.20 (`phoenix_1`) | *(chưa xong)* | 3/5 | -224.18 | 0.02595 |
| `building_train_7` | -379.39 (`atlanta_8`) | -270.51 (`denver_5`) | -412.80 (`fairbanks_7`) | -331.17 (`phoenix_3`) | -233.00 (`singapore_6`) | 5/5 | -325.37 | 0.03766 |
| `building_train_8` | -231.04 (`atlanta_1`) | -159.27 (`denver_6`) | -506.78 (`fairbanks_8`) | -582.76 (`phoenix_4`) | -221.11 (`singapore_7`) | 5/5 | -340.20 | 0.03937 |
| **Tổng hợp tạm (26/30)** | **TB -242.66 (6/6)** | **TB -260.46 (4/6)** | **TB -504.20 (5/6)** | **TB -413.37 (6/6)** | **TB -219.05 (5/6)** | **26/30** | **-330.55** | **0.03826** |

- **Phân tích tỷ trọng thành phần phạt theo 5 khí hậu (trên 26 kịch bản đã xong):**

| Khí hậu | Số kịch bản đã xong | Điểm TB / kịch bản | LB quy đổi | Tỷ trọng phạt tiện nghi | Tỷ trọng năng lượng + carbon |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `atlanta` | 6/6 | -242.66 | 0.02809 | 76.6% | 23.4% |
| `denver` | 4/6 | -260.46 | 0.03015 | 83.3% | 16.7% |
| `fairbanks` | 5/6 | -504.20 | 0.05836 | 62.4% | 37.6% |
| `phoenix` | 6/6 | -413.37 | 0.04784 | 65.0% | 35.0% |
| `singapore` | 5/6 | -219.05 | 0.02535 | 59.7% | 40.3% |
| **Toàn bộ 26 kịch bản** | **26/30** | **-330.55** | **0.03826** | **67.8%** | **32.2%** (20.0% năng lượng + 12.2% carbon) |

- **Chi tiết thành phần điểm từ `summary.json` của 21 kịch bản mới chạy thêm (ngoài 5 kịch bản `building_train_1` đã ghi ở Phiên 10):**

| Kịch bản | Tổng điểm | Tiện nghi (regret) | Năng lượng | Carbon | Nhiệt độ phòng TB |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `building_train_2/atlanta_3` | -155.40 | -194.15 | 157.28 | 37.26 | 23.91°C |
| `building_train_2/denver_8` | -344.97 | -515.46 | 83.70 | 94.75 | 21.06°C |
| `building_train_2/fairbanks_2` | -623.74 | -862.54 | 201.07 | 330.01 | 19.81°C |
| `building_train_2/phoenix_6` | -396.61 | -385.56 | 638.96 | 187.43 | 24.27°C |
| `building_train_2/singapore_1` | -181.81 | -188.87 | 275.08 | 67.38 | 24.32°C |
| `building_train_4/atlanta_5` | -230.13 | -231.84 | 369.18 | 85.92 | 24.29°C |
| `building_train_4/phoenix_8` | -246.25 | -388.69 | 50.21 | 14.99 | 22.95°C |
| `building_train_4/singapore_3` | -236.05 | -225.88 | 408.09 | 94.52 | 24.35°C |
| `building_train_5/atlanta_6` | -269.80 | -297.27 | 347.93 | 109.26 | 24.02°C |
| `building_train_5/fairbanks_5` | -129.54 | -186.37 | 71.41 | 17.18 | 23.34°C |
| `building_train_5/phoenix_1` | -273.20 | -433.78 | 31.94 | 32.70 | 21.91°C |
| `building_train_7/atlanta_8` | -379.39 | -543.61 | 103.28 | 162.86 | 19.80°C |
| `building_train_7/denver_5` | -270.51 | -305.24 | 337.46 | 99.38 | 23.63°C |
| `building_train_7/fairbanks_7` | -412.80 | -567.72 | 135.06 | 225.77 | 19.32°C |
| `building_train_7/phoenix_3` | -331.17 | -357.99 | 454.12 | 127.74 | 24.11°C |
| `building_train_7/singapore_6` | -233.00 | -231.87 | 376.33 | 93.05 | 24.31°C |
| `building_train_8/atlanta_1` | -231.04 | -319.74 | 77.10 | 118.90 | 20.34°C |
| `building_train_8/denver_6` | -159.27 | -190.34 | 182.11 | 43.22 | 23.83°C |
| `building_train_8/fairbanks_8` | -506.78 | -402.79 | 452.78 | 872.77 | 18.10°C |
| `building_train_8/phoenix_4` | -582.76 | -551.99 | 974.80 | 283.06 | 24.14°C |
| `building_train_8/singapore_7` | -221.11 | -222.67 | 347.96 | 89.61 | 24.33°C |

- **Bản chất rút ra:**
  - Bộ điều khiển Chặng 1 giữ ổn định khi mở rộng sang 5 tòa nhà chưa dùng để chỉnh tham số (`building_train_2`, `4`, `5`, `7`, `8`): điểm LB quy đổi trung bình trên 26 kịch bản đạt `0.03826`, tốt hơn mức `0.05044` trên riêng `building_train_1` (vì `building_train_1` là một trong những tòa khó nhất).
  - Phạt tiện nghi vẫn chiếm tỷ trọng lớn nhất (`67.8%` tổng phạt trên 26 kịch bản), tập trung chủ yếu ở hai vùng khắc nghiệt `fairbanks` (TB `-504.20`) và `phoenix` (TB `-413.37`).
  - Trong cùng một khí hậu lạnh (`fairbanks`), cơ cấu phạt khác nhau rõ giữa các tòa nhà: `building_train_2/fairbanks_2` mất 83.0% ở tiện nghi (có phòng góc tụt sâu), trong khi `building_train_1/fairbanks_1` mất 57.3% ở năng lượng và carbon. Điều này cho thấy mức trần gió sưởi cố định 35% và độ nhạy làm mát cố định chưa tối ưu đồng đều cho mọi kiểu tòa nhà và trạng thái nguồn cấp.
