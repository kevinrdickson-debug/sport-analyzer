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
    L_SHOULDER, R_SHOULDER, L_HIP, R_HIP,
    L_KNEE, R_KNEE, L_ANKLE, R_ANKLE, R_WRIST, R_ELBOW,
)


def _packaged(name, value, target, unit):
    return {
        "name": name,
        "value": round(value, 1) if value is not None else None,
        "target": target,
        "unit": unit,
        "status": status_for(value, target),
    }


def _find_plant_frame(frames):
    """Crude front-foot plant detector: frame where ankle separation is widest.
    Good enough as the reference moment for stride and separation."""
    best_i, best_sep = None, -1
    for i, fr in enumerate(frames):
        sep = dist(pt(fr, L_ANKLE), pt(fr, R_ANKLE))
        if sep is not None and sep > best_sep:
            best_sep, best_i = sep, i
    return best_i


# ---------------------------------------------------------------------------
# PITCHING (fully built + validated targets)
# ---------------------------------------------------------------------------
def pitching_metrics(frames, fps, height_in=None):
    plant = _find_plant_frame(frames)
    out = []

    if plant is not None:
        fr = frames[plant]

        # Stride length as % of standing height (uses pixel proxy)
        stride_px = dist(pt(fr, L_ANKLE), pt(fr, R_ANKLE))
        # standing height proxy = shoulder midpoint to ankle, early frame
        early = next((f for f in frames if f is not None), None)
        height_px = None
        if early is not None:
            sh = pt(early, R_SHOULDER)
            ank = pt(early, R_ANKLE)
            height_px = dist(sh, ank)
        stride_pct = (stride_px / height_px * 100) if (stride_px and height_px) else None
        out.append(_packaged("Stride length", stride_pct, (85, 110), "% height"))

        # Hip-shoulder separation at plant
        hip_ang = line_angle(pt(fr, L_HIP), pt(fr, R_HIP))
        sho_ang = line_angle(pt(fr, L_SHOULDER), pt(fr, R_SHOULDER))
        sep = abs(hip_ang - sho_ang) if (hip_ang is not None and sho_ang is not None) else None
        out.append(_packaged("Hip-shoulder separation", sep, (40, 60), "deg"))

        # Front knee flexion (right side assumed lead for a lefty; adjust as needed)
        knee = joint_angle(pt(fr, R_HIP), pt(fr, R_KNEE), pt(fr, R_ANKLE))
        knee_flex = (180 - knee) if knee is not None else None
        out.append(_packaged("Front knee flexion", knee_flex, (30, 45), "deg"))

        # Arm slot at plant (shoulder-elbow-wrist line vs horizontal)
        slot = line_angle(pt(fr, R_SHOULDER), pt(fr, R_WRIST))
        slot_abs = abs(slot) if slot is not None else None
        out.append(_packaged("Arm slot", slot_abs, (75, 95), "deg"))

    return {"reference_frame": plant, "items": out}


PITCHING_TARGETS = {
    "Stride length": [85, 110],
    "Hip-shoulder separation": [40, 60],
    "Front knee flexion": [30, 45],
    "Arm slot": [75, 95],
}


# ---------------------------------------------------------------------------
# HITTING (stub - structure ready, validate ranges before trusting numbers)
# ---------------------------------------------------------------------------
def hitting_metrics(frames, fps, height_in=None):
    contact = _find_plant_frame(frames)  # placeholder reference moment
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
def kick_metrics(frames, fps, height_in=None):
    plant = _find_plant_frame(frames)
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
def fielding_metrics(frames, fps, height_in=None):
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
