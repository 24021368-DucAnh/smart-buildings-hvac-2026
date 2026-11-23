"""Script chạy đo điểm đánh giá riêng cho Thành viên A.

Tự động đăng ký 'member_a' vào POLICY_MAP mà không làm bẩn file evaluate.py của BTC.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from smart_buildings.evaluate import POLICY_MAP, main
from team.policy.member_a_policy import MemberAPolicy

# Đăng ký policy của Thành viên A
POLICY_MAP["member_a"] = MemberAPolicy

if __name__ == "__main__":
    main()
