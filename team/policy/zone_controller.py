"""Module điều khiển cấp phòng (Zone & VAV Continuous Controller) — Thành viên A.

Tuân thủ hợp đồng giao tiếp của nhóm:
    adjust(obs, action, ctx) -> dict
Chỉ can thiệp vào các chỉ số van phòng (damper và reheat valve).
Tuyệt đối không can thiệp vào discrete action hoặc các thiết bị cấp tổng (AHU/HWS).
"""

from collections.abc import Mapping
import re
from typing import Any

import numpy as np


class ZoneController:
    """Bộ điều khiển vi mô cho từng phòng (Zone/VAV)."""

    def __init__(
        self,
        building_meta_data: Mapping[str, Any],
        zone_damper_full_k: float = 2.0, 
        zone_reheat_full_k: float = 2.0,
    ) -> None:
        """Khởi tạo một lần cho mỗi tòa nhà.
        
        Args:
            building_meta_data: Metadata của tòa nhà nhận từ môi trường.
            zone_damper_full_k: Độ lệch nhiệt độ (Kelvin) để van gió mở 100%.
        """
        self.metadata = building_meta_data
        self.zone_damper_full_k = zone_damper_full_k
        self.zone_reheat_full_k = zone_reheat_full_k

        # 1. Cửa sổ nhiệt độ tiện nghi và tiết kiệm
        self.comfort_temp_window = building_meta_data["comfort_temp_window"]
        self.eco_temp_window = building_meta_data["eco_temp_window"]
        self.morning_start_hour = building_meta_data["morning_start_hour"]
        self.evening_start_hour = building_meta_data["evening_start_hour"]

        # 2. Thông tin giải chuẩn hóa nhiệt độ phòng
        norm_meta = building_meta_data["observation_normalization_metadata"]
        self.temp_mean = norm_meta["zone_air_temperature_sensor"]["sample_mean"]
        self.temp_std = norm_meta["zone_air_temperature_sensor"]["sample_std"]

        # 3. Chỉ số thời gian (giờ trong ngày, ngày trong tuần)
        field_names = building_meta_data["observation_field_names"]
        self.hod_sin_idx = field_names.index("hod_sin_000")
        self.hod_cos_idx = field_names.index("hod_cos_000")
        self.dow_sin_idx = field_names.index("dow_sin_000")
        self.dow_cos_idx = field_names.index("dow_cos_000")

        # 4. Ánh xạ từng phòng: (tên_vav, chỉ_số_obs, chỉ_số_damper, chỉ_số_reheat)
        self.zones: list[tuple[str, int, int | None, int | None]] = []
        zone_action_indices = building_meta_data["zone_action_indices"]
        zone_temp_field_index = {
            name: i
            for i, name in enumerate(field_names)
            if "zone_air_temperature" in name
        }

        for vav_id, actions in zone_action_indices.items():
            temp_field = f"{vav_id}_zone_air_temperature_sensor"
            if temp_field in zone_temp_field_index:
                obs_idx = zone_temp_field_index[temp_field]
                damper_idx = actions.get("supply_air_damper_percentage_command")
                reheat_idx = actions.get("reheat_valve_percentage_command")
                self.zones.append((vav_id, obs_idx, damper_idx, reheat_idx))

    def _denormalize_temp(self, normalized_val: float) -> float:
        """Đưa giá trị nhiệt độ quan sát về độ Kelvin thực tế."""
        return normalized_val * self.temp_std + self.temp_mean

    def _get_target_band(self, obs: np.ndarray) -> tuple[float, float]:
        """Xác định ngưỡng nhiệt độ [low, high] dựa vào giờ làm việc hay giờ nghỉ."""
        angle_h = np.arctan2(obs[self.hod_sin_idx], obs[self.hod_cos_idx])
        if angle_h < 0:
            angle_h += 2 * np.pi
        hour = int(np.floor(24 * angle_h / (2 * np.pi)))

        angle_d = np.arctan2(obs[self.dow_sin_idx], obs[self.dow_cos_idx])
        if angle_d < 0:
            angle_d += 2 * np.pi
        day = int(np.floor(7 * angle_d / (2 * np.pi)))

        is_weekday = day < 5
        is_work_hour = self.morning_start_hour <= hour < self.evening_start_hour

        if is_weekday and is_work_hour:
            return self.comfort_temp_window
        return self.eco_temp_window

    def adjust(
        self,
        obs: np.ndarray,
        action: dict[str, np.ndarray],
        ctx: dict[str, Any] | None = None,
    ) -> dict[str, np.ndarray]:
        """Can thiệp và cập nhật vị trí van phòng vào action.
        
        Args:
            obs: Vector quan sát hiện tại của tòa nhà.
            action: Dict chứa 'continuous_action' và 'discrete_action' từ base.
            ctx: Ngữ cảnh tùy chọn mở rộng.
            
        Returns:
            Dict action đã được cập nhật vùng van phòng của A.
        """
        continuous = action["continuous_action"]
        low, high = self._get_target_band(obs)

        for _, obs_idx, damper_idx, reheat_idx in self.zones:
            temp_k = self._denormalize_temp(obs[obs_idx])

            # Tính sai số nhiệt độ:
            # > 0 nếu phòng lạnh dưới sàn low (cần sưởi)
            # < 0 nếu phòng nóng vượt trần high (cần làm mát)
            if temp_k < low:
                zone_error = low - temp_k
            elif temp_k > high:
                zone_error = high - temp_k
            else:
                zone_error = 0.0

            # 1. Điều khiển van gió mát (damper)
            if damper_idx is not None:
                damper_ratio = min(1.0, abs(zone_error) / self.zone_damper_full_k)
                continuous[damper_idx] = 2.0 * damper_ratio - 1.0

            # 2. Điều khiển van sưởi (reheat valve)
            if reheat_idx is not None:
                if zone_error > 0:
                    reheat_ratio = min(1.0, abs(zone_error) / self.zone_reheat_full_k)
                    continuous[reheat_idx] = 2.0 * reheat_ratio - 1.0
                else: 
                    continuous[reheat_idx] = - 1.0

        return action
