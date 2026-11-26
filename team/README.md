# Workspace nhóm — Smart Buildings HVAC 2026

## Nộp thử Kaggle

[Hướng dẫn từng bước và nguồn template](KAGGLE_TRIAL_GUIDE.md). Builder
`python -m team_tools.build_kaggle_trial --output artifacts/kaggle-trial-new-01`
tạo hai notebook tự chứa: Safe official PID-water và candidate A. Gói chuẩn bị
chưa phải submission được Kaggle chấm; giữ G0/G1 pending cho tới bằng chứng thật.

## Điểm bắt đầu và nguồn gốc

Đọc [PROJECT_KNOWLEDGE.md](PROJECT_KNOWLEDGE.md) để biết source URL/SHA/license,
phần AI hỗ trợ, Base kế thừa, ownership, thời gian đo được và các gate chưa duyệt.
Ngày 26/11 user đã cho phép merge phần B đạt kiểm chứng; các ghi chú no-push của
phiên trước là lịch sử, không phải G1 approval. Code nghiên cứu B04 không bật B05.
Điểm DEV-SMALL cuối cùng nằm trong `DEV_SMALL_RESULTS.json`; chỉ được có mean
khi đủ đúng năm case mỗi policy. Dữ liệu/model/raw receipts không đi kèm Git.

Cập nhật 26/11: đã kiểm chứng đủ **15/15 full cases DEV-SMALL** (5 khí hậu ×
3 policy × 8640 bước). Mean loss: `member_a=0.05414362`, `pid=0.06947283`,
`pid_water=0.08769696`; thấp hơn tốt hơn. A thắng PID-water ở 3/5 case nhưng
thua tại Denver/Phoenix. Xem `DEV_SMALL_RESULTS.json` và `B_DELIVERY_CHECKS.json`
cho số từng case, nguồn, AI, tests và runtime. Đây chưa phải G1 approval/Kaggle.

## Kiểm chứng main và B04 — 25/11/2026

Nền kiểm chứng main: `3dd6b3a`. Các lệnh bên dưới chạy từ root repository.
Environment/dataset phải được cài hoặc tạo lại theo hướng dẫn; không phụ thuộc
đường dẫn máy của người phát triển. Raw artifacts cũ được giữ riêng để đối chiếu.

- B01 runtime audit mới: `artifacts/B01-main-20261125/checks.json`.
- B03 validation mới: `artifacts/B03-main-validation.json`; nguồn corpus giữ SHA cũ,
  không đổi receipt lịch sử sang SHA mới. Official simulator/evaluator không đổi.
- Review hợp đồng A: `artifacts/main_compatibility.json`. Có write ownership đúng
  trong fixture, nhưng action bị sửa in-place; enable/disable composer chưa có.
- B04: `team_tools/forecast.py`, báo cáo nhỏ [`B04_checks.json`](B04_checks.json),
  model `artifacts/B04-20261125-01/ridge.npz`, bảng theo building/zone và plots cùng
  thư mục. Một lượt fixed-alpha; không tuning generated-dev, không mở holdout.
- Chuẩn bị và giới hạn thí nghiệm: [`B04_PLAN.md`](B04_PLAN.md).

