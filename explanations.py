"""
Static, rule-based coaching explanations for each metric.

Design guardrails (deliberate):
- These explain well-documented, uncontroversial mechanical relationships only.
- Every cue is framed as "what this would suggest IF it holds across pitches,"
  because the target bands are generic (not yet calibrated to the athlete) and a
  2D side camera compresses some angles.
- Where a real coaching judgment is needed, the cue says "check with his coach"
  rather than inventing a drill or biomechanical claim.
- Nothing here is a medical or definitive performance claim.

Each entry maps metric name -> function(status) -> explanation dict:
  what    : what the metric measures (always shown)
  reading : what THIS status suggests (status-specific)
  caveat  : the confidence / calibration caveat (always shown)
"""

# What each metric measures (status-independent).
_WHAT = {
    "Stride index":
        "How far the lead foot strides relative to the athlete's own leg "
        "length. Longer strides generally support more extension and velocity.",
    "Hip-shoulder separation":
        "The angle between the hip line and shoulder line near plant. It is the "
        "main torque source for a pitch: hips lead, shoulders follow.",
    "Front knee flexion":
        "How much the front knee is bent at release. A firming/extending front "
        "leg helps transfer energy up the chain.",
    "Arm slot":
        "The angle of the throwing upper arm at release: over-the-top vs "
        "three-quarter vs sidearm. Mostly a consistency marker, not good/bad.",
}

# Calibration caveats (status-independent).
_CAVEAT = {
    "Stride index":
        "Relative index, not a textbook number. Most useful tracked against his "
        "own baseline over several pitches with the same camera setup.",
    "Hip-shoulder separation":
        "A 2D side camera compresses this angle, so a low reading can be camera "
        "angle rather than mechanics. Treat as a watch-item until confirmed.",
    "Front knee flexion":
        "Some pitchers block with a firm, fairly straight front leg by design, "
        "so 'low' is not automatically a flaw. Compare to his own norm.",
    "Arm slot":
        "Arm slot is a style, not a target to hit. The band only flags whether "
        "it is consistent pitch to pitch.",
}

# Status-specific readings.
def _reading(name, status):
    table = {
        "Stride index": {
            "green": "Stride is in a healthy range relative to his leg length.",
            "yellow": "Stride is near the edge of his typical range.",
            "red": "Stride looks short relative to leg length, which can limit "
                   "extension and velocity if it holds across pitches.",
        },
        "Hip-shoulder separation": {
            "green": "Hips and shoulders are sequencing with good separation.",
            "yellow": "Separation is moderate; some torque available.",
            "red": "Low separation suggests hips and shoulders may be rotating "
                   "together rather than hips leading, which can cost velocity.",
        },
        "Front knee flexion": {
            "green": "Front knee bend is in a typical range at release.",
            "yellow": "Front knee bend is near the edge of the expected range.",
            "red": "Front leg is fairly straight at release. If unintended, a "
                   "firmer block can sometimes help energy transfer, but this is "
                   "a coach call, not a fix to force.",
        },
        "Arm slot": {
            "green": "Arm slot sits in a consistent over-the-top/high range.",
            "yellow": "Arm slot is slightly outside the consistency band.",
            "red": "Arm slot reads unusual for this frame; verify the release "
                   "frame is correct before reading anything into it.",
        },
    }
    return table.get(name, {}).get(status, "")


def explain(name, status):
    """Return the explanation dict for a metric at a given status."""
    return {
        "what": _WHAT.get(name, ""),
        "reading": _reading(name, status),
        "caveat": _CAVEAT.get(name, ""),
    }
