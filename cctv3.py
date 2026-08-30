import cv2
import math
import time
import numpy as np
from ultralytics import YOLO

# ==========================================
# ADVANCED EVENT-BASED THREAT ENGINE
# ==========================================
class AdvancedEventSurveillanceEngine:
    def __init__(self):
        self.active_alerts_memory = {}
        self.ALERT_HOLD_DURATION = 3.5
        self.CONFIRMATION_FRAMES = 2
        
        # Spatial & Motion Thresholds
        self.WRIST_TO_NECK_MAX_DIST = 65.0   # Pixel distance threshold between wrist & victim head/neck
        self.MIN_MOTION_VELOCITY = 12.0      # Minimum joint velocity (pixels/frame) required for violent hit
        self.WEAPON_PROXIMITY_THRESHOLD = 110.0
        
        # Frame-to-frame joint history for velocity calculations
        self.previous_keypoints = {}
        self._pending_counters = {}

    def _calculate_distance(self, pt1, pt2):
        if pt1 is None or pt2 is None:
            return float('inf')
        return math.sqrt((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2)

    def _calculate_velocity(self, current_pt, previous_pt):
        if current_pt is None or previous_pt is None:
            return 0.0
        return math.sqrt((current_pt[0] - previous_pt[0]) ** 2 + (current_pt[1] - previous_pt[1]) ** 2)

    def _confirm(self, key):
        self._pending_counters[key] = self._pending_counters.get(key, 0) + 1
        return self._pending_counters[key] >= self.CONFIRMATION_FRAMES

    def _decay_unseen(self, seen_keys):
        for key in list(self._pending_counters.keys()):
            if key not in seen_keys:
                del self._pending_counters[key]

    def _remember_alert(self, alert_msg, current_time, threat_boxes, boxes):
        self.active_alerts_memory[alert_msg] = {
            "expires": current_time + self.ALERT_HOLD_DURATION,
            "boxes": boxes,
        }
        threat_boxes.extend(boxes)

    def process_pose_event_rules(self, detected_people, detected_weapons):
        """
        Evaluates contextual events based on Skeleton Joints (YOLO-Pose Keypoints):
        0: Nose, 1: L-Eye, 2: R-Eye, 3: L-Ear, 4: R-Ear, 
        9: L-Wrist, 10: R-Wrist, 13: L-Knee, 14: R-Knee, 15: L-Ankle, 16: R-Ankle
        """
        current_time = time.time()
        person_ids = list(detected_people.keys())
        seen_this_frame = set()
        threat_boxes = []

        for i in range(len(person_ids)):
            p1_id = person_ids[i]
            p1_data = detected_people[p1_id]
            box1, kpts1 = p1_data["box"], p1_data["keypoints"]

            # --- EVENT 1: WEAPON THREAT EVENT ---
            for w_idx, weapon in enumerate(detected_weapons):
                w_coords = weapon["box"]
                w_cx = (w_coords[0] + w_coords[2]) / 2
                w_cy = (w_coords[1] + w_coords[3]) / 2
                p1_cx = (box1[0] + box1[2]) / 2
                p1_cy = (box1[1] + box1[3]) / 2

                if self._calculate_distance((w_cx, w_cy), (p1_cx, p1_cy)) < self.WEAPON_PROXIMITY_THRESHOLD:
                    key = f"WEAPON_{p1_id}_{w_idx}"
                    seen_this_frame.add(key)
                    if self._confirm(key):
                        weapon_name = weapon["label"].upper()
                        alert_msg = f"CRITICAL: Armed Threat - {weapon_name} near Person {p1_id}"
                        self._remember_alert(alert_msg, current_time, threat_boxes, [box1, w_coords])

            # --- EVENT 2: INTERACTION & VIOLENCE EVENTS ---
            for j in range(i + 1, len(person_ids)):
                p2_id = person_ids[j]
                p2_data = detected_people[p2_id]
                box2, kpts2 = p2_data["box"], p2_data["keypoints"]

                ordered_ids = f"{min(p1_id, p2_id)}_{max(p1_id, p2_id)}"

                if kpts1 is not None and kpts2 is not None:
                    p1_wrists = [kpts1[9], kpts1[10]]   # Left & Right Wrists
                    p1_legs = [kpts1[15], kpts1[16]]     # Left & Right Ankles

                    p2_wrists = [kpts2[9], kpts2[10]]
                    p2_head = kpts2[0] if kpts2[0] is not None else kpts2[1]  # Nose or Eye target
                    p2_neck = kpts2[5] if len(kpts2) > 5 else p2_head
                    p2_legs = [kpts2[15], kpts2[16]]

                    # Compute kinematic movement velocity across consecutive frames
                    prev_kpts1 = self.previous_keypoints.get(p1_id)
                    p1_wrist_vel = 0.0
                    if prev_kpts1 is not None:
                        p1_wrist_vel = max(
                            self._calculate_velocity(kpts1[9], prev_kpts1[9]),
                            self._calculate_velocity(kpts1[10], prev_kpts1[10])
                        )

                    # A. EVENT: POISON HANDKERCHIEF / NECK HOLDING
                    # Condition: Wrist positioned directly over victim's face/neck
                    for w in p1_wrists:
                        if w and p2_head:
                            dist_to_face = self._calculate_distance(w, p2_head)
                            if dist_to_face < self.WRIST_TO_NECK_MAX_DIST:
                                key = f"NECK_POISON_{ordered_ids}"
                                seen_this_frame.add(key)
                                if self._confirm(key):
                                    alert_msg = f"CRITICAL: Poison Handkerchief / Neck Hold Event (IDs: {p1_id} & {p2_id})"
                                    self._remember_alert(alert_msg, current_time, threat_boxes, [box1, box2])

                    # B. EVENT: PHYSICAL BEATING / PUNCHING
                    # Condition: Wrist near upper torso/head AND moving with high velocity
                    for w in p1_wrists:
                        if w and p2_neck:
                            dist_to_body = self._calculate_distance(w, p2_neck)
                            if dist_to_body < (self.WRIST_TO_NECK_MAX_DIST * 1.5) and p1_wrist_vel > self.MIN_MOTION_VELOCITY:
                                key = f"PUNCH_{ordered_ids}"
                                seen_this_frame.add(key)
                                if self._confirm(key):
                                    alert_msg = f"CRITICAL: Violent Punching/Beating Event (IDs: {p1_id} & {p2_id})"
                                    self._remember_alert(alert_msg, current_time, threat_boxes, [box1, box2])

                    # C. EVENT: KICKING ASSAULT
                    # Condition: Foot/Ankle elevated significantly and driving towards opponent
                    for ankle in p1_legs:
                        if ankle and p2_neck:
                            if ankle[1] < box1[3] - ((box1[3] - box1[1]) * 0.3):  # Foot lifted high
                                dist_to_target = self._calculate_distance(ankle, p2_neck)
                                if dist_to_target < (self.WRIST_TO_NECK_MAX_DIST * 1.8):
                                    key = f"KICK_{ordered_ids}"
                                    seen_this_frame.add(key)
                                    if self._confirm(key):
                                        alert_msg = f"CRITICAL: Violent Kicking Event (IDs: {p1_id} & {p2_id})"
                                        self._remember_alert(alert_msg, current_time, threat_boxes, [box1, box2])

            # Update historical pose buffer for velocity calculation
            if kpts1 is not None:
                self.previous_keypoints[p1_id] = kpts1

        self._decay_unseen(seen_this_frame)
        self.active_alerts_memory = {
            msg: data for msg, data in self.active_alerts_memory.items()
            if current_time < data["expires"]
        }

        for data in self.active_alerts_memory.values():
            threat_boxes.extend(data["boxes"])

        return list(self.active_alerts_memory.keys()), threat_boxes


# ==========================================
# DRAWING UTILITIES & PIPELINE
# ==========================================
def draw_box(frame, coords, label, color, thickness=2):
    x1, y1, x2, y2 = [int(v) for v in coords]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

def boxes_overlap(box1, box2, min_ratio=0.45):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])
    if x_right <= x_left or y_bottom <= y_top:
        return False
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    smaller_area = min(area1, area2)
    return smaller_area > 0 and (intersection_area / smaller_area) >= min_ratio