PowerShell, từ checkout mới:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m team_tools.dataset data/generated/trajectories/b03-corpus-20261123-02
.\.venv\Scripts\python.exe -m team_tools.forecast data/generated/trajectories/b03-corpus-20261123-02 --output artifacts/B04-user-reproduce-01
```

Windows generated-dev cần bản sao đường dẫn portable; chạy các lệnh sau sau khi
job Base đã kết thúc (mỗi lần chọn tên output/run mới):

```powershell
.\.venv\Scripts\python.exe -m team_tools.prepare_scenarios --output artifacts/portable-generated-next --scenario building_0500/atlanta_4
.\.venv\Scripts\python.exe -m team_tools.run_batch --suite generated_dev --scenario building_0500/atlanta_4 --steps 288 --scenarios-dir artifacts/portable-generated-next --experiment-id generated-smoke-next --timeout-seconds 180
```

Smoke đường này đã chạy thật ngày 25/11; không phải full generated score.

Output phải là tên mới; lệnh cuối chạy lại fit offline, không chạy simulator.
MAE/RMSE dự báo được tính theo zone-transition; xem riêng từng building, không để
building nhiều zone che mất lỗi. Baseline persistence dự báo ΔT=0. Ridge tối thiểu
hóa `sum((y-Xw-b)^2) + alpha*sum(w^2)` sau khi fit mean/std chỉ trên train.
Ridge giảm MAE trên validation 5/7 nhưng tăng MAE generated 0500; không đủ bằng
chứng để bật Module B. Các B05–B09 vẫn nằm ở bước kế tiếp theo kế hoạch.

Đánh giá Base có giới hạn: `python -m team_tools.compare_bases` dùng runner B02
và wrapper A, smoke trước full, 1 worker, trần 2400 giây. Kết quả nằm trong
`artifacts/base_comparison.json` và `artifacts/benchmark_runs/`; hai kịch bản chẩn
đoán không đại diện DEV-SMALL/DEV-FULL hoặc điểm Kaggle. Xem báo cáo phiên trong
[`MAIN_B04_REVIEW.md`](MAIN_B04_REVIEW.md) trước khi quyết định Base.

Repo này kế thừa [starter kit chính thức](https://github.com/smart-buildings-2026/starter-kit) tại commit `1fb7560`. Giữ nguyên `smart_buildings/`, `pyproject.toml`, `LICENSE` và `NOTICE`; code nhóm được đặt trong `team/`.

## Thành viên và trách nhiệm

| Thành viên | Phạm vi chính | Action được phép chỉnh |
| --- | --- | --- |
| A | Tái hiện base policy; điều khiển từng VAV/zone | VAV continuous |
| B | Benchmark, thu thập dữ liệu, mô hình dự báo, module dự báo | AHU/HWS discrete |
| C | Tối ưu phần AHU/HWS, tích hợp policy, nộp Kaggle | AHU/HWS continuous |

Một policy chung với các module có thể bật/tắt độc lập; **không mặc định tất cả module đều cải thiện điểm**. Chỉ tích hợp những thay đổi đã được kiểm chứng.

## Cấu trúc tối giản

```text
smart-buildings-hvac-2026/
├── smart_buildings/   # Mã nguồn và các scenario chính thức (giữ nguyên)
├── team/             # Hợp đồng, policy A và bằng chứng/tài liệu B
├── team_tools/       # CLI audit, benchmark, dataset và forecast B
├── configs/          # Manifest benchmark và split dataset
├── tests/            # Unit/contract tests B
├── experiments/      # Registry nhỏ, không chứa dữ liệu mô phỏng
├── notebooks/        # Một notebook giải thích và tái hiện nhẹ
├── AGENTS.md         # Quy tắc làm việc và nguồn tri thức chung
├── README.md          # Hướng dẫn chính thức + đường dẫn đến team/
├── pyproject.toml     # Dependencies chính thức
└── LICENSE, NOTICE, ... # Các file gốc của starter kit
```

**Chỉ tạo thư mục khi có file thực tế.** Dự kiến: `team/policy/` (base và module A/B/C), `team/experiments/` (benchmark, dữ liệu, ML), `team/tests/` (kiểm tra) và `team/submission/` (đóng gói Kaggle). Không tạo sẵn các thư mục rỗng với `.gitkeep`.

## Bắt đầu trên máy cá nhân

```powershell
git clone https://github.com/24021368-DucAnh/smart-buildings-hvac-2026.git
cd smart-buildings-hvac-2026
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m smart_buildings.run_environment --building building_train_1 --weather fairbanks_1
```

Nếu đã có repo và môi trường Python như Member B thì **không cần clone/cài lại**; chỉ cập nhật `main` sau khi PR được merge.

## Git workflow

1. `main`: bản tích hợp ổn định; không phát triển tính năng trực tiếp trên `main`.
2. Mỗi nhiệm vụ làm trên một nhánh riêng, ví dụ `feature/a-zone`, `feature/b-data-ml`, `feature/c-plant`.
3. Tạo Pull Request vào `main`, mô tả thay đổi, cách kiểm tra và kết quả; người khác review trước khi merge.
4. Không sửa vùng action của thành viên khác nếu chưa thống nhất interface. Module dự kiến dùng `adjust(obs, action, ctx) -> dict`.
5. Mọi benchmark lưu commit SHA, scenario, config, thời điểm và metrics; so sánh cùng điều kiện chạy.

## Dữ liệu, bảo mật và nguồn gốc

- Không commit `.venv/`, secrets, API keys, `.env`, dữ liệu holdout hoặc output mô phỏng lớn.
- Artifact và dataset tạo ra có thể lưu ngoài Git; phải có hướng dẫn tạo lại và đường dẫn chia sẻ nội bộ.
- Repository hiện **Public**: chỉ push tài liệu và code được phép công khai theo quy định cuộc thi và môn học.
- Giữ nguyên license/notice của starter kit; ghi nguồn riêng cho base policy bên ngoài nếu sử dụng.
- `upstream` là repo chính thức, `origin` là repo nhóm. Chỉ push lên `origin`.

## Member B: data audit và benchmark

- B01 source audit và leakage notes: [`team/data_dictionary.md`](data_dictionary.md).
- B02 suites và episode lengths: [`configs/benchmark_manifest.yaml`](../configs/benchmark_manifest.yaml). `dev_small` là 5 cặp fixed phủ 5 khí hậu; `dev_full` đọc đúng 30 cặp từ `smart_buildings/training_set.yaml`. Generated-dev đã tạo 4 building từ seeds 500–504 (503 bị loại), holdout đã chuẩn bị 4 building từ 800–804 (800 bị loại); mỗi tập có 20 cặp với 5 weather strips tách biệt. Holdout có trạng thái `prepared_not_frozen`: chờ nhóm freeze và quyết định mở, chưa đánh giá/tune.
- `team_tools/run_batch.py` gọi evaluator chính thức theo từng cặp, workers = 1, output mới cho mỗi experiment ID tại `artifacts/benchmark_runs/<experiment_id>/`. `run.json` ghi SHA, config, số bước, runtime, trạng thái và mỗi scenario; log stdout/stderr nằm cùng thư mục. Không chạy lại với ID đã tồn tại.
- Theo COMMON_CONTRACT v2.1, công cụ B ở `team_tools/`, manifest ở `configs/`, kiểm tra ở `tests/`, registry ở `experiments/` và một notebook ở `notebooks/B_research.ipynb`. `team/` giữ tài liệu và kết quả audit nhỏ; cách này cụ thể hóa cấu trúc dự kiến ở trên và giữ source chính thức nguyên vẹn.
- Mỗi run mới lưu manifest, snapshot cấu hình, patch/file source chưa commit, Python/dependencies và hash lockfile. Các thread NumPy/BLAS/Numba được giới hạn 1; CPU-core-hours lấy từ CPU time của tiến trình evaluator, không suy từ wall time. Nếu tiến trình bị kill/timeout thì CPU chưa đo đủ để trống. Timeout/launch failure trả exit khác 0 và trạng thái terminal trong receipt/registry.

Setup giữ nguyên lockfile và chạy test nhanh từ repository root:

```powershell
uv sync --frozen --python 3.12
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Nếu cần chạy cả test của starter-kit: `uv pip install --python .venv/Scripts/python.exe pytest`, rồi `.\.venv\Scripts\python.exe -m pytest -q`. `pytest.ini` loại artifact/dataset khỏi việc tìm test, tránh thu nhầm source snapshot lịch sử.

