"""Policy thử nghiệm của Thành viên A.

Kế thừa base PID nhưng thay thế toàn bộ phần điều khiển van phòng
bằng module ZoneController độc lập của Thành viên A.
"""

from typing import Any
import numpy as np

from smart_buildings.baselines.pid import PIDPolicy
from team.policy.zone_controller import ZoneController


class MemberAPolicy(PIDPolicy):
    """Policy kết hợp: Máy tổng dùng base PID, Từng phòng dùng ZoneController của A."""

    name = "member_a"

    def __init__(
        self,
        building_meta_data: Any,
        action_spec: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(building_meta_data, action_spec, **kwargs)
        # Khởi tạo module điều khiển phòng độc lập của A
        self.zone_controller = ZoneController(building_meta_data)

    def _command_zones(
        self,
        continuous: np.ndarray,
        zones: list[tuple[str, int, dict[str, int]]],
        obs: np.ndarray,
        low: float,
        high: float,
    ) -> None:
        """Chuyển giao quyền điều khiển van phòng cho ZoneController của A."""
        # Đóng gói thành action dict theo chuẩn hợp đồng
        action = {
            "continuous_action": continuous,
            "discrete_action": np.zeros(self.n_discrete, dtype=np.int32),
        }
        # Gọi module của A xử lý
        self.zone_controller.adjust(obs, action)
