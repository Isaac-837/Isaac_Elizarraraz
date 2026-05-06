from ultralytics import YOLO


#Isaac Elizarraraz [3/30/2026]
#This function is passed a frame and returns a list of detected objects
def detect_objects(frame,detector:YOLO):
    """
    Runs YOLOv8 inference on a given video frame to find specific objects.

    Args:
        frame (np.ndarray): The OpenCV BGR image matrix.
        detector (YOLO): The instantiated Ultralytics YOLO model.

    Returns:
        list: A list of dictionaries containing detected labels, bounding boxes, and confidence scores.
    """
    detections = []
    results = detector(frame, verbose=False)

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = detector.names[cls]

            if label == 'stop sign':
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                detections.append({
                    "label": label,
                    "bbox": (x1,y1,x2,y2),
                    "confidence": float(box.conf[0])
                })
            elif label == 'person':
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                detections.append({
                    "label": label,
                    "bbox": (x1,y1,x2,y2),
                    "confidence": float(box.conf[0])
                })

    return detections


#Isaac Elizarraraz [3/30/2026]
#helper function for object detection handling
#measures the distance from an object by the size of its bounding box
#the measurement may need to be calibrated based on the cameras focal length
def measure_distance(bbox,focal_length,real_height):
    """
    Estimates distance to an object using the pinhole camera geometry model.

    Args:
        bbox (tuple): Bounding box coordinates (x1, y1, x2, y2).
        focal_length (float): Calibrated camera focal length.
        real_height (float): Known physical height of the object in meters.

    Returns:
        float: Estimated distance in meters, or None if calculation fails.
    """
    x1,y1,x2,y2 = bbox
    height = abs(y2-y1)

    if height <= 0: return None

    distance = (real_height * focal_length)/(height)
    return distance