PowerShell smoke (288 bước, chỉ kiểm tra wiring; không phải score):

```powershell
.\.venv\Scripts\python.exe -m team_tools.run_batch --suite dev_small --scenario building_train_1/fairbanks_1 --steps 288
```

Full run của DEV-SMALL (5 cặp × 8.640 bước):

```powershell
.\.venv\Scripts\python.exe -m team_tools.run_batch --suite dev_small --steps 8640
```

Chỉ sau khi generated-dev đã được tạo và khai báo đầy đủ trong manifest, chấm đúng run đó bằng:

```powershell
$experimentId = "paste-the-generated-dev-run-folder-name"
.\.venv\Scripts\python.exe -m team_tools.score_generated "artifacts/benchmark_runs/$experimentId/results" --manifest "artifacts/benchmark_runs/$experimentId/manifest.yaml" --suite generated_dev --policy pid_water
```

Generated scoring từ chối thừa/thiếu scenario (không phụ thuộc tiền tố tên building), policy lẫn, episode không đủ 8.640 bước, reward không hữu hạn, JSON field trùng hoặc manifest rỗng. Receipt phải có đúng SHA manifest và snapshot khớp config hash. Điểm là `mean(abs(total_reward / 8640))`, mỗi scenario có trọng số bằng nhau; chưa đủ suite thì không có điểm. `pid_water` hiện chỉ là policy provisional cho harness, chưa phải Base cuối của nhóm. Smoke và run một scenario không được ghi mean loss vào registry. Các receipt cũ thiếu snapshot không được nâng cấp bằng cách tự điền bằng chứng; giữ làm log lịch sử.

