"""
Sport Analyzer backend.
One pose engine, multiple movement types.
Adding a new movement = add one entry to the MOVEMENTS registry.
"""
import os
import tempfile
import cv2
import mediapipe as mp
from flask import Flask, request, jsonify
from flask_cors import CORS

from movements import MOVEMENTS
from velocity import velocity_from_marks

app = Flask(__name__)
CORS(app)

mp_pose = mp.solutions.pose


def extract_landmarks(video_path):
    """Run MediaPipe Pose on every frame. Returns (fps, list_of_frames).
    Each frame is a list of 33 (x, y, z, visibility) tuples, or None if no pose."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    with mp_pose.Pose(model_complexity=1, min_detection_confidence=0.5) as pose:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)
            if res.pose_landmarks:
                frames.append([
                    (lm.x, lm.y, lm.z, lm.visibility)
                    for lm in res.pose_landmarks.landmark
                ])
            else:
                frames.append(None)
    cap.release()
    return fps, frames


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "movements": list(MOVEMENTS.keys())})


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Form-data params:
      video        : the video file (required)
      movement     : one of MOVEMENTS keys, default 'pitching'
      height_in    : athlete height in inches (for stride %), optional
      ref_inches   : real-world length of the reference object, optional
      release_x/y  : normalized coords of release point tap (manual velo)
      catch_x/y    : normalized coords of catch/contact point tap (manual velo)
      frames_between : frame count between the two marks (manual velo)
    """
    if "video" not in request.files:
        return jsonify({"error": "no video uploaded"}), 400

    movement = request.form.get("movement", "pitching")
    if movement not in MOVEMENTS:
        return jsonify({"error": f"unknown movement '{movement}'",
                        "available": list(MOVEMENTS.keys())}), 400

    f = request.form
    height_in = float(f.get("height_in", 0)) or None
    ref_inches = float(f.get("ref_inches", 0)) or None

    # Save upload to a temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mov")
    request.files["video"].save(tmp.name)

    try:
        fps, frames = extract_landmarks(tmp.name)
        if not any(frames):
            return jsonify({"error": "no pose detected. check framing and lighting."}), 422

        # Velocity from manual tap marks (the reliable path)
        velocity_mph = None
        try:
            if all(k in f for k in ("release_x", "release_y", "catch_x", "catch_y",
                                    "frames_between", "ref_px", "ref_inches")):
                velocity_mph = velocity_from_marks(
                    release=(float(f["release_x"]), float(f["release_y"])),
                    catch=(float(f["catch_x"]), float(f["catch_y"])),
                    frames_between=float(f["frames_between"]),
                    fps=fps,
                    ref_px=float(f["ref_px"]),
                    ref_inches=float(f["ref_inches"]),
                )
        except (KeyError, ValueError):
            velocity_mph = None

        # Release frame from the user's ball tap (preferred). Auto-detected as
        # fallback inside the metric function when this is None.
        release_frame = None
        try:
            if "release_frame" in f and f.get("release_frame") != "":
                release_frame = int(float(f["release_frame"]))
        except (KeyError, ValueError):
            release_frame = None

        # Movement-specific mechanical metrics
        metric_fn = MOVEMENTS[movement]["metrics"]
        metrics = metric_fn(frames, fps, height_in=height_in,
                            release_frame=release_frame)

        payload = {
            "movement": movement,
            "fps": fps,
            "frame_count": len(frames),
            "velocity_mph": velocity_mph,
            "metrics": metrics,
            "targets": MOVEMENTS[movement]["targets"],
        }

        # Heavy per-frame landmark data is only included when explicitly asked
        # for (used live for the skeleton overlay, NEVER saved to Supabase).
        # Send include_frames=true in the form to get it.
        if request.form.get("include_frames", "false").lower() == "true":
            payload["frames"] = frames

        return jsonify(payload)
    finally:
        os.unlink(tmp.name)


@app.route("/coach", methods=["POST"])
def coach():
    """OPTIONAL AI coaching summary. Called only when the user taps 'Generate
    coaching summary'. Takes the already-computed metrics JSON and returns a
    short natural-language read across all metrics together.

    Requires ANTHROPIC_API_KEY in the environment (set it in Render's env vars).
    If the key is absent, returns a clear message instead of failing.
    """
    import json as _json
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({
            "summary": None,
            "error": "AI summary unavailable: ANTHROPIC_API_KEY not set on the "
                     "server. Add it in Render > Environment to enable this."
        }), 200

    body = request.get_json(silent=True) or {}
    metrics = body.get("metrics", {})
    movement = body.get("movement", "pitching")
    athlete = body.get("athlete", "the athlete")

    # Build a tightly-scoped prompt with the guardrails baked in.
    items = metrics.get("items", [])
    lines = []
    for it in items:
        lines.append(
            f"- {it['name']}: {it.get('value')} {it.get('unit')} "
            f"(status {it.get('status')}, target {it.get('target')})"
        )
    metric_block = "\n".join(lines) if lines else "(no metrics available)"

    system = (
        "You are helping a parent review youth baseball pitching mechanics from "
        "automated 2D video metrics. Be concise and practical. Hard rules: "
        "(1) The target bands are GENERIC and not yet calibrated to this athlete, "
        "and a 2D side camera compresses some angles, so frame everything as "
        "'if this holds across several pitches.' "
        "(2) Do NOT invent specific drills, rep counts, or biomechanical claims; "
        "where real coaching judgment is needed, say to check with his coach. "
        "(3) No medical or injury claims. "
        "(4) 4-6 sentences max. Note the single most useful thing to watch next."
    )
    user = (
        f"Movement: {movement}. Athlete: {athlete}.\n"
        f"Measured at a release frame the user verified by eye.\n\n"
        f"Metrics:\n{metric_block}\n\n"
        f"Give a short, honest read across these together. What stands out, "
        f"what might be camera/calibration noise, and the one thing to watch "
        f"on the next few pitches."
    )

    req_body = _json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 400,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=req_body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        ).strip()
        return jsonify({"summary": text or "(empty response)", "error": None})
    except Exception as e:
        return jsonify({"summary": None, "error": f"AI request failed: {e}"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
