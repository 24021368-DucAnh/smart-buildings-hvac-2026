# Checkpoint nộp thử của nhóm — 26/11/2026

**Candidate đề nghị nộp tiếp: `20261126-a-stage1-e2c9ae5`.**
Trạng thái PROVISIONAL_NEXT_SUBMISSION_CANDIDATE sau kiểm chứng local;
chưa có score Kaggle, chưa phải Base/G1/composer cuối.

- [Notebook cố định để tải và import](checkpoints/20261126-a-stage1-e2c9ae5.ipynb).
- [Nguồn, hash và kết quả chi tiết](checkpoints/20261126-a-stage1-e2c9ae5.json).
- Mỗi source mới tạo ID mới, không ghi đè checkpoint cũ. Notebook code83KB giữ
  trong Git để A/C lấy đúng artifact. Không chứa data/model/raw logs. LF cố định
  bằng .gitattributes; license/source nằm trong metadata.

## Checkpoint chứa gì

Core nền main `6fb101e6932ba4c106c8d0d289ac8fe55a29abef`; packaging commit
`0f6d5eb` (full SHA trong JSON). A từ commit bất biến
`e2c9ae5ae73917d55e37964726393e22ceb8e040` trên `feature/a-zone`.

- **A:** ba commit chưa merge: van gió sưởi hai nấc, PI/anti-windup, comfort_soon
  preconditioning, một ZoneController call/bước. Git authorBenn326; không suy
  AI usage/person-hours. Không nhận là code B viết.
- **B:** harness/kiểm chứng/packaging. B04/Ridge offline, B05/B06 OFF.
- **C:** chưa thấy implementation trong các heads/open PR của repo nhìn được;
  không kết luận C chưa làm gì ngoài Git. TransferPolicy0.41179 từ ảnh user chưa
  có source/version/runtime độc lập để đưa vào checkpoint như code C.
- Stale chore branches là setup/layout cũ, lịch sử riêng không chung merge-base
  với main; không merge chúng để “lấy toàn bộ cập nhật”.

**Main runtime chưa tự đổi sang A Stage1.** Đây là snapshot A mới+officialPID-water.
`team.evaluate_a` trên main vẫn dùng A cũ; chỉ kéo main và chạy lệnh đó không tái
hiện controller trong checkpoint. Không sửa numerical files của A để đóng gói.

## Kết quả đã tự chạy lại

Cùng official simulator/config,8640bước/case,1worker/thread. Loss thấp hơn tốt hơn,
loss=abs(total_reward/8640). Hai case chẩn đoán không phải suite score/Kaggle.

| Case | A cũ3dd6b3a loss | A Stage1e2c9ae5 loss | Reward A Stage1 |
|---|---:|---:|---:|
| building_train_1/fairbanks_1 | 0.14705493 | **0.09816342** | -848.13192690 |
| building_train_4/phoenix_8 | 0.03108700 | **0.02850137** | -246.25184787 |

Đạt tiêu chí đặt trước: không kém A cũ cả hai case và tốt hơn ít nhất một; không
tuning sau khi xem kết quả. Cold reward khớp log A khi làm tròn. JSON giữ producer
summary/receipt hashes. Smoketest288bước thành công38.457s, không phải score.
Hai fullrun479.568s và499.359s; driver1020.169s trong budget1500s.
Successful evaluatorCPU tổng0.271506core-hours, đủ profiler receipts; không cộng
replay/tests/human time/Kaggle. Preflight đầu ID quá64ký tự bị từ chối trước khi
evaluator khởi chạy; log lỗi giữ riêng, không gọi đó là timeout của policy.

Replay actual notebook288observation×2building×2policy khớp bit-exact với A Git
blobs import độc lập; đúng1adjust/action và fresh-instance state isolation.
Kaggle Policy base được stub local; actual server/hidden runtime NOT RUN.
Các code cells của checkpoint cuối giống hệt bản replay; chỉ thêm thông tin release.

## Không so nhầm hai tập điểm

A cũ3dd6b3a đã được B kiểm chứng DEV-SMALL5building khác nhau: mean0.05414362098,
PID-water0.08769695526. Đây là fallback có bằng chứng rộng hơn, file cũ giữ riêng.
Log A mới ghi mean0.05044 trên5weather strips **của building_train_1**, chưa có raw
receipts trong Git nên chỉ là REPORTED_BY_A. Không so hai mean khác scenario sets
để nhận “best”. Checkpoint là candidate có lý do để thử, chưa chứng minh tốt nhất
trên mọi building/generated/hidden test và không dự đoán thứ hạng.

## Nộp checkpoint

1. Tải notebook đầu trang, tạo notebook Kaggle riêng tên
   `Team3 Checkpoint A Stage1 e2c9ae5`; giữ Safe đang scoring.
2. Import file, gắn official competition Input, CPU/acceleratorNone, InternetOFF;
   giữ source/Policy/server cells. SaveVersion->Save&RunAll.
3. Saved version thành công thì submit đúng version nếu quota team còn và Kaggle
   cho phép. Mô tả: `checkpoint 20261126-A-stage1-e2c9ae5; B05 OFF; experimental`.
4. Lưu URL/version/time/status/PublicScore thật. Chưa có score thì pending/NOT RUN;
   không điền điểm local. Nộp version khác là attempt mới, không bảo đảm hủy/thay
   attempt đang chấm hoặc giúp nhanh hơn. Không gửi lặp cùng file vì chờ lâu.

Competition chạy lại policy trong hidden simulator; không chỉ đọc CSV dự đoán.
Tác nhân không đăng nhập/upload/submit hoặc tự đồng ý Rules trong bước này.

## Tái tạo và nguồn

`--policy-ref` yêu cầu full40SHA đã fetch local; output phải tên mới:

```powershell
.\.venv\Scripts\python.exe -m team_tools.build_kaggle_trial `
  --policy-ref e2c9ae5ae73917d55e37964726393e22ceb8e040 `
  --output artifacts/checkpoint-rebuild-new-01
```

HEAD khác có metadata/whole-file hash khác; so individual source hashes/code cells.
Muốn đúng artifact đã chốt thì tải notebook cố định từ Git tag/checkpoint. Tests
kiểm tra file/embedded/original hashes, reconstruct import lines, finite scores và
scope chẩn đoán, không cần data/network. Full tests/runtime proof ghi trong JSON.

A vẫn mutate input action, thiếu shared enable/disable identity; inherited reset()
không clear zone PI trên instance cũ. Fresh constructor isolation đã kiểm tra,
không gọi reset() đã đạt. Official template dùng constructor theo scenario;
standalone snapshot không phải composer G1 nghiệm thu. C tiếp tục owner submission.

Official Apache-2.0:
https://github.com/smart-buildings-2026/starter-kit @1fb75606d12e016463fbc63de704967c5b2bf9d5,
LICENSE/NOTICE giữ nguyên. Source content main/A branch không đổi simulator/reward/
evaluator/dependencies. Kaggle handshake từ Ayush Rai TransferPolicy Notebook v1,
Apache-2.0: https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook.
Codex/ChatGPT hỗ trợ B packaging/tests/verification/notes; không nhận PID/PI là
thuật toán mới, không đoán AI usage của teammate, không bịa person-hours/G0/G1.