### Tái tạo generated data (không chạy mô phỏng)

Output nằm trong `data/generated/` được Git ignore. Dùng đúng batch seed/count để giữ nguyên vật liệu stratified; không tạo lại lên thư mục có dữ liệu cần giữ.

```powershell
.\.venv\Scripts\python.exe -m smart_buildings.run_floor_generator --start-seed 500 --count 5 --no-pdf --output-dir data/generated/generated_dev/buildings
.\.venv\Scripts\python.exe -m smart_buildings.run_scenario_generator --buildings data/generated/generated_dev/buildings/building_0500.yaml data/generated/generated_dev/buildings/building_0501.yaml data/generated/generated_dev/buildings/building_0502.yaml data/generated/generated_dev/buildings/building_0504.yaml --weathers atlanta_4 denver_1 fairbanks_3 phoenix_2 singapore_2 --output-dir data/generated/generated_dev/scenarios
```

Batch holdout dùng start seed 800, count 5, accepted 0801/0802/0803/0804 và weather atlanta_7/denver_4/fairbanks_6/phoenix_7/singapore_5; thay output thành `data/generated/frozen_holdout/`. Chỉ tái tạo khi phụ trách chuẩn bị holdout, không chạy `evaluate` trên tập đó. Manifest ghi đúng accepted/skipped seeds, đường dẫn output và hash generation receipt. Scenarios directory tự lấy theo suite, hoặc override bằng `--scenarios-dir`.

### Bằng chứng và giới hạn

- B01: [`data_dictionary_fields.csv`](data_dictionary_fields.csv) có 807 dòng; [`data_audit_checks.json`](data_audit_checks.json) ghi bốn transition audit thật. Lệnh audit: `.\.venv\Scripts\python.exe -m team_tools.audit_data --output-dir artifacts/data_audit_new`.
- B02: [`benchmark_checks.json`](benchmark_checks.json) ghi kết quả kiểm chứng, provenance và các mục NOT RUN. [`B_research.ipynb`](../notebooks/B_research.ipynb) giải thích đơn vị, chronology, fixture scoring và đọc registry; không chạy mô phỏng nặng.
- Bảng `baseline_returns.json` được tạo ở upstream ban đầu `3bb6c32`, không đổi sau cập nhật simulator. Run chẩn đoán cùng policy/scenario/8640 bước tại bản ban đầu khớp reference tuyệt đối; không dùng reference cũ làm mốc paired cho source hiện tại. Cần cùng SHA simulator và cùng suite khi so sánh cải tiến.

