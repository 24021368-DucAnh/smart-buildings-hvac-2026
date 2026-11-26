# Nộp thử Smart Buildings — 26/11/2026

**Có checkpoint A mới:** xem [submission/CHECKPOINTS.md](submission/CHECKPOINTS.md)
và notebook pin SHA trong `submission/checkpoints/`. Hướng dẫn gói ban đầu bên
dưới dùng A3dd6b3a; bản A_STAGE1 e2c9ae5 là snapshot riêng của nhánh chưa merge.
Không coi nộp version mới là tự hủy/thay lượt đang scoring; kiểm tra quota team.

Mục tiêu: lấy một submission được Kaggle chấm thành công, rồi mới so Safe với
candidate A. Đây là hỗ trợ đóng gói cho phần C theo yêu cầu user, không ký G0/G1
thay C/A. Chưa upload/submit, chưa có điểm hoặc thứ hạng Kaggle của hai notebook.

## 1. File cần dùng và khác nhau thế nào

Chạy builder từ root để tạo một thư mục mới:

```powershell
.\.venv\Scripts\python.exe -m team_tools.build_kaggle_trial --output artifacts/kaggle-trial-user-01
```

Trong thư mục đó:

- `smart-buildings-safe.ipynb`: bản đầu tiên nên nộp. Official PIDWaterResetPolicy
  (pid_water), dùng để xác nhận toàn bộ workflow. Không phải Base cuối đã khóa.
- `smart-buildings-candidate-a.ipynb`: bản thứ hai, cùng PID-water nhưng zone logic
  của A. Candidate đã benchmark local, chưa được G1 signoff. Không sửa code A.
- `manifest.json`: HEAD nền, upstream SHA, hash original/embedded từng source,
  import adaptations và hash notebook; dùng xác định chính xác đã nộp bản nào.
- `LICENSE`, `NOTICE`: giữ nguồn official và attribution Google.
- `kaggle-trial-bundle.zip`: tiện gửi giữa ba thành viên; giải nén rồi chọn `.ipynb`
  để import. ZIP không phải file submission mà server yêu cầu.

Hai notebook đầy đủ, tự chứa PID/PID-plus và, với candidate, code A. Chỉ bỏ
import của các class đã được đặt trong cell trước; không đổi logic điều khiển.
Không cần upload repo, NPZ, model Ridge, dữ liệu generated/holdout, token hay .venv.
Notebook gọi inference server được Kaggle cấp; không tải code từ Internet khi chạy.

## 2. Nguồn và điều đã xác minh

- Official Data / How to Submit:
  https://www.kaggle.com/competitions/neurips-2026-smart-buildings/data
- Mẫu gốc Ayush Rai, TransferPolicy Notebook, version1, Apache-2.0:
  https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook
  Download được ngày26/11, SHA256 notebook gốc:
  `786545a08be78ce7e9f60110297fc345a91fe1a39c8eedd4058b5444913629c5`.
- Official starter kit Apache-2.0:
  https://github.com/smart-buildings-2026/starter-kit
  SHA `1fb75606d12e016463fbc63de704967c5b2bf9d5`.
- A: group policy tại numerical SHA `3dd6b3a`; Git delivery PR4/main `ed07917`.
  Builder ghi thêm HEAD và hash source thực đọc. Code A được ghi công cho A;
  không tự đoán A có dùng AI không.
- Codex/ChatGPT hỗ trợ đáng kể phần adapter, builder, tests và hướng dẫn này.
  Không phát minh PID/Ridge. Không gọi OpenAI API trong inference.
- Code-requirements đã đọc trên UI official: notebook CPU/GPU <=9h, Internet OFF.
  Chọn CPU, accelerator None vì policy này không dùng GPU.
- Notebook/Data page đã xem được khi chưa đăng nhập. Editor/Submit/account limits
  chưa kiểm chứng trong tài khoản user; tên menu có thể khác theo phiên bản UI.
- License input data trên trang Kaggle là CC BY-NC-SA4.0, khác license code
  starter-kit. Gói này không phân phối data/server của Kaggle.

