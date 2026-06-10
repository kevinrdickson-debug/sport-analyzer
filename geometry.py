"""
Shared geometry helpers. MediaPipe landmark coords are normalized 0-1.
Landmark index reference:
 11/12 shoulders, 13/14 elbows, 15/16 wrists,
 23/24 hips, 25/26 knees, 27/28 ankles.
Even indices = left side of the body, odd = right (from MediaPipe's view).
"""
import math

# Named indices for readability
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def pt(frame, idx):
    """Return (x, y) for a landmark index, or None if missing/low visibility."""
    if frame is None:
        return None
    x, y, z, vis = frame[idx]
    if vis < 0.3:
        return None
    return (x, y)


def dist(a, b):
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def line_angle(a, b):
    """Angle in degrees of the line from a to b, relative to horizontal."""
    if a is None or b is None:
        return None
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def joint_angle(a, b, c):
    """Interior angle at point b formed by a-b-c, in degrees."""
    if None in (a, b, c):
        return None
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    d = math.hypot(*v1) * math.hypot(*v2)
    if d == 0:
        return None
    cosang = max(-1.0, min(1.0, (v1[0]*v2[0] + v1[1]*v2[1]) / d))
    return math.degrees(math.acos(cosang))


def status_for(value, target):
    """Green if inside [lo, hi], yellow if within 15% of the band, red otherwise."""
    if value is None:
        return "unknown"
    lo, hi = target
    if lo <= value <= hi:
        return "green"
    band = (hi - lo) * 0.15
    if (lo - band) <= value <= (hi + band):
        return "yellow"
    return "red"
