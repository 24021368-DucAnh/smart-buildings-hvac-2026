# Workspace nhóm — Smart Buildings HVAC 2026

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
├── team/
│   └── README.md      # Điểm bắt đầu cho ba thành viên
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

## Việc tiếp theo

- **A:** xác nhận base policy và hợp đồng module.
- **B:** hoàn thiện B01 Data Dictionary rồi B02 benchmark; sau đó mới thu thập trajectory và train ML.
- **C:** thử một Kaggle Safe Submission sớm, sau đó tối ưu và tích hợp.