def is_threat_box(coords, threat_boxes):
    return any(boxes_overlap(coords, threat_box) for threat_box in threat_boxes)

def get_track_id(box, fallback_id):
    if box.id is None:
        return fallback_id
    try:
        return int(box.id[0])
    except (TypeError, ValueError, IndexError):
        return fallback_id


def run_surveillance_system(video_path=0, pose_model_path="yolov8n-pose.pt"):
    print("[INFO] Launching Event-Based Intelligent Surveillance Engine...")
    
    try:
        pose_model = YOLO(pose_model_path)
    except Exception as exc:
        print(f"[WARN] Downloading default pose model... ({exc})")
        pose_model = YOLO("yolov8n-pose.pt")

    engine = AdvancedEventSurveillanceEngine()

    weapon_labels = {
        "knife": "Knife",
        "scissors": "Knife-like Weapon",
        "gun": "Gun", "pistol": "Gun", "rifle": "Gun",
    }

    cap = cv2.VideoCapture(video_path, cv2.CAP_DSHOW if video_path == 0 else cv2.CAP_ANY)
    if not cap.isOpened():
        cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("[ERROR] Could not open video feed source.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    fallback_id = 1

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Track joints and bounding boxes concurrently
        try:
            results = pose_model.track(frame, persist=True, verbose=False, conf=0.35, iou=0.45)
        except Exception:
            results = pose_model.predict(frame, verbose=False, conf=0.35, iou=0.45)

        detected_people = {}
        detected_weapons = []
        tracked_boxes = []

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            
            keypoints_data = None
            if hasattr(results[0], 'keypoints') and results[0].keypoints is not None:
                keypoints_data = results[0].keypoints.xy.cpu().numpy()

            for idx, box in enumerate(boxes):
                cls_id = int(box.cls[0])
                label = pose_model.names[cls_id].lower()
                coords = box.xyxy[0].tolist()
                track_id = get_track_id(box, fallback_id)
                fallback_id += 1

                if label == "person":
                    kpts = None
                    if keypoints_data is not None and idx < len(keypoints_data):
                        raw_kpts = keypoints_data[idx]
                        kpts = [(float(pt[0]), float(pt[1])) if pt[0] > 0 else None for pt in raw_kpts]

                    detected_people[track_id] = {"box": coords, "keypoints": kpts}
                    tracked_boxes.append(("person", track_id, coords))

                elif label in weapon_labels:
                    weapon_name = weapon_labels[label]
                    detected_weapons.append({"label": weapon_name, "box": coords})
                    tracked_boxes.append((weapon_name, track_id, coords))

        # Evaluate rules using Event Understanding & Motion Kinetics
        visible_alerts, threat_boxes = engine.process_pose_event_rules(detected_people, detected_weapons)

        # Render Bounding Boxes
        for label, track_id, coords in tracked_boxes:
            threat = is_threat_box(coords, threat_boxes)
            color = (0, 0, 255) if threat else (255, 100, 0)

            if label == "person":
                text = f"THREAT ID: {track_id}" if threat else f"Person ID: {track_id}"
            else:
                text = f"WARNING: {label.upper()}"
                color = (0, 0, 255)

            draw_box(frame, coords, text, color, thickness=3 if threat else 2)

        # Render UI Banner Overlay
        if visible_alerts:
            y_offset = 50
            for alert in visible_alerts:
                cv2.rectangle(frame, (20, y_offset - 24), (740, y_offset + 12), (0, 0, 140), -1)
                cv2.putText(frame, alert, (30, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                y_offset += 40

        cv2.imshow("Builder Boys Intelligent Surveillance Engine", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_surveillance_system(video_path=0)