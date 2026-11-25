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
  - Hướng tiếp theo cần nhắm vào phần tiện nghi: tìm lúc nào cần mở thêm van gió để đưa thêm nhiệt vào phòng khi trời rét sâu (giới hạn khí xả 35°C nên van gió quá nhỏ thì nhiệt đưa vào cũng bị giới hạn).

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
  - Hướng tiếp theo (Bước 2): Thêm khâu tích phân (PI) + chống tràn (anti-windup) cho từng phòng để kéo nhiệt độ các phòng còn lệch 1–3 K tiến sát hẳn về ngưỡng mục tiêu 294 K (20.85°C).

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
  - Hướng tiếp theo (Bước 3): Sưởi đón đầu trước giờ làm việc (Pre-heating) và chạy đo điểm đối chứng trên đủ 5 khí hậu của `building_train_1` để kiểm tra tính tổng quát hóa sang vùng nóng.