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
  - Chạy đo điểm kiểm chứng trên kịch bản thời tiết lạnh: building_train_1 / fairbanks_1.
- **Minh chứng & Kết quả thực tế:**
  - pid (bản gốc của BTC): -1362.92
  - member_a (sau khi làm mịn van sưởi): -1521.09
  - Kết quả: Điểm số bị tụt ~158 điểm.
  - Nguyên nhân: do trong kịch bản fairbanks cực kỳ lạnh, nhiệt độ phòng giảm rất nhanh, khi làm mịn van sưởi (lệch ít chỉ mở 20-30%) lượng nước nóng cấp vào ko đủ mạnh để bù nhiệt mất
  --> Phòng sẽ bị ấm lên rất chậm -> điểm phạt comfort tích lũy làm tổng điểm kém đi nhiều.
- **Rút ra:**
  - Với thời tiết lạnh, sưởi cần dứt khoát như thuật toán pid của btc (tức là đóng mở 100% công suất)
  - Hướng khắc phục: rút ngắn ngưỡng mở sưởi max công suất từ 2 -> 0.4 - 0.5 hoặc có thể đổi sang điều chỉnh van gió mát(damper)