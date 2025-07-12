import cv2
import numpy as np
from typing import List, Dict


def analyze_video(video_path: str) -> List[Dict]:
    """
    Analyzes the given video file and extracts a list of user actions.
    Attempts to detect:
      - Mouse cursor movement (by tracking a bright spot or shape)
      - Clicks (by detecting sudden cursor stops and/or visual feedback)
      - Scrolls (by detecting rapid vertical motion of the screen)
      - Page changes (by detecting large screen changes)
    """
    actions = []
    cap = cv2.VideoCapture(video_path)
    prev_frame = None
    prev_cursor = None
    frame_idx = 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    last_scroll = None
    last_page_change = None
    last_cursor_move = None
    click_cooldown = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (21, 21), 0)
        timestamp = frame_idx / fps

        # --- Detect page change (large screen change) ---
        if prev_frame is not None:
            frame_delta = cv2.absdiff(prev_frame, gray_blur)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            motion_score = np.sum(thresh) / 255
            if motion_score > 100000:  # Large threshold for page change
                if not last_page_change or (timestamp - last_page_change > 1):
                    actions.append({
                        "type": "page_change",
                        "timestamp": timestamp,
                        "motion_score": float(motion_score)
                    })
                    last_page_change = timestamp
        prev_frame = gray_blur

        # --- Detect mouse cursor (brightest spot heuristic) ---
        minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(gray)
        cursor_pos = maxLoc  # (x, y)
        if prev_cursor is not None:
            dx = cursor_pos[0] - prev_cursor[0]
            dy = cursor_pos[1] - prev_cursor[1]
            dist = np.hypot(dx, dy)
            # Mouse move
            if dist > 5:
                actions.append({
                    "type": "mouse_move",
                    "timestamp": timestamp,
                    "from": prev_cursor,
                    "to": cursor_pos
                })
                last_cursor_move = timestamp
            # Click: sudden stop after move (and not too soon after last click)
            elif dist < 2 and last_cursor_move and (timestamp - last_cursor_move < 0.2) and click_cooldown == 0:
                actions.append({
                    "type": "mouse_click",
                    "timestamp": timestamp,
                    "position": cursor_pos
                })
                click_cooldown = int(fps * 0.3)  # 0.3s cooldown
        prev_cursor = cursor_pos
        if click_cooldown > 0:
            click_cooldown -= 1

        # --- Detect scroll (vertical motion in central region) ---
        h, w = gray.shape
        center_strip = gray[int(h*0.3):int(h*0.7), int(w*0.4):int(w*0.6)]
        if frame_idx > 0:
            if 'prev_center_strip' in locals():
                strip_delta = cv2.absdiff(center_strip, prev_center_strip)
                strip_motion = np.sum(strip_delta) / 255
                if strip_motion > 5000:  # Heuristic threshold
                    direction = 'down' if np.mean(center_strip) > np.mean(prev_center_strip) else 'up'
                    if not last_scroll or (timestamp - last_scroll > 0.5):
                        actions.append({
                            "type": "scroll",
                            "timestamp": timestamp,
                            "direction": direction,
                            "motion_score": float(strip_motion)
                        })
                        last_scroll = timestamp
            prev_center_strip = center_strip.copy()
        else:
            prev_center_strip = center_strip.copy()

        frame_idx += 1
    cap.release()
    return actions 

if __name__ == '__main__':
    actions = analyze_video('/Users/markkuang/PycharmProjects/workflow-use/workflows/tmp/people-detection.mp4')
    print("ACTIONS")
    print(actions)