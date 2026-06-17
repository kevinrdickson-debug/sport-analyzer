"""
Movement registry. THIS is the file you touch to add a sport.

Each movement defines:
  - a metrics function: takes (frames, fps, height_in) -> dict of metrics
  - target ranges for status coloring

To add a movement later: write its metrics function below, add it to the
MOVEMENTS dict at the bottom. Nothing else in the app changes.
"""
from geometry import (
    pt, dist, line_angle, joint_angle, status_for,
    L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
    L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE,
)
from explanations import explain


def _packaged(name, value, target, unit):
    status = status_for(value, target)
    return {
        "name": name,
        "value": round(value, 1) if value is not None else None,
        "target": target,
        "unit": unit,
        "status": status,
        "explanation": explain(name, status),
    }


def _series(frames, idx, axis):
    """Return list of (frame_i, value) for one landmark coordinate over time.
    axis 0 = x, 1 = y. Skips frames where the landmark is missing."""
    out = []
    for i, fr in enumerate(frames):
        p = pt(fr, idx)
        if p is not None:
            out.append((i, p[axis]))
    return out


def _detect_handedness(frames):
    """Throwing arm = the wrist that travels the most horizontally during the
    clip (the arm whips across). Returns the wrist/elbow/shoulder/knee/ankle
    indices for the THROW side and the LEAD (front) side."""
    lx = _series(frames, L_WRIST, 0)
    rx = _series(frames, R_WRIST, 0)
    l_range = (max(v for _, v in lx) - min(v for _, v in lx)) if len(lx) > 2 else 0
    r_range = (max(v for _, v in rx) - min(v for _, v in rx)) if len(rx) > 2 else 0
    if r_range >= l_range:
        # right-handed: throw = right, lead leg = left
        return {
            "throw_wrist": R_WRIST, "throw_elbow": R_ELBOW, "throw_shoulder": R_SHOULDER,
            "lead_hip": L_HIP, "lead_knee": L_KNEE, "lead_ankle": L_ANKLE,
            "back_ankle": R_ANKLE,
        }
    return {
        "throw_wrist": L_WRIST, "throw_elbow": L_ELBOW, "throw_shoulder": L_SHOULDER,
        "lead_hip": R_HIP, "lead_knee": R_KNEE, "lead_ankle": R_ANKLE,
        "back_ankle": L_ANKLE,
    }


def _detect_release_frame(frames, sides):
    """Release = frame where the throwing wrist is near its HIGHEST point
    (smallest y, since y increases downward), up near the head, just before the
    arm whips down and across into follow-through.

    Verified against real footage: at release the wrist/elbow are up high; in
    follow-through the wrist drops to shoulder height and flings out to the side
    (which is why max-x and peak-speed detectors both fired too late).

    To avoid catching the early cocked/leg-lift phase (wrist also high there),
    we only consider frames in the back half of the clip, after the stride.
    """
    wser = _series(frames, sides["throw_wrist"], 1)  # axis 1 = y (height)
    if len(wser) < 4:
        return None

    # Restrict to the throwing phase: skip the first 55% of tracked frames so
    # we don't catch the wind-up where the hand is also raised.
    start_cut = wser[int(len(wser) * 0.55)][0]

    # Highest wrist = minimum y, within the throwing-phase window.
    best_i, best_y = None, 1e9
    for i, y in wser:
        if i < start_cut:
            continue
        if y < best_y:
            best_y, best_i = y, i

    # Fallback if the window filtered everything out.
    if best_i is None:
        best_i = min(wser, key=lambda t: t[1])[0]
    return best_i


def _detect_plant_frame(frames, sides, release_i):
    """Plant = the frame BEFORE release where the lead foot stops moving forward.
    We look at the lead ankle's horizontal position and find where its
    frame-to-frame motion settles (decelerates) in the window leading up to
    release. Falls back to ~60% of the way to release if motion is noisy."""
    ser = [(i, x) for i, x in _series(frames, sides["lead_ankle"], 0)
           if release_i is None or i <= release_i]
    if len(ser) < 4:
        return release_i
    # speed per step
    speeds = []
    for k in range(1, len(ser)):
        (i_prev, x_prev), (i_cur, x_cur) = ser[k-1], ser[k]
        speeds.append((i_cur, abs(x_cur - x_prev)))
    if not speeds:
        return release_i
    # peak stride speed, then first frame after it where speed drops below 20%
    peak_speed = max(s for _, s in speeds)
    peak_idx = next(i for i, s in speeds if s == peak_speed)
    threshold = peak_speed * 0.2
    for i, s in speeds:
        if i > peak_idx and s < threshold:
            return i
    return peak_idx