## 3. Đăng nhập và vào đúng team

1. Mở https://www.kaggle.com/competitions/neurips-2026-smart-buildings .
2. Đăng nhập tài khoản nhóm đã thống nhất dùng. Nếu nhóm đã có team, kiểm tra
   trang Team/tên team của competition trước khi submit để tránh nộp nhầm team.
3. Nếu còn nút Join Competition, tự đọc Rules và chấp nhận nếu bạn đồng ý.
   Nếu được yêu cầu xác minh tài khoản/điện thoại, hoàn tất trên Kaggle.
4. Không chia sẻ password/API token với nhóm/chat. Luồng này không cần API key.

## 4. Tạo notebook Safe và gắn input

1. Mở mẫu TransferPolicy Notebook ở link trên. Sau đăng nhập, chọn **Copy & Edit**.
   Tạo tên dễ phân biệt, ví dụ `Team3 Safe PID-water 20261126`.
2. Trong editor, dùng **File -> Import Notebook** (hoặc nút Import/Upload notebook
   của phiên bản UI) và chọn `smart-buildings-safe.ipynb` trong gói đã giải nén.
   Nếu menu này không có, vào competition **Code -> New Notebook**, rồi tìm Import
   trong File hoặc menu notebook. Không chọn Upload Dataset để nộp notebook.
3. Nếu import mở một notebook mới, đặt lại tên và kiểm tra competition Input.
4. Ở sidebar **Input/Data**, phải có competition `neurips-2026-smart-buildings`.
   Nếu thiếu: **Add Input / Add Data -> Competitions**, tìm tên cuộc thi và Add.
   Dữ liệu competition chỉ truy cập được sau khi tài khoản đồng ý Rules.
5. Cell đầu dùng đúng đường dẫn mẫu chính thức:
   `/kaggle/input/competitions/neurips-2026-smart-buildings/`.
   Bên trong phải có `kaggle_evaluation/`. Nếu cell báo thiếu, kiểm tra Input và
   đường dẫn thực sidebar; không tự tạo thư mục rỗng để vượt assertion.
6. Trong **Settings/Session options**: language Python; accelerator None/CPU;
   **Internet OFF**. Metadata file đã ghi OFF, vẫn kiểm tra lại trên editor.
7. Giữ notebook **Private** khi thử; xác nhận privacy trước khi lưu/share.

## 5. Chạy, lưu version và submit

1. Không cần chạy full DEV-SMALL trong notebook. Cell cuối gọi:

   ```python
   smart_buildings_inference_server.SmartBuildingsInferenceServer(TransferPolicy).run(
       competition_data_folder=COMPETITION_DATA_FOLDER,
   )
   ```

   Đây là đường chạy của BTC: local notebook dùng public example; lúc submit
   Kaggle chạy lại trên hidden scenarios. Giữ cell này, không đổi sang evaluate.py.
2. Chọn **Save Version -> Save & Run All** để có version chạy từ đầu, tránh phụ
   thuộc biến còn sót trong session. Có thể Run All trước để debug, nhưng khi
   nộp vẫn chọn version đã Save & Run All thành công.
3. Chờ version kết thúc. Có thể mất nhiều phút; notebook mẫu gốc hiển thị khoảng
   12m47s trên public example, không phải cam kết thời gian cho policy của nhóm.
   Không bấm Run All lặp lại khi job vẫn chạy.
4. Kiểm tra status hoàn thành, không traceback; cell cuối đã chạy; có gateway /
   episode logs. Một reward in log public example chưa phải Public leaderboard score.
5. Mở version đã hoàn thành, chọn **Submit to Competition / Submit** theo UI.
   Chọn đúng Smart Buildings competition và đúng saved version. Nếu UI yêu cầu
   output/file, theo output chính thức của server và template; không tự tạo CSV
   từ reward local. Chưa xác minh output picker trong tài khoản user nên không
   đoán tên file bắt buộc.
6. Mô tả submission: `G0 trial - official pid_water; source manifest attached locally;
   no B04/B05; packaging AI-assisted; 2026-11-26`.