## B03 — thu thập transition và kiểm tra dataset

Plan/split được khóa trước khi thu trong [`configs/dataset_manifest.yaml`](../configs/dataset_manifest.yaml):
train = building_train_1/2/4, validation = building_train_5/7; generated-dev
building_0500 dùng để kiểm tra layout/weather mới và không fit model/scaler.
Corpus ban đầu có 6 cặp, phủ 5 khí hậu, mỗi cặp 8640 bước; các building generated-dev
còn lại không trở thành train, toàn bộ frozen holdout tiếp tục đóng.

Collector dùng loader, metadata, action validator, `pid_water` và `SimulationTracker`
chính thức (`capture_snapshots=False`). Wrapper chỉ đọc validity của response
hiện có trước carry-forward, trả nguyên response cho môi trường; không query sensor
thêm lần nữa. Native arrays được khôi phục từ normalized observation bằng đúng
measurement key; đối chiếu với raw response chỉ là assertion offline, không thêm
latent simulator state vào feature. Command và measured position là hai đại lượng
khác nhau; action variation không đủ để chứng minh causal response.

Audit pha sensor đã xác minh VAV latch nhiệt độ trước thermal solve: observation
trả về sau một step có thể phản ánh trạng thái vật lý trước solve. Nhãn B03 là
sensor delta theo API, không phải hidden-grid delta hay tác động tức thì của
action_t. Lịch sử action t-1 vẫn có sẵn để B04 thử feature lag một cách hợp lệ.
Chi tiết và số đo nằm trong Data Dictionary/B03 checks; không sửa simulator.

Mỗi episode gồm `arrays.npz`, `metadata.json`, `quality.json`, `episode.json` và
snapshot input config. Dữ liệu có T+1 observation và T action: transition i là
`observations[i], action[i], observations[i+1]`, nên không lặp observation hay lệch
timestep do ghép bảng. Metadata giữ scenario/building/split, field order, units,
normalizers, action bounds và room → VAV → AHU mapping. Timestamp naive của
simulator được giữ nguyên, không tự đổi thành UTC.

| Array | Vai trò |
| --- | --- |
| `observations` / `observations_native` | Vector policy-visible normalized / native khôi phục, shape `(T+1,D)` |
| `continuous_action`, `discrete_action` | Lệnh đã chọn ở t, dtype float32/int32; continuous nằm trong [-1,1], discrete 0/1 |
| `continuous_action_native` | Lệnh continuous đổi về range native của đúng actuator |
| `zone_temperature_K`, `delta_temperature_K` | Nhiệt độ zone và nhãn ΔT một bước theo Kelvin |
| `observation_valid`, `target_valid` | Validity trước imputation; target chỉ hợp lệ khi cả t và t+1 của zone hợp lệ |
| `timestamps`, `step_index`, `rewards`, `terminated`, `truncated` | Alignment/diagnostics; reward và future observation không dùng làm inference feature |

Không âm thầm bỏ hàng. Validator kiểm tra exact arrays, dtype/dimensions thay đổi
theo building, finite values, timestamp 300 giây, duplicate/index, Kelvin/ΔT,
action bounds, target mask, partial episodes, checksum và building split overlap.
Kiểm tra Kelvin dùng sanity range [150,400] K và assertion phép chuyển đổi; đó
không phải tiêu chí comfort. Counts imputation/masked labels và action variation
(range/std/switch count/on fraction) nằm trong quality report. B04 phải dùng mask
và ghi lại số mẫu bị loại khỏi fit, chỉ fit preprocessing trên train.