# ---------------------------------------------------------------------------
# PITCHING (fully built + validated targets)
# ---------------------------------------------------------------------------
def pitching_metrics(frames, fps, height_in=None, release_frame=None):
    out = []
    sides = _detect_handedness(frames)
    # Release is provided by the user's ball tap (accurate). Only auto-detect
    # as a fallback when no tap was sent.
    release = release_frame if release_frame is not None else _detect_release_frame(frames, sides)
    if release is not None and not (0 <= release < len(frames)):
        release = None
    plant = _detect_plant_frame(frames, sides, release)

    # ---- Measured at PLANT: stride + hip-shoulder separation ----
    if plant is not None and frames[plant] is not None:
        fp = frames[plant]

        # Stride length: horizontal distance between feet at plant, as % of
        # standing height. Height proxy = shoulder-to-ankle in an early frame
        # where the pitcher is upright.
        stride_px = abs(
            (pt(fp, sides["lead_ankle"]) or (0, 0))[0]
            - (pt(fp, sides["back_ankle"]) or (0, 0))[0]
        ) if pt(fp, sides["lead_ankle"]) and pt(fp, sides["back_ankle"]) else None

        # STRIDE INDEX (relative, not textbook % of height).
        # A single 2D camera that isn't perfectly perpendicular can't give a
        # trustworthy absolute stride-as-%-of-height. So we report a relative
        # index normalized to the athlete's own leg length, useful for tracking
        # Kade vs Kade over time with the same camera setup.
        #
        # Normalize stride (ankle-to-ankle horizontal) by lead-leg length
        # (hip->knee->ankle), the most stable body segment to measure in 2D.
        # Scale x100 so a typical full stride reads near 100.
        stride_px = abs(
            (pt(fp, sides["lead_ankle"]) or (0, 0))[0]
            - (pt(fp, sides["back_ankle"]) or (0, 0))[0]
        ) if pt(fp, sides["lead_ankle"]) and pt(fp, sides["back_ankle"]) else None

        leg_px = None
        lh, lk, la = (pt(fp, sides["lead_hip"]), pt(fp, sides["lead_knee"]),
                      pt(fp, sides["lead_ankle"]))
        if lh and lk and la:
            seg1 = dist(lh, lk)
            seg2 = dist(lk, la)
            if seg1 and seg2:
                leg_px = seg1 + seg2
        stride_index = (stride_px / leg_px * 100) if (stride_px and leg_px) else None
        if stride_index is not None and not (0 <= stride_index <= 400):
            stride_index = None
        # Target band is provisional and calibrates to Kade's own baseline over
        # several sessions. Treat color as "vs his own norm," not absolute.
        out.append(_packaged("Stride index", stride_index, (90, 140), "rel"))

        # Hip-shoulder separation: difference between hip-line and shoulder-line
        # angles at plant. Normalize to 0-90 (a separation, not a signed angle).
        hip_ang = line_angle(pt(fp, L_HIP), pt(fp, R_HIP))
        sho_ang = line_angle(pt(fp, L_SHOULDER), pt(fp, R_SHOULDER))
        sep = None
        if hip_ang is not None and sho_ang is not None:
            d = abs(hip_ang - sho_ang) % 180
            sep = min(d, 180 - d)  # fold into 0-90
        out.append(_packaged("Hip-shoulder separation", sep, (40, 60), "deg"))
    else:
        out.append(_packaged("Stride index", None, (90, 140), "rel"))
        out.append(_packaged("Hip-shoulder separation", None, (40, 60), "deg"))

    # ---- Measured at RELEASE: knee flexion + arm slot ----
    if release is not None and frames[release] is not None:
        fr = frames[release]

        # Front knee flexion: 0 = straight leg, higher = more bend.
        knee = joint_angle(pt(fr, sides["lead_hip"]),
                           pt(fr, sides["lead_knee"]),
                           pt(fr, sides["lead_ankle"]))
        knee_flex = (180 - knee) if knee is not None else None
        if knee_flex is not None and not (0 <= knee_flex <= 120):
            knee_flex = None
        out.append(_packaged("Front knee flexion", knee_flex, (30, 45), "deg"))

        # Arm slot: angle of the upper arm (shoulder->elbow) above horizontal.
        # Fold to 0-90 so a sideways-or-down arm can't read as 170.
        slot = line_angle(pt(fr, sides["throw_shoulder"]), pt(fr, sides["throw_elbow"]))
        slot_abs = None
        if slot is not None:
            a = abs(slot) % 180
            slot_abs = min(a, 180 - a)  # fold into 0-90
        out.append(_packaged("Arm slot", slot_abs, (45, 90), "deg"))
    else:
        out.append(_packaged("Front knee flexion", None, (30, 45), "deg"))
        out.append(_packaged("Arm slot", None, (45, 90), "deg"))

    return {"reference_frame": {"plant": plant, "release": release}, "items": out}