7. Xem **My Submissions/Submissions**; đợi trạng thái chấm xong. Chỉ ghi G0/Kaggle
   chấm thành công khi status và score thật xuất hiện. Ghi nguyên tên status UI;
   không gọi notebook chạy xong là submission Accepted.
8. Lưu notebook URL/version, submission timestamp, mô tả, status, score, runtime
   và lỗi nếu có. Giữ manifest của chính gói đã import. Chưa có score thì ghi
   PENDING/FAILED/NOT RUN; không điền 0 hoặc điểm DEV-SMALL thay thế.

## 6. Nộp candidate A sau khi Safe đã được chấm

Tạo notebook riêng `Team3 Candidate A 20261126`, import
`smart-buildings-candidate-a.ipynb`, lặp các bước trên. Giữ Safe/version cũ để
fallback và đối chiếu; không sửa notebook Safe thành A rồi mất dấu bản đã nộp.
Mô tả candidate: `trial A on official pid_water; B05 OFF; G1 not approved`.

Điểm local DEV-SMALL: Safe0.08769696; A0.05414362. A thắng3/thua2 case so vớiSafe.
Không dự đoán Public score/thứ hạng từ hai số này. So hai submission cùng điều
kiện, ghi kết quả thật. Chưa G1 signoff/copy-flag contract không được gọi candidate
là composer chính thức đã nghiệm thu; adapter standalone không sửa vấn đề đó.
Không tune liên tục theo leaderboard hoặc dùng hidden feedback như train data.

## 7. Lỗi thường gặp và cách xử lý

- **Copy & Edit/Submit bị mờ:** kiểm tra login, Join/Rules, verification, version
  chạy thành công, Internet OFF và quota mà account hiển thị. Không đoán quota.
- **Thiếu kaggle_evaluation/module:** attach competition input; giữ bootstrap và
  server cell. Không pip install ngẫu nhiên package cùng tên từ Internet.
- **Thiếu team hoặc smart_buildings.baselines:** đang dùng code rời từ repo.
  Import lại notebook tự chứa trong gói, không chỉ copy MemberAPolicy một mình.
- **Action sai shape/range/NaN:** giữ traceback và notebook version; đừng tự clip
  để che lỗi. Adapter fail rõ để tránh nộp âm thầm policy khác bản benchmark.
- **Version succeeded nhưng submission lỗi:** lưu cả notebook log và submission
  error. Hidden buildings có layout khác; local pass chưa chứng minh mọi building.
- **Timeout:** lấy runtime thật, xác định constructor hay get_action, rồi sửa
  có test. Không tự rút episode hoặc tự tính score thay cho Kaggle.
- **Có file scores/CSV local:** không dùng làm submission; cuộc thi chấm policy.
- **Gateway báo8641 trong public log mẫu:** khác count8640 local; mẫu official
  có hiện tượng này. Không sửa gateway/episode length hoặc suy điểm từ log đó.

## 8. Tiêu chí xong lần nộp thử

Có version notebook tái chạy được trên Kaggle + submission được chấm + score
thật + URL/version/time/manifest được lưu. Trước đó trạng thái chỉ là prepared
hoặc runtime verified, chưa đạt G0. Không tự thay status của nhóm trong repo.

Builder không upload/submit hoặc tự đồng ý Rules. Lần này người dùng làm các nút
trên Kaggle; C vẫn là owner duy trì submission theo phân công.

## 9. Kiểm tra local của gói này

`python -m pytest -q`:185 passed,34 subtests,15 dependency warnings,92.16s.
Sau thay đổi metadata provenance:6 packaging tests đạt lại; cùng6 tests đạt ở
cây source không có generated data, dùng installed environment sẵn có.
Actual exported policy/adapter cells được replay với hai building, mỗi policy288
observation liên tiếp/building: action khớp bit-exact; wall6.302s, processCPU6.375s.
Không simulator.step trong replay, không score, Policy superclass được stub.
Independent technical AI review không còn P1/P2; không phải human approval.
Chi tiết: `team/KAGGLE_TRIAL_CHECKS.json`. Person-hours chưa có worklog xác nhận.
