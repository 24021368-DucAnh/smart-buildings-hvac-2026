# NHẬT KÝ CÔNG VIỆC — THÀNH VIÊN A (ZONE & VAV)


---

###  Ngày 20/11/2026
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

- **Kế hoạch cải thiện từng phần tiếp theo (Dựa trên Base này):**
  - **Mục tiêu 1:** Phù hợp kịch bản Fairbanks bằng cách điều khiển thích ứng: Khi nhiệt độ ngoài trời âm sâu -> bật sưởi 100%; khi trời bình thường -> giữ nguyên logic làm mượt.
  - **Mục tiêu 2:** Tối ưu tiếp van gió làm mát (`damper`) để nâng điểm ở các xứ nóng (Phoenix, Singapore).

---

##  Cơ sở lý thuyết & Công thức nhiệt động lực học VAV

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
