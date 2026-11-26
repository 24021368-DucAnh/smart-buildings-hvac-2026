# B03 — collector và dataset kiểm chứng (22/11/2026)

Goal: thu `(obs_t, action_t, obs_t+1)` thật, đúng đơn vị/thời gian, có schema,
snapshot, SHA, split theo building và báo cáo chất lượng để B04 sử dụng.
Spec: FINAL v2.1, 04_MEMBER_B B03 (22–26/11), data dictionary B01 và harness B02.

Thiết kế được triển khai theo yêu cầu hoàn thành B03 và các bước đã trao đổi:
collector Python tái dùng loader/metadata/policy/validator chính thức; NPZ theo
episode tránh lặp observation cho từng zone; JSON giữ mapping và provenance.
CSV phẳng theo zone sẽ nhân bản dữ liệu lớn, còn log tracker B02 không giữ đủ
observation/action; vì vậy chọn collector riêng, không viết lại evaluator.

## Ràng buộc và nghiệm thu

- Giữ nhánh feature hiện tại vì B01/B02 còn uncommitted; không sửa main/push/PR.
- `pid_water` provisional; không dùng/chờ Base cuối, không mở frozen holdout.
- Một worker, thread limits=1, timeout/episode=1800s, tổng budget=7200s.
- Smoke 288 bước không được đưa vào dataset trainable.
- Corpus tối thiểu: 3 train buildings, 2 validation buildings, 1 generated-dev;
  6 full episodes × 8640 bước, đủ 5 khí hậu. Đây là corpus ban đầu, không claim
  đã quét DEV-FULL/generated-dev toàn bộ hay đã chứng minh ML cải thiện control.
- `obs` dùng field names runtime; native được khôi phục từ đúng measurement key,
  không lấy latent simulator state làm feature. Metadata giữ room/VAV/AHU map.
- Capture raw validity trước carry-forward bằng wrapper trả nguyên response;
  không query sensor thêm lần nữa. Giữ mọi row, mask imputed/label không hợp lệ.
- Dataset lưu timestamp gốc, không tự gán UTC cho timestamp naive; bước 300s.
- Fail khi NaN/Inf, shape/dtype sai, timestamp trùng/lệch, episode thiếu, target
  sai đơn vị, SHA sai hoặc building xuất hiện ở nhiều split. Không âm thầm bỏ row.
- Lưu action variation; baseline logs không đủ để kết luận causal response.

## Task 1 — schema và validator

Files: `team_tools/dataset.py`, `configs/dataset_manifest.yaml`,
`tests/test_dataset.py`. Interfaces: `TransitionBuffer`, `validate_arrays`,
`load_plan`, `validate_corpus`. Test trước: aliasing, chronology, target Kelvin,
NaN, duplicate/missing/extra arrays, variable dimensions, split overlap/holdout.
- [x] Tests RED → implementation → GREEN, including corrupt arrays/checksums.

## Task 2 — collector thật

Files: `team_tools/collect_transitions.py`, `tests/test_collect_transitions.py`.
CLI parent chạy worker riêng từng episode, output unique, progress/checkpoint,
source/config snapshots, schema/NPZ/hash, CPU/runtime/status và dataset registry.
Worker dùng chính official pid_water, không ghi hidden state vào feature.
- [x] Test lỗi/partial/no-overwrite; guarded smoke thật 23/11 đủ 288 bước, 15 arrays khớp smoke cũ.
- [x] Thu đủ 6 full episodes; giữ nguyên run PAUSED/FAILED, reuse byte-identical 5 episode trong lượt cuối.

## Task 3 — nghiệm thu và giải thích

Files: `team/README.md`, `team/data_dictionary.md`, `team/B03_checks.json`,
`notebooks/B_research.ipynb`, `experiments/datasets.csv`.
- [x] Validate lại từ disk: exact corpus, hashes, step/zone counts, group split,
  missingness, action variation, feature/label separation, checksum snapshots.
- [x] Toàn repository pytest: 151 tests +29 subtests. Tám code cells notebook chạy tuần tự trong fresh project Python process; source/diff kiểm tra. Kernel Jupyter startup NOT VERIFIED (preflight bị chờ).
- [x] Báo cáo thực tế trong `team/B03_checks.json`, gồm nguồn gốc cũ/mới, lỗi đường dẫn, runtime, ΔT tails và NOT RUN.

Ruling: tài liệu gọn ở `team/`, ledger ở `artifacts/b03_progress.json`; không tạo
bộ tài liệu quản trị khác hoặc tự commit. Chỉ B01–B03 trong phạm vi phiên này.

## Tiếp tục 23/11 và quyết định thực nghiệm

Giả thuyết kỹ thuật: hardening nguồn gốc/validator giữ nguyên numerical data,
và có thể ghép lại corpus từ các episode full đã kiểm chứng mà không chạy lại
chúng hoặc nhận checkpoint dở dang làm dữ liệu hoàn tất. Smoke cũ là đối chứng
cùng SHA/scenario/policy/steps; so sánh cả 15 arrays, yêu cầu tất cả bằng nhau.
Test âm từ chối source/manifest/hash/audit sai, smoke, partial và worker pin chưa
kiểm tra đủ hai đầu. Kết quả: 54 group tests; toàn repo 148 tests và 29 subtests.

Thứ tự ít compute: kiểm tra source+artifact → unit tests → smoke 288 → đối chiếu
arrays → toàn bộ tests → reuse 3 episode full → thu 3 episode thiếu tuần tự →
validate exact corpus → chạy notebook. Tiêu chí corpus vẫn như đã khóa ở trên;
không đặt tiêu chí prediction/control sau khi nhìn dữ liệu. Không tăng số seed,
không tune policy, không train model trong B03. Nếu timeout/fail, giữ nguyên
artifact thất bại và training_ready=false; không điền bằng chứng hoặc điểm giả.

Run mới: `b03-corpus-20261123-01`; run cũ `b03-corpus-20261122-01` giữ nguyên.
Legacy reused episodes có manual producer audit trong lineage; new episodes có
scoped pin before/after. Không diễn giải hai loại evidence thành cùng một mức
chứng minh runtime. Partial Atlanta chạy lại từ đầu vì NPZ không lưu simulator
state. Chi phí collection mới và chi phí sản xuất episode reused báo riêng.


Nghiệm thu 23/11: `b03-corpus-20261123-02` SUCCEEDED_FULL/training_ready=true,
6 × 8640 = 51840 transitions, 3568320 zone-transition samples. Raw-invalid/mask,
nonfinite/duplicate/drop counts = 0. Lượt cuối 1786.31 s wall, 0.48329 CPU-core-h
collection mới; production CPU của 5 episode reused = 0.60576 core-h. Số này
không phải tổng CPU mọi lần thử. Full generated worker trần 3600 s sau smoke
82.13 s; batch trần 7200 s. Chưa train model hoặc mở holdout. B03 code notebook
đã chạy; chức năng khởi động kernel Jupyter vẫn là giới hạn môi trường.
