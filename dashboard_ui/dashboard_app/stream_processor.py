from __future__ import annotations

from typing import List, Tuple

import numpy as np


def derive_detection_state(
    keypoints_list: List[list],
    consecutive_frames: int = 0,
    proximity_threshold: int = 150,
    required_frames: int = 5,
) -> Tuple[str, bool, float, int]:
    """Convert pose keypoints into a simple shave-detection state.

    This is intentionally lightweight so the dashboard can use the same logic
    as the backend detector without requiring a full YOLO runtime in the web process.
    """
    if not keypoints_list:
        return "EMPTY", False, 0.0, max(0, consecutive_frames - 1)

    if len(keypoints_list) == 1:
        return "CUSTOMER SEATED", False, 0.0, max(0, consecutive_frames - 1)

    try:
        barber = keypoints_list[0]
        customer = keypoints_list[1]
        left_wrist = barber[9] if len(barber) > 9 else None
        right_wrist = barber[10] if len(barber) > 10 else None
        face = customer[0] if len(customer) > 0 else None

        if face is not None and len(face) >= 2:
            min_dist = float("inf")
            for wrist in [left_wrist, right_wrist]:
                if wrist is not None and len(wrist) >= 2:
                    dist = float(np.linalg.norm(np.array(wrist[:2]) - np.array(face[:2])))
                    min_dist = min(min_dist, dist)

            if min_dist < proximity_threshold:
                confidence = float(1.0 - (min_dist / proximity_threshold))
                consecutive_frames += 1
                is_shaving = consecutive_frames >= required_frames
                if is_shaving:
                    return "SHAVING ACTIVE", True, confidence, consecutive_frames
                return "BARBER PRESENT", False, confidence, consecutive_frames

        return "BARBER PRESENT", False, 0.0, max(0, consecutive_frames - 1)
    except (IndexError, ValueError, TypeError):
        return "BARBER PRESENT", False, 0.0, max(0, consecutive_frames - 1)
