# Nguồn gốc, AI và tri thức làm việc chung

Ngày cập nhật: **26/11/2026**. Đây là tài liệu kỹ thuật và bàn giao; sinh viên tự
viết báo cáo học phần từ các bằng chứng đã đọc hiểu. Không dùng số liệu chưa chạy.

## 1. Nguồn ưu tiên và phiên bản

1. Quy định cuộc thi/giảng viên đã xác nhận; các điểm chưa xác nhận giữ UNVERIFIED.
2. Mã nguồn được pin và log thực chạy.
3. FINAL v2.1: 00_START_HERE, 01_MASTER_PLAN, 02_COMMON_CONTRACT,
   04_MEMBER_B, 06_TEMPLATES; các PDF do thành viên cung cấp, không vendoring vào Git.
4. Ý tưởng/tài liệu ngoài và AI, phải kiểm chứng với nguồn trên.

| Nguồn | Phiên bản/bằng chứng | Cách dùng |
|---|---|---|
| [Official starter kit](https://github.com/smart-buildings-2026/starter-kit) | `1fb75606d12e016463fbc63de704967c5b2bf9d5`; Apache-2.0, LICENSE/NOTICE giữ nguyên | Simulator, reward, evaluator, baselines, scenario generators và metadata APIs |
| [Nhóm](https://github.com/24021368-DucAnh/smart-buildings-hvac-2026) | nền kiểm chứng `3dd6b3a850354ea1eddfe58b9c8d2926f48bff31` | Bao gồm wrapper/policy zone A; Git author commit này là `Gnudxxx` |
| `pid_water` | `smart_buildings/baselines/pid_plus.py`, thuộc official revision trên | Nền kỹ thuật provisional/fallback; không tự coi là Base thắng mọi scenario |
| A / `member_a` | `team/policy/member_a_policy.py`, `zone_controller.py`, `team/evaluate_a.py`, tại `3dd6b3a` | Kế thừa `PIDWaterResetPolicy`, thay zone logic. B dùng để đánh giá, không nhận là code B viết |
| [Ridge, scikit-learn 1.6.1](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.Ridge.html) | objective chuẩn `||y-Xw||² + alpha||w||²`; dependency pin trong pyproject/uv.lock | Tài liệu thuật toán và implementation độc lập dùng làm đối chứng unit test |
| [NumPy 2.0 solve](https://numpy.org/doc/2.0/reference/generated/numpy.linalg.solve.html) | runtime pin NumPy 2.0.2 | Giải hệ tuyến tính cho Ridge; không tự nhận phát minh thuật toán |

Hai notebook công khai trong Master Plan (`jazivxt/smart-buildings-facilities-v17`,
`malyshevdanil/smart-buildings-probe-zone-pi-k10`) hiện **NOT VERIFIED** về source,
license/version và reproduction của nhóm. Chưa sao chép code/weights của chúng;
không nhận Public score tác giả công bố làm điểm của nhóm.

B01–B04 ban đầu được làm khi code B còn dirty/untracked: Git SHA trong receipt
là HEAD nền tại thời điểm chạy, không có nghĩa toàn bộ code B đã nằm trong commit
đó. B02/B03 giữ patch/archive/fingerprint; B04 giữ SHA256 `forecast.py` và model.
Khi đưa code B lên Git, giữ nguyên SHA lịch sử và dẫn thêm commit/PR bàn giao;
không thay mọi receipt cũ bằng SHA merge mới hoặc tự nhận code đã commit từ trước.

## 2. AI đã làm gì, ai chịu trách nhiệm

**Code B trong lần bàn giao này được tạo/sửa với hỗ trợ đáng kể của Codex/ChatGPT.**
AI đọc source và yêu cầu của Member B, đề xuất thiết kế, viết code/test, chạy công
cụ local, phân tích log và viết ghi chú giải thích. Không trình bày toàn bộ code
này là sinh viên tự viết độc lập hoặc thuật toán mới do nhóm phát minh.

Member B là owner công việc và người cần đọc hiểu, kiểm tra, chấp nhận kết quả;
owner không đồng nghĩa mỗi dòng là do người đó tự gõ. Các lượt review AI độc lập
là technical review, không thay chữ ký A/C hoặc approval của giảng viên.
Model ID/API run ID chính xác cho từng phiên lịch sử không được lưu trong repo;
không tự điền phiên bản AI hoặc prompt transcript không có bằng chứng.

Phân biệt ba khái niệm: **AI trợ lập trình** là Codex/ChatGPT; **Base điều khiển**
là các policy quy tắc/PID chính thức; **mô hình ML B04** là Ridge học từ transition.
Policy hiện tại không gọi ChatGPT/OpenAI API khi inference. Ridge là thuật toán
có sẵn được triển khai/kiểm chứng cho bài toán, không phải thuật toán mới do AI
hoặc nhóm phát minh. Đóng góp B nằm ở dữ liệu, features, kiểm chứng, evaluation và
module điều khiển chỉ khi có ablation chứng minh hữu ích.

| File/phần | Nguồn và mức kế thừa | Vai trò AI / kiểm chứng |
|---|---|---|
| `smart_buildings/`, `score_leaderboard.py`, dependencies, LICENSE/NOTICE | Official starter kit | Giữ nguyên; B đọc/dùng APIs, không viết lại evaluator/reward |
| `team/policy/*`, `team/evaluate_a.py`, MEMBER_A_LOG | Code A từ Git `3dd6b3a` | B audit và benchmark. Mức sử dụng AI của A chưa được A xác nhận |
| `team_tools/audit_data.py` | B mới, gọi loader/metadata chính thức, đối chiếu sensor/proto/normalizer | AI-assisted; unit tests + runtime audit hai building |
| `benchmark.py`, `run_batch.py`, `score_generated.py` | B mới bao quanh official evaluator/summary; công thức từ FINAL v2.1 | AI-assisted; tests âm membership/steps/NaN/duplicate, smoke/full thật |
| `dataset.py`, `collect_transitions.py` | B mới, dùng official env/policy/metadata, lưu NPZ và provenance | AI-assisted; synthetic contract tests + corpus thật; không lấy latent state làm feature |
| `forecast.py` | B mới triển khai Ridge chuẩn bằng NumPy, persistence và causal features | AI-assisted; đối chiếu sklearn trong test, train-only, model reload/reproduction |
| `forecast_diagnostics.py` | B mới tái dùng validator/causal features/frozen model B04; không fit/simulator | AI-assisted; residual/slices/coverage/past-lag/readback và artifact binding tests; nguồn phase là simulator/vav/environment official |
| `prepare_scenarios.py` | B adapter đường dẫn từ whitelist B03 | AI-assisted; giữ source, chỉ đổi đường dẫn và metrics destination, tests + generated smoke |
| `audit_main.py`, `compare_bases.py`, `assemble_benchmark.py` | B mới, gọi lại evaluator/wrapper A/receipt | AI-assisted; audit ownership, bounded jobs, strict assembler và provenance tests |
| `tests/*`, notebook B, manifests, registry, ghi chú B | B mới theo FINAL v2.1 và source APIs | AI-assisted; số thật lấy từ output; fixtures synthetic không phải score mô phỏng |
| C / submission | Chưa có bằng chứng đủ trong repo tại lần đọc 26/11 | Không đoán tác giả, AI usage, số giờ hoặc Kaggle Accepted của C |

## 3. Kiến trúc và hợp đồng dữ liệu

`Official env + metadata -> B01 audit -> B02 runner/summary -> B03 transitions ->
validator -> B04 per-zone causal features -> train-only Ridge -> MAE/RMSE`.

- Observation/action thay kích thước theo building; dùng field names/metadata.
- Zone temperature được giải chuẩn hóa về Kelvin. Heating/cooling setpoint sensor
  là raw Kelvin trong source đã kiểm tra. `-0.2 * 5 + 295 = 294 K ≈ 20.85°C`.
- Command được chọn khác measured actuator state. Sensor VAV có phase delay;
  target B04 là delta giữa hai observation liên tiếp, không phải latent temperature.
- Corpus: observations `(T+1,D)`, action/reward/target `T`; label `T[t+1]-T[t]`.
  Chỉ features hiện tại/quá khứ; rewards/future state/hidden IDs không vào infer.
- Train buildings 1/2/4; validation 5/7; generated 0500 evaluation-only. Không fit
  scaler/hệ số trên generated-dev; frozen holdout chưa mở.
- B04 có 16 features/zone, Ridge alpha=1 cố định, persistence delta=0; model offline.
  Validation MAE giảm nhưng generated-dev MAE tăng. **B05 chưa bật.**
- B01 dictionary 807 dòng đại diện hai building; không phải toàn bộ khả năng vật
  lý đã được chứng minh. Giữ delta tail lớn để điều tra, không âm thầm clipping.

## 4. Thời gian và trạng thái bằng chứng

| Giai đoạn | Thời điểm bằng chứng | Nguồn thời gian/status |
|---|---|---|
| B01/B02 audit/harness | 20–21/11/2026 | Small checks + registry; log run có wall/CPU khi đo được |
| B03 collector/corpus | 22–23/11/2026 | dataset.json/episode.json, hashes, lineage, registry datasets |
| B04 + main compatibility | 25/11/2026 | B04_checks, model hash, metrics, tests và notebook-cell log |
| Hai case Base × ba policy | 25–26/11/2026 | 6 full runs; A/Phoenix bổ sung 468.160s wall, 0.124722 CPU-core-hours |
| Hoàn thiện DEV-SMALL / delivery | 26/11/2026 | Đủ 15/15 full cases, strict assembly exit 0; xem DEV_SMALL_RESULTS/B_DELIVERY_CHECKS |

UTC/ISO timestamps trong registry là thời gian thực của công cụ; diễn giải ngày
cho nhóm theo Asia/Saigon. Wall-clock là thời gian chờ hoàn tất, CPU-core-hours
lấy từ process CPU khi đo được. Timeout/interruption không có CPU đầy đủ thì
để trống/null. **Person-hours của B/A/C chưa có worklog xác nhận, không suy đoán.**
Không cộng CPU-hours với person-hours; không suy giờ làm từ số commit.

Run bị ngắt/timeout được giữ nguyên, không đổi thành thành công. Public exports
chỉ chuẩn hóa/redact đường dẫn máy; số, timestamps, trạng thái và hash gốc giữ
nguyên. Raw receipts/logs/NPZ/model lớn ở `artifacts/` hoặc `data/generated/`,
không có trong Git. URI trong public registry là logical relative reference;
không có nghĩa artifact đã được upload hoặc teammate đã tải được.

## 5. Scoring, provenance và nghiệm thu

`loss_s = abs(total_reward_s / 8640)`, `mean_loss = sum(loss_s)/N`, mỗi scenario
trọng số bằng nhau. Thấp hơn tốt hơn. Smoke 288 không phải score. Hai-case mean
không phải DEV-SMALL; DEV-SMALL không phải Kaggle score.

Assembler xác minh exact membership, policy, 8640 steps, finite reward, duplicate
JSON/scenario, SHA/config/runtime environment, canonical official assets, và source
archive không sửa numerical code. Nó không tạo receipt producer giả cho run cũ.
Hash summary của legacy run chỉ là hash quan sát khi assembly; run mới có producer
summary binding và before/after pin cho code + actual scenario/weather inputs.
Before/after pin không được gọi là giám sát liên tục mọi bước.

Dataset reuse mới phải so numerical pin của producer leaf gốc qua lineage với
current inputs. Với legacy, cần supplemental audit thật đã bind archive/episode;
thiếu thì từ chối reuse mới, không tự bịa audit. Đọc/validate corpus lịch sử vẫn
giữ nguyên mức bằng chứng lịch sử, không âm thầm sửa JSON/NPZ cũ.

## 6. Quyết định và các phần chưa hoàn tất

- G0/Kaggle Accepted: chưa có bằng chứng C xác nhận trong repo.
- G1: PREPARED_FOR_HUMAN_REVIEW, chưa APPROVED. Official pid_water là nền kỹ thuật
  provisional/fallback; member_a là candidate. Chưa có base_lock/signoff A/C đủ.
- A cần no-input-mutation và enabled/disabled identity trước composition. B chỉ
  ghi nhận phát hiện, không tự sửa policy A hoặc nhận phần đó là B đã hoàn thành.
- C sở hữu submission/composer/plant optimization. Không nhắn/submit thay khi
  chưa được giao. User đã cho phép merge phần B đạt kiểm chứng ngày 26/11; điều
  này không phải Kaggle authorization hoặc G1 approval.
- DEV-FULL 30, full generated-dev 20, frozen holdout, B05/control gain và online
  B06 chưa chạy. Tối ưu theo evidence và paired ablation, không bảo đảm top điểm.
- Suite ngày 26/11 đã VERIFIED_FULL_SUITE_ASSEMBLY trong `DEV_SMALL_RESULTS.json`.
  A có mean thấp nhất nhưng còn regression Denver/Phoenix; không chọn theo mean
  đơn lẻ hoặc hardcode policy theo building/weather ID.

## 7. Cách tiếp tục và cập nhật tri thức

Đọc README, file này, kế hoạch B và small checks. Xác minh Git status/HEAD trước
thay đổi. Mỗi task cập nhật source/revision/AI role, lệnh và exit code thực, output
status, wall/CPU scope, hạn chế và next step. Khi merge, kiểm tra staged files
không chứa machine paths/data/binaries; chạy test ở clone không có generated data.
Không biến technical AI review thành chữ ký người. Giữ Safe và snapshot trước.

Notebook B và MAIN_B04_REVIEW là ghi chú để hiểu/tái hiện, không phải báo cáo học
phần do sinh viên tự viết. Mỗi thành viên phải tự giải thích feature, split, loss,
nguồn code, đóng góp mới và kết quả thất bại khi vấn đáp.

## 8. B01–B09 theo FINAL v2.1: đã đến đâu, điều kiện bước tiếp

Nguồn lịch: `04_MEMBER_B.pdf`, mục task-by-task; không đổi deadline vì làm sớm.

| Task / lịch kế hoạch | Trạng thái kiểm chứng và việc tiếp theo |
|---|---|
| B01 / 19–20/11 | Audit/mapping/units/chronology usable; 807 dòng đại diện hai building. Chưa xác minh vật lý mọi sensor và delta tail; không ghi hoàn tất tuyệt đối. |
| B02 / 20–22/11 | Runner/scorer/manifest/registry usable; smoke, full và DEV-SMALL 15 cases thật; generated-dev full20 chưa chạy; holdout prepared_not_frozen, chưa đánh giá. |
| B03 / 22–26/11 | Corpus thật 6 episodes đã validate lại: 51,840 transitions. Policy thu là official pid_water provisional, không relabel thành Base cuối. |
| B04 / 27–29/11 | Đã làm sớm fixed Ridge/persistence offline; MAE/RMSE per-building/zone, plots/model hash trong B04_checks và artifacts. Validation tốt hơn, generated MAE xấu hơn; cần residual/sensor-phase/action-diversity audit trước control. |
| B05 / 29/11–02/12 | NOT IMPLEMENTED. Cần locked common base, enable_b, flag-off identity, copy action, discrete AHU/HWS-only, fallback và paired BASE/BASE+B1 full runs. Predictor một bước dưới policy cũ chưa chứng minh causal response cho pre-start. |
| B06 / 01–04/12 | OPTIONAL, NOT IMPLEMENTED. Chỉ thử bounded online calibration từ transition đã quan sát, reset state theo episode và ablation; tắt nếu yếu/chậm. |
| B07 / 03–05/12 | Chưa nghiệm thu control gain/G2. So cùng Base/suite/source, paired delta, mean/worst/win-loss, comfort/energy/carbon và runtime; không suy gain từ MAE. |
| B08 / 06–08/12 | Chưa thực hiện G3/holdout. Reproduce ledger và candidate composer trước; holdout chỉ mở một lần khi nhóm quyết định, không dùng tune. |
| B09 / 09–11/12 | Notebook/source/AI/time notes hỗ trợ học và vấn đáp; sinh viên tự viết báo cáo và giải thích. Chưa có báo cáo học phần tự viết hoặc nghiệm thu vấn đáp. |

Ưu tiên tiếp: A sửa copy/flag contract; C bổ sung Safe/G0 và composition evidence;
B phân tích residual validation và action coverage với dữ liệu sẵn có trước khi
đề xuất thêm compute. Không mở B05/B06 chỉ vì B02 đã có điểm.

## Delivery evidence — 26/11/2026

Latest suite: `DEV_SMALL_RESULTS.json`; code/test/time/AI evidence: `B_DELIVERY_CHECKS.json`.
Suite status: VERIFIED_FULL_SUITE_ASSEMBLY. 179 passed, 15 warnings, 34 subtests passed in 87.10s (0:01:27). G1 remains NOT APPROVED. Git delivery references belong to actual commit/PR history; do not fabricate future SHA.

## Chuẩn bị nộp thử theo yêu cầu user — 26/11/2026

B01–B04 đã merge PR4, main `ed0791728fbfbccd07bf03c6509fb7f3c7306562`.
User tiếp tục yêu cầu gói đầy đủ và hướng dẫn tự nộp. Đã chuẩn bị builder
`team_tools/build_kaggle_trial.py` và `KAGGLE_TRIAL_GUIDE.md` để hỗ trợ C; không
upload, tự đồng ý Rules, submit hoặc ký G0/G1 thay nhóm.

Nguồn handshake thật: Ayush Rai, TransferPolicy Notebook v1 (Apache-2.0),
https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook; Data page yêu cầu
subclass server.Policy và chạy server.run, khác CLI evaluate.py local.
Notebook gói embed official PID/PID-plus và candidate A với đúng source hashes,
chỉ bỏ imports tới các class đã định nghĩa trước; wrapper do AI-assisted B viết
kiểm tra action mà không clip/đổi điều khiển. Không đưa Ridge vào policy.
Kaggle data/server không vendoring; license input Kaggle riêng với code Apache.

Replay actual exported cells trên288 observation liên tiếp ×2building ×2policy
khớp BIT_EXACT với code gốc. Đây là replay từ corpus có sẵn, không simulator run
hoặc control score; base class server được stub local. Bootstrap/server/Kaggle
hidden runtime, notebook saved version và Accepted/score vẫn NOT RUN.
Guide nêu rõ UI editor/Submit chưa xem trong tài khoản user; không đoán tên file
output hoặc quota. C tiếp tục owner submission; AI hỗ trợ packaging/tests/guide,
không tự nhận sáng tạo PID hoặc đã đạt thứ hạng nào.

## B04 frozen-model diagnosis — 26/11/2026

Task tiếp theo được user giao khi Safe đang scoring: `B04_DIAGNOSTICS.md/json`
và CLI `team_tools.forecast_diagnostics.py`. Không đổi model/features/normalizer,
không collect/fit/holdout hay can thiệp notebook đang nộp. Reproduce đủ12metric
building×model cũ trong1e-10; input/source hashes kiểm tra trước/sau, no dropped rows.
Giữ ba run diagnostic raw riêng; tổng processCPU40.546875s, không phải person-hours.
Person-hours chưa ghi nhận; tests/previous training/Kaggle không cộng vào số này.

Generated0500 Ridge MAE kém111/120zone; vùng abs(delta)<=0.1K gồm634,143mẫu:
persistenceMAE0.011013 vs Ridge0.132188K. Ridge tốt hơn với delta>1K, giải thích
tradeoff RMSE/MAE về mặt số học. Đây là retrospective label slices, không được
dùng delta tương lai để chọn model/fallback lúc inference. Generated đã xem là
development evidence, không còn là final held-out acceptance cho nghiên cứu mới.

Coverage generated có114/120 reheat channel hằng. Pearson lag chỉ mô tả closed-loop
observations, không causal effect. Reheat readback[t+1] khớp command[t]100%; damper
khớp max(command_native,0.1)100% **trong tolerance1e-5**, không bit-exact/thermal
response. Default floor lấy từ official VAV source, không fit từ generated data.
Large sensor jumps còn tồn tại; B01 physical plausibility chưa đóng. Quyết định
giữ Ridge offline/B05off, validation-led next design; chưa thử model/control mới.

User screenshot trong chat26/11 cho thấy team có TransferPolicy trước đó Succeeded,
PublicScore0.41179; bản SafePID-water Version2 vẫn Notebook Running ở thời điểm
ảnh. Đây là USER_PROVIDED_UI_EVIDENCE, chưa có URL/version-code/runtime độc lập
để lưu ledger đầy đủ. Không gán0.41179 cho SafePID-water/A hoặc tự ký G0/G1;
nhận định cũ “chưa thấy bằng chứng submission nào” đã được bổ sung bằng ảnh này.
