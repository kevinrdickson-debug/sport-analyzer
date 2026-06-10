"""
Velocity from two manual taps. This is the reliable path that avoids
fragile auto ball-tracking.

The user taps the ball at release and at catch/contact, and tells us how
many frames are between those two taps. A known reference object in frame
(rubber width, marker) converts pixels to real distance.
"""
import math

MPH_PER_FPS = 0.681818  # feet/sec -> mph


def velocity_from_marks(release, catch, frames_between, fps, ref_px, ref_inches):
    """
    release, catch : (x, y) normalized 0-1 tap coordinates
    frames_between : number of frames between the two taps
    fps            : video frame rate (e.g. 240 for slow-mo)
    ref_px         : pixel length of the reference object in the frame
    ref_inches     : real-world length of that reference object

    Returns mph (float) or None if inputs are unusable.
    NOTE: tap coords are normalized 0-1, so we need the frame width in px
    to convert. We approximate using ref_px which is already in px, and
    treat tap distance in normalized units scaled by the same frame.
    For simplicity the frontend sends ref_px and tap deltas in the SAME
    coordinate space (pixels). See frontend notes.
    """
    if None in (frames_between, fps, ref_px, ref_inches) or ref_px == 0:
        return None
    if frames_between <= 0 or fps <= 0:
        return None

    # pixel distance the ball traveled
    px_traveled = math.hypot(catch[0] - release[0], catch[1] - release[1])

    inches_per_px = ref_inches / ref_px
    feet_traveled = (px_traveled * inches_per_px) / 12.0

    seconds = frames_between / fps
    fps_speed = feet_traveled / seconds  # feet per second
    return round(fps_speed * MPH_PER_FPS, 1)