Chạy từ repository root; dataset ID/output không được trùng:

```powershell
.\.venv\Scripts\python.exe -m team_tools.collect_transitions --steps 288 --scenario building_train_1/fairbanks_1 --dataset-id b03-my-smoke
.\.venv\Scripts\python.exe -m team_tools.dataset data/generated/trajectories/b03-my-smoke --allow-smoke
.\.venv\Scripts\python.exe -m team_tools.collect_transitions --dataset-id b03-my-full --steps 8640
.\.venv\Scripts\python.exe -m team_tools.dataset data/generated/trajectories/b03-my-full
```

Smoke có `training_ready=false`; validator training mặc định từ chối smoke.
Full batch chạy tuần tự workers=1, thread limits=1, timeout 1800 giây/episode và
tổng 7200 giây; có thể cấu hình qua `--timeout-seconds`/`--max-wall-seconds`.
Tiến độ mỗi 288 bước; NPZ checkpoint mỗi 1440 bước, được thay atomic tại cùng
output owned bởi run. Episode thiếu/failed giữ để chẩn đoán, không được train.
`dataset.json` ghi SHA/config/source snapshot/environment/runtime/CPU và exact
scenario list; `schema.json` và `dataset_manifest.yaml` đi cùng artifact.
Dataset registry riêng ở [`experiments/datasets.csv`](../experiments/datasets.csv),
không trộn dataset smoke với control scores của registry B02.

### Tiếp tục sau khi tạm dừng

Checkpoint NPZ lưu các transition đã ghi, **không lưu toàn bộ trạng thái vật lý,
sensor và policy** để khôi phục simulator giữa chừng. Vì vậy episode bị dừng phải
chạy lại từ đầu. `--reuse-from` chỉ sao chép episode `SUCCEEDED_FULL` đủ 8640 bước
sau khi kiểm tra schema, manifest, SHA nguồn, môi trường Python/packages, checksum,
input snapshots và toàn bộ arrays. ID mới bảo vệ artifact cũ khỏi ghi đè.

Ba episode đầu của lượt `b03-corpus-20261122-01` được kiểm chứng trước khi áp dụng
review hardening ngày 23/11. Chúng giữ nguyên byte và receipt gốc trong lượt mới;
`lineage/` lưu snapshot nguồn cùng bản ghi kiểm chứng thủ công. Không gán ngược
nhãn worker pin cho dữ liệu cũ. Episode mới có pin source/config/weather/packages,
được đối chiếu trước và sau thu thập. Nếu dùng lại dữ liệu đã có pin, validator
kiểm tra pin của producer gốc, không thay bằng pin của lượt mới.

Lượt 23/11 đầu tiên thu xong Atlanta/Singapore rồi giữ trạng thái FAILED vì
generated-dev lỗi đường dẫn Windows ngay bước 0. Lượt mới dùng lại cả 5 episode
full. Các ID đã tồn tại; dùng ID mới nếu chủ động tái tạo, không cần chạy lại
chỉ để đọc kết quả:

```powershell
.\.venv\Scripts\python.exe -m team_tools.collect_transitions --dataset-id b03-corpus-20261123-02 --steps 8640 --reuse-from data/generated/trajectories/b03-corpus-20261123-01 --timeout-seconds 3600 --max-wall-seconds 7200
```

`cpu_core_hours` trong registry chỉ đếm worker thu **mới**, không tính lại CPU
của episode được sao chép. `reused_production_cpu_core_hours` nằm riêng trong
`dataset.json`. Cả hai đo phase collection bằng `time.process_time`, không tính
worker startup/import và parent validation. CPU của lượt bị ngắt trước đây không
có số đo cuối nên tổng chi phí mọi lần thử vẫn chưa biết đầy đủ.

### Đọc pipeline bằng một transition