PITCHING_TARGETS = {
    "Stride index": [90, 140],
    "Hip-shoulder separation": [40, 60],
    "Front knee flexion": [30, 45],
    "Arm slot": [45, 90],
}


# ---------------------------------------------------------------------------
# HITTING (stub - structure ready, validate ranges before trusting numbers)
# ---------------------------------------------------------------------------
def hitting_metrics(frames, fps, height_in=None, release_frame=None):
    contact = _detect_release_frame(frames, _detect_handedness(frames))  # placeholder
    out = []
    if contact is not None:
        fr = frames[contact]
        hip_ang = line_angle(pt(fr, L_HIP), pt(fr, R_HIP))
        sho_ang = line_angle(pt(fr, L_SHOULDER), pt(fr, R_SHOULDER))
        sep = abs(hip_ang - sho_ang) if (hip_ang is not None and sho_ang is not None) else None
        out.append(_packaged("Hip-shoulder separation", sep, (35, 55), "deg"))
        # TODO: bat path, weight shift, contact extension once validated
    return {"reference_frame": contact, "items": out,
            "note": "hitting ranges are provisional, validate before trusting"}

HITTING_TARGETS = {"Hip-shoulder separation": [35, 55]}


# ---------------------------------------------------------------------------
# SOCCER KICK (stub)
# ---------------------------------------------------------------------------
def kick_metrics(frames, fps, height_in=None, release_frame=None):
    sides = _detect_handedness(frames)
    plant = _detect_plant_frame(frames, sides, _detect_release_frame(frames, sides))
    out = []
    if plant is not None:
        fr = frames[plant]
        hip_rot = line_angle(pt(fr, L_HIP), pt(fr, R_HIP))
        out.append(_packaged("Hip line at plant", hip_rot, (-20, 20), "deg"))
        # TODO: plant foot position, follow-through angle, ball speed
    return {"reference_frame": plant, "items": out,
            "note": "kick ranges are provisional"}

KICK_TARGETS = {"Hip line at plant": [-20, 20]}


# ---------------------------------------------------------------------------
# FIELDING (stub - hardest, sequence-based, add last)
# ---------------------------------------------------------------------------
def fielding_metrics(frames, fps, height_in=None, release_frame=None):
    return {"reference_frame": None, "items": [],
            "note": "fielding is sequence-based, not yet implemented"}

FIELDING_TARGETS = {}


# ---------------------------------------------------------------------------
# REGISTRY - add new movements here
# ---------------------------------------------------------------------------
MOVEMENTS = {
    "pitching": {"metrics": pitching_metrics, "targets": PITCHING_TARGETS},
    "hitting":  {"metrics": hitting_metrics,  "targets": HITTING_TARGETS},
    "kick":     {"metrics": kick_metrics,     "targets": KICK_TARGETS},
    "fielding": {"metrics": fielding_metrics, "targets": FIELDING_TARGETS},
}
