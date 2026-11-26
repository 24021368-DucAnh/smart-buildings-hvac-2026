# B04 — lỗi dự báo, action coverage và sensor phase

26/11/2026. Frozen-model audit theo B04_PLAN/FINALv2.1. Đây là ghi chú kỹ thuật
AI-assisted để sinh viên đọc hiểu; báo cáo học phần do sinh viên tự viết.

## Mục tiêu và kiến trúc

Trả lời vì sao Ridge có RMSE tốt hơn nhưng MAE generated-dev xấu hơn, và dữ liệu
hiện tại cho phép kết luận gì trước B05. Không train model mới hay chạy simulator.

`B03 corpus -> validator/hash -> frozen Ridge -> zone_features -> predictions ->
residual/slices + action/readback diagnostics -> CSV/PNG/report -> review`.

CLI mới `team_tools/forecast_diagnostics.py` tái dùng `dataset.validate_corpus`,
`forecast.episodes/zone_features/predict`. Không viết lại normalizer hay evaluator.
Original Ridge: alpha1,16 features,1,537,920 train samples, scaler fit train-only.
Train1/2/4, validation5/7, generated0500 là development evidence đã xem từ trước.

## Nguồn và tính toàn vẹn

- Official source Apache-2.0:
  https://github.com/smart-buildings-2026/starter-kit @
  `1fb75606d12e016463fbc63de704967c5b2bf9d5`; LICENSE/NOTICE giữ nguyên.
- Model/B04 do B phát triển với hỗ trợ đáng kể của Codex/ChatGPT, thuật toán Ridge
  chuẩn bằng NumPy; nguồn thuật toán đã ghi trong PROJECT_KNOWLEDGE.md.
- Chẩn đoán/test/tài liệu mới có AI hỗ trợ. Không suy tác giả/AI usage của A/C.
- HEAD nền chẩn đoán main `b041343ec1104e7bccaeff52c486b657efe161ec`, bổ sung exact
  SHA256 của script/model/dataset/reference/numerical source trong JSON. Không
  đổi SHA receipt B03 hoặc giả toàn bộ code mới đã có trong HEAD nền.
- Model SHA256 `0ab9c94df325a11755c90e90b95c9e9a3248e862eca0188e7b53e68e9687ad4d`.
  Corpus6episodes:51,840 transitions/3,568,320 zone-transition samples.
- Cả12 dòng metric building×model cũ được tái hiện với tolerance1e-10. Chỉ phân
  tích sau khi hash/schema/metrics đều đúng; không bỏ hàng, clipping hay impute thêm.

## Kết quả chính

Validation Atlanta5: Ridge tốt MAE ở65/79zone; Singapore7:23/36zone.
Generated0500: chỉ9/120zone tốt hơn,111/120zone kém persistence về MAE.

| Generated0500 slice | Samples | Persistence MAE K | Ridge MAE K |
|---|---:|---:|---:|
| Toàn episode | 1,036,800 | 0.296897 | 0.336567 |
| abs(delta)<=0.1K | 634,143 | 0.011013 | 0.132188 |
| 0.1<abs(delta)<=1K | 314,413 | 0.578251 | 0.619599 |
| abs(delta)>1K | 88,244 | 1.348864 | 0.796841 |

Khoảng61.16% mẫu có abs(delta)<=0.1K. Ridge có lợi ở biến động lớn nhưng dự báo
khác0 quá nhiều ở vùng gần đứng yên. Ridge tối ưu tổng bình phương sai số, nên
giảm lỗi lớn có thể làm RMSE tốt hơn mà MAE điển hình xấu đi. Bias generated
`mean(pred-y)=-0.152920K`, không biến kết quả này thành hệ số hiệu chỉnh mới.
Đây là phân rã số học quan sát được; chưa chứng minh nguyên nhân vật lý duy nhất.

**Các slice dùng delta thật chỉ được xem sau khi có label.** Khi inference chưa
biết delta tương lai; không thể dùng quy tắc “delta thật lớn thì chọn Ridge” vì
đó là leakage/oracle. Không chọn model hoặc tune alpha theo generated đã xem.

## Action coverage và giới hạn học tác động điều khiển

Generated0500 có115/291 kênh action không đổi suốt episode, trong đó114/120 kênh
reheat không đổi. Train1/2/4 có lần lượt0/39,6/85,18/54 kênh reheat không đổi.
CSV còn có bins[-1,-0.5,0,0.5,1], std, unique(round4), switch rate và edge fractions.

Nhiều dòng dữ liệu không đồng nghĩa nhiều thử nghiệm action độc lập. Policy PID
chọn action theo nhiệt độ; action/nhiệt độ có quan hệ phản hồi và bị lịch/weather
chi phối. Pearson ở lag0/1/2/3 chỉ mô tả liên hệ, không chứng minh mở van gây delta
bao nhiêu. Không diễn giải kênh hằng là bug; nó có thể là hành vi hợp lý của Base
trong episode đó. Chưa đủ bằng chứng causal action response để làm pre-start.

Các feature của generated0500 nằm trong min/max train, nhưng MAE vẫn kém. Vì vậy
range check đơn giản không bảo đảm transfer. Dùng z-score từ scaler train cũ;
không fit lại scaler bằng validation/generated. Bounds chỉ là support diagnostic.

## Command, measured position và sensor phase

Source `vav.py`: action ghi `damper_command`, observable cùng tên đọc
`damper_setting`; `update_settings` áp mức mở tối thiểu(default0.1). `simulator.py`
gọi setup/update_settings rồi execute; zone-average được lấy trước solve và VAV
sensor nhận giá trị đó. `environment.step` áp action, wait_time rồi lấy observation.
Do đó actuator readback và thermal sensor phase là hai chuyện khác nhau.