1. `configs/dataset_manifest.yaml` chọn đúng building/weather/split trước khi thu;
   `team_tools/collect_transitions.py` nạp môi trường và policy chính thức.
2. `TransitionBuffer` trong `team_tools/dataset.py` giữ state hiện tại, action,
   state kế tiếp. `np.array(..., copy=True)` tránh việc simulator tái dùng bộ nhớ
   khiến dữ liệu lịch sử bị đổi theo state mới.
3. Worker xuất NPZ (mảng số), JSON (nghĩa/cấu trúc/nguồn gốc) và config snapshot;
   parent kiểm tra đủ corpus rồi mới đặt `training_ready=true`. Registry CSV là
   sổ tra cứu từng lượt, không thay thế artifact hoặc validator.
4. Notebook đọc artifact để minh họa X/y/mask. B04 sẽ thiết kế feature có schema
   cố định theo zone và train model; B03 chưa fit scaler hay model.

Ví dụ sensor normalized `-0.2`, mean `295 K`, std `5 K` cho native
`T = -0.2 * 5 + 295 = 294 K`. Nếu sensor kế tiếp là `294.1 K`, nhãn
`delta_temperature_K = 294.1 - 294 = 0.1 K`. Đây là **nhãn sensor kế tiếp**,
không bảo đảm action vừa chọn gây ra mức đổi đó, do pha latch và quán tính thiết bị.
Ở một transition có 39 zone, ta có 39 nhãn zone nhưng chỉ một vector action chung;
không gọi 39 nhãn đó là 39 episode độc lập.

Group split giữ cả building trong một tập: các dòng lân cận rất giống nhau nên
random row split dễ làm validation trông tốt giả tạo. `building_id` dùng để phân
tập/đọc báo cáo, không đưa vào model. Preprocessing chỉ fit trên train; validation
và generated-dev dùng để đánh giá, holdout vẫn đóng. `pid_water` đủ tạo dữ liệu
cho contract và baseline dự báo; khi A khóa Base cuối, đánh giá điều khiển phải
chạy trên cùng Base và cùng simulator SHA, không suy điểm từ corpus hiện tại.

`assert` là chốt dừng khi giả định sai; `dict` ánh xạ tên → giá trị; NumPy array
là bảng số có shape/dtype; mask là bảng True/False chọn nhãn dùng được. Ví dụ
Python chạy được và kết quả thật có sẵn trong `notebooks/B_research.ipynb`, mỗi
cell một nhiệm vụ nhỏ. Không cần chạy lại simulator để học các ví dụ này.

Artifact lớn nằm trong `data/generated/trajectories/` (Git ignore). Báo cáo nghiệm
thu nhỏ là [`B03_checks.json`](B03_checks.json); notebook B có phần đọc NPZ và
minh họa feature/label bằng dữ liệu thật. Vector D thay đổi giữa building: B04
cần xây fixed-schema per-zone features từ metadata, không stack nguyên vector D
của các layout khác nhau hoặc đưa ID building vào model.

Corpus này là dữ liệu quan sát từ policy provisional. Không có model được train
trong B03, chưa có prediction MAE hay kết luận cải thiện điều khiển. Full suite
DEV-SMALL có cả building train và validation, nên không gọi toàn bộ suite đó là
unseen. Generated-dev và holdout có vai trò riêng; holdout chưa được mở.

## Việc tiếp theo

- **A:** xác nhận base policy và hợp đồng module.
- **B:** B03 corpus ban đầu đã qua kiểm tra đầy đủ ngày 23/11: xem `B03_checks.json`. Việc tiếp theo là B04 persistence/Ridge với group split; kiểm tra các ΔT lớn và pha sensor trước khi kết luận về model. Giới hạn launch generated config Windows của B02 được ghi riêng trong `benchmark_checks.json`.
- **C:** thử một Kaggle Safe Submission sớm, sau đó tối ưu và tích hợp.


