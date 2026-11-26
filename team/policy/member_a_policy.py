"""Policy thử nghiệm của Thành viên A.

Kế thừa base PID nhưng thay thế toàn bộ phần điều khiển van phòng
bằng module ZoneController độc lập của Thành viên A.
"""

from typing import Any
import numpy as np

from smart_buildings.baselines.pid_plus  import PIDWaterResetPolicy
from team.policy.zone_controller import ZoneController


class MemberAPolicy(PIDWaterResetPolicy):
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
    # Tắt hàm điều khiển van phòng mặc định của pid_plus (vốn bị gọi lặp theo số AHU)
    def _command_zones(
        self,
        continuous: np.ndarray,
        zones: list[tuple[str, int, dict[str, int]]],
        obs: np.ndarray,
        low: float,
        high: float,
    ) -> None:
        """Bỏ qua trong vòng lặp AHU để tránh gọi lặp K lần mỗi bước."""
        pass

    def get_action(self, obs: np.ndarray) -> dict[str, Any]:
        """Lấy action máy tổng từ base rồi gọi ZoneController đúng 1 lần mỗi bước."""
        action = super().get_action(obs)
        return self.zone_controller.adjust(obs, action)