Trên cả6episodes:

- Reheat readback trong obs[t+1] khớp command[t] 100% với tolerance1e-5.
- Damper thô có sai khác; nếu kiểm tra công thức cố định từ source
  `readback ~= max(command_native,0.1)`,100% mẫu khớp trong tolerance1e-5.
  MAE còn khoảng2.2e-9 đến4.5e-9 do biểu diễn số; không gọi là bit-exact.
- Đây là kiểm tra giả thuyết floor có sẵn từ source, không fit floor hay đổi data.
  Không chứng minh nhiệt độ đáp ứng tức thì hoặc xác định được physical lag.

Ví dụ chạy không cần simulator:

```python
import numpy as np
from team_tools.forecast_diagnostics import readback_alignment
command_normalized = np.array([-1., 0., 1.])
command_native = (command_normalized + 1) / 2  # [0,0.5,1]
observations = np.array([0.1, 0.1, 0.5, 1.]) # reset rồi3post-action readbacks
print(readback_alignment(command_native, observations, 0, floor=0.1))
```

Ra lệnh0% không làm vị trí damper xuống dưới10%. Đây là giới hạn thông gió,
không phải dữ liệu “bẩn” cần sửa. Lag0 trong chẩn đoán nghĩa command[t] so với
post-action readback[t+1], không phải command[t] so với obs[t] trước hành động.

## Tails và B01 còn mở

Ví dụ validation Atlanta5/VAV_7 step1262,15:10→15:15: observed sensor từ287.783K
lên302.257K, delta14.474K; Ridge dự báo0.225K, sai14.249K. CSV events giữ timestamp,
band/command và một worst event mỗi zone để điều tra. Không coi delta sensor này
là physical ground truth đã được chứng minh hợp lý. Không xóa/clipping các jump.
Ở Atlanta5, chỉ0.834% mẫu có abs(delta)>5K nhưng chiếm45.85% squared error Ridge.
B01 vẫn chưa đóng phần physical plausibility/tails; source chronology đúng không
tự chứng minh mọi biến động nhiệt độ đều hợp lý ngoài thực tế.

## Tái hiện trên Windows PowerShell

Chạy từ root checkout mới. Cần corpus B03 và **đúng file model gốc** ngoài Git;
dataset/model/raw artifacts không được đưa lên public repo. Trong Work hiện tại
đã có bản model sao byte-identical ở `artifacts/B04-original-model/ridge.npz`.
Teammate nhận model gốc qua kênh nội bộ và đối chiếu SHA trên; không relabel một
model train lại thành artifact gốc để vượt kiểm tra.

```powershell
.\.venv\Scripts\python.exe -m team_tools.forecast_diagnostics `
  data/generated/trajectories/b03-corpus-20261123-02 `
  --model artifacts/B04-original-model/ridge.npz `
  --output artifacts/B04-diagnostics-reproduce-01
```

Output phải tên mới. `report.json` ghi hashes,metrics,status,wall/CPU; CSV có
building/zones/slices/coverage/lags/readbacks/support/events. PNG có building
MAE/RMSE,zone delta-MAE,readback alignment,action occupancy. Tập generated không
fit gì; frozen holdout không mở. Budget600s kiểm tra hợp tác theo episode, không
phải watchdog cưỡng chế ngắt ở đúng giây600; một numerical thread.

`notebooks/B_research.ipynb` đọc public small checks để học mà không cần corpus.
Mean error(bias) giữ dấu; MAE lấy abs; RMSE bình phương nên phạt lỗi lớn mạnh hơn.
Boolean mask chọn slice để thống kê, không loại sample khỏi metric toàn tập.
Correlation khác causal effect; persistence là baseline dự báo delta0 hợp lệ.

## Nghiệm thu và bước kế tiếp

DoD: model/corpus/hash giữ nguyên; all12 metric cũ reproduce; đầy đủ mọi zone,
fixed slices/lag/coverage và tolerance; no refit/rollout/holdout; meaningful tests,
notebook nhỏ, report/registry/source/AI/time và technical review.

Kiểm chứng cuối:199tests+34subtests đạt,15 third-party warnings,88.84s.
14focused tests đạt lại;14tests đạt trên cây source không có generated data,
dùng installed environment cũ.10notebook code cells chạy fresh Python; Jupyter
kernel startup NOT RUN. Có independent technical AI review, không thay human signoff.
Run cuối11.702s wall/11.453125s processCPU. Ba run chẩn đoán giữ riêng tổng
40.546875s processCPU; không cộng test/training/Kaggle hoặc person-hours vào đây.
Không có simulation mới. Hashes/log refs và phạm vi thời gian nằm trong JSON.

Quyết định: **KEEP RIDGE OFFLINE, B05 OFF**. Chưa có control gain, chưa thay Base
hoặc code đang scoring Kaggle. B04 baseline dùng được cho nghiên cứu, chưa đủ để
làm bộ điều khiển preconditioning. B05 cần locked Base, predictor/fallback phù hợp
và BASE vs BASE+B full paired control evidence theo kế hoạch.

Thí nghiệm kế tiếp nên dùng validation để kiểm tra một thay đổi có lý do: bổ sung
observable thời tiết/plant hoặc history ngắn, giữ persistence mạnh, so cảMAE/RMSE
và per-building bias. Chưa chạy thí nghiệm đó trong audit này; không tự dùng bias
generated để hiệu chỉnh, không tăng horizon thành15–60phút khi chưa định nghĩa
label/window/split. Nếu cần thêm action diversity, phải thiết kế collection có
ngân sách và giới hạn an toàn riêng, không tự coi6episode hiện tại là causal data.