Generated configs do upstream generator chạy trên Windows có dấu `\` trong
Gin string: `\b`, `\f`, `\a` bị giải mã thành ký tự điều khiển. Collector B
chỉ đổi separator của bốn path macro (`weather_csv_path`, `floor_plan_filepath`,
`zone_map_filepath`, `metrics_path`) sang `/` trong bản nạp
`inputs/effective_config.gin`. Cấu hình gốc và assets không đổi. Receipt ghi cả
hash trước/sau cùng tên macro; validator tái tạo phép đổi để từ chối việc sửa
tham số vật lý/policy dưới danh nghĩa sửa đường dẫn. Source evaluator/generator
chính thức được giữ nguyên. Smoke generated 288 bước sau sửa mất 82.13 giây;
ước lượng tuyến tính khoảng 2464 giây chỉ dùng để chọn trần full episode 3600
giây, không gọi đó là runtime full đã đo. Tổng batch vẫn trần 7200 giây.


Giới hạn B02 được phát hiện khi thu B03: `run_batch`/official evaluator trực tiếp
vẫn đọc raw generated config trên Windows. Cơ chế portable ở trên hiện thuộc
**collector B03**; không suy rằng generated control suite B02 đã chạy thành công.
Trước control ablation cần chuẩn bị portable config hoặc áp dụng cùng cơ chế
có snapshot cho launch route đó. Official DEV-SMALL/DEV-FULL và scorer unit tests
không bị lỗi separator này. Generated full control suite vẫn là NOT RUN.


### Kết quả B03 đã kiểm chứng ngày 23/11/2026

Corpus `data/generated/trajectories/b03-corpus-20261123-02` có trạng thái
`SUCCEEDED_FULL`, `training_ready=true`: 6 episode × 8640 bước = **51840
transitions**, **3568320 zone-transition samples**. NPZ tổng khoảng 90.09 MiB.
Không có raw-invalid sensor, masked label, duplicate timestamp, nonfinite value
hoặc row bị bỏ trong corpus này. Manifest/split giữ nguyên: train 1/2/4,
validation 5/7, generated-dev 0500; holdout đóng.

Lượt cuối mất 1786.31 giây wall, collection mới 0.48329 CPU-core-hours;
0.60576 CPU-core-hours sản xuất 5 episode reused được báo riêng, không tính
lại vào lượt mới. Đây không phải tổng chi phí mọi lần thử: worker bị ngắt hôm
22/11 thiếu CPU cuối, và số đo không gồm startup/import/parent validation.
151 pytest tests +29 subtests qua, 15 warnings từ dependencies; compileall và
git diff --check qua. Notebook có output thật cho cả 8 code cells, chạy tuần tự
trong **fresh project Python process**. Kernel Jupyter preflight bị chờ nên
khởi động kernel vẫn **NOT VERIFIED**, không ghi nhận thành công giả.

`training_ready` xác nhận hợp đồng dữ liệu, không chứng minh predictor hay
controller tốt. Atlanta có ΔT tối thiểu -15.6831 K/5 phút; mọi row vẫn giữ nguyên,
chi tiết min/max/quantiles và ví dụ nằm trong `B03_checks.json`. B04 cần kiểm tra
đuôi phân phối, lag action và baseline persistence trước khi đánh giá Ridge.
Corpus ban đầu chỉ có 6 building/scenario; climate/layout shifts còn confounded.

Chỉ đọc và xác minh lại corpus đã có (không chạy mô phỏng):

```powershell
.\.venv\Scripts\python.exe -m team_tools.dataset data/generated/trajectories/b03-corpus-20261123-02
.\.venv\Scripts\python.exe -m pytest -q
```

MAE/RMSE, full control-suite score, paired final-Base ablation, B04 training và
holdout evaluation đều **NOT RUN** trong B03. Reward từng rollout chỉ là
diagnostic, không lấy trung bình sáu episode này để gọi là điểm generated suite.
