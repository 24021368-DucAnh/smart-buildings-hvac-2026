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
        zone_reheat_full_k: float = 1.0,
        max_heating_damper: float = 0.35,
        heating_damper_start_k: float = 1.0,
        # Tốc độ tích lũy
        ki: float = 0.05,
        # Tích phân limit
        integral_limit: float = 2.0,
        # Tốc độ tích phân giảm
        integral_decay: float = 0.85,

    ) -> None:
        """Khởi tạo một lần cho mỗi tòa nhà.
        
        Args:
            building_meta_data: Metadata của tòa nhà nhận từ môi trường.
            zone_damper_full_k: Độ lệch nhiệt độ (Kelvin) để van gió mở 100%.
        """
        self.metadata = building_meta_data
        self.zone_damper_full_k = zone_damper_full_k
        self.zone_reheat_full_k = zone_reheat_full_k
        self.max_heating_damper = max_heating_damper
        self.heating_damper_start_k = heating_damper_start_k
        self.integral_decay = integral_decay
        self.integral_limit = integral_limit
        self.ki = ki

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

        # 4. Ánh xạ từng phòng: (tên_vav, chỉ_số_obs, chỉ_số_damper, chỉ_số_reheat, heat_sp_idx, cool_sp_idx)
        self.zones: list[tuple[str, int, int | None, int | None, int | None, int | None]] = []
        self.zone_integrals: dict[str, float] = {}
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

                # Lưu lại cảm biến của từng phòng 
                # Độ ấm bé nhất
                heat_sp_field = f"{vav_id}_zone_air_heating_temperature_setpoint_sensor"
                # Độ mát lớn nhất
                cool_sp_field = f"{vav_id}_zone_air_cooling_temperature_setpoint_sensor"
                # Lưu Vị trí 2 cảm biến, để đọc trực tiếp từ obs
                heat_sp_idx = field_names.index(heat_sp_field) if heat_sp_field in field_names else None
                cool_sp_idx = field_names.index(cool_sp_field) if cool_sp_field in field_names else None
                
                self.zones.append((vav_id, obs_idx, damper_idx, reheat_idx, heat_sp_idx, cool_sp_idx))
                self.zone_integrals[vav_id] = 0.0

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
        low_default, high_default = self._get_target_band(obs)

        for vav_id, obs_idx, damper_idx, reheat_idx, heat_sp_idx, cool_sp_idx in self.zones:
            # Giải chuẩn hóa nhiệt độ
            temp_k = self._denormalize_temp(obs[obs_idx])

            # Lấy setpoint nếu cảm biến đo được, không thì lấy default
            low = float(obs[heat_sp_idx]) if heat_sp_idx is not None else low_default
            high = float(obs[cool_sp_idx]) if cool_sp_idx is not None else high_default
            if not (np.isfinite(low) and np.isfinite(high) and low < high):
                low, high = low_default, high_default

            # Tính sai số nhiệt độ:
            error_heat = max(0.0, low - temp_k)
            error_cool = max(0.0, temp_k - high)

            # Dương khi đang lạnh, âm khi đang nóng, bằng 0 khi trong dải
            signed_error = error_heat - error_cool
            # Lấy tích phân hiện tại
            integral = self.zone_integrals[vav_id]
            # Nếu trong dải tiện nghi: xả dần tích phân
            if signed_error == 0.0:
                integral *= self.integral_decay
            # Nếu integral ngược dấu với signed_error (đổi pha, reset rồi tích lũy lại)
            elif integral * signed_error < 0.0:
                integral = self.ki * signed_error
            # Ngược lại cùng dấu với signed_error (tiếp tục tích lũy)
            else:
                integral += self.ki * signed_error
            # Chặn biên anti-windup
            integral = float(np.clip(integral, -self.integral_limit, self.integral_limit))
            self.zone_integrals[vav_id] = integral

            # Tính sai số hiệu dụng sau khi cộng tích phân
            effort_heat = error_heat + max(0.0, integral)
            effort_cool = error_cool + max(0.0, -integral)

            # Điều khiển 2 van
            # Nếu đang bị lạnh
            if error_heat > 0:
                if reheat_idx is not None:
                    heat_ratio = min(1.0, effort_heat / self.zone_reheat_full_k)
                    continuous[reheat_idx] = 2.0 * heat_ratio - 1.0
                if damper_idx is not None:
                    if effort_heat <= self.heating_damper_start_k:
                        heat_damper_ratio = 0.0
                    else:
                        extra_cold = max(0.0, effort_heat - self.heating_damper_start_k)
                        heat_damper_ratio = min(
                            self.max_heating_damper,
                            (extra_cold / self.zone_damper_full_k) * self.max_heating_damper,
                        )
                    continuous[damper_idx] = 2.0 * heat_damper_ratio - 1.0

            # Nếu đang nóng
            elif error_cool > 0:
                if reheat_idx is not None:
                    continuous[reheat_idx] = -1.0
                if damper_idx is not None:
                    cool_ratio = min(1.0, effort_cool / self.zone_damper_full_k)
                    continuous[damper_idx] = 2.0 * cool_ratio - 1.0
            else:
                if reheat_idx is not None:
                    continuous[reheat_idx] = -1.0
                if damper_idx is not None:
                    continuous[damper_idx] = -1.0
        return action
