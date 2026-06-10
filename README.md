# Sport Analyzer Backend

Pose-based mechanics + velocity from a single side-view video.
One engine, multiple movements (pitching built, hitting/kick/fielding stubbed).

## Files
- `app.py` - Flask server, MediaPipe pipeline, `/analyze` endpoint
- `movements.py` - THE file you edit to add sports. Registry at the bottom.
- `geometry.py` - shared angle/distance math
- `velocity.py` - mph from two manual taps + a reference object
- `requirements.txt`, `render.yaml` - deploy config

## Deploy to Render
1. Push this folder to a GitHub repo
2. Render dashboard -> New -> Blueprint -> point at the repo (uses render.yaml)
3. Wait for build. You get a URL like https://sport-analyzer.onrender.com
4. Test: open `https://YOUR-URL/health` in a browser. Should list the movements.

Free tier sleeps after inactivity. First request after idle takes ~30s to wake.

## Test /analyze locally before Render (optional)
```
pip install -r requirements.txt
python app.py
# in another terminal, with one of Kade's clips:
curl -X POST http://localhost:5000/analyze \
  -F "video=@kade_pitch.mov" \
  -F "movement=pitching" \
  -F "height_in=58"
```
Returns JSON with metrics + per-frame landmarks.

## Metrics-only storage (default)
The response does NOT include per-frame landmark data unless you ask for it.
That keeps saved data tiny. Two cases:
- Saving to Supabase: save only velocity + metric values. Tiny, never hits caps.
- Live skeleton replay: send `include_frames=true` to get the landmark array
  for that one session, draw the overlay, and discard it. Never persist it.

Add `-F "include_frames=true"` to a request only when you need the overlay.
Do not store raw video in Supabase either. Keep clips in iCloud/Google; keep
numbers in Supabase.

## How velocity works (read this)
Auto ball-tracking is fragile, so velocity uses TWO MANUAL TAPS from the frontend:
- user taps the ball at release and at the glove (or bat contact)
- frontend sends release_x/y, catch_x/y, frames_between, ref_px, ref_inches
- a known reference object (rubber width = 24in, or any marker) sets the scale

IMPORTANT: tap coords and ref_px must be in the SAME pixel space. Send raw pixel
coordinates from the video element, not normalized 0-1 values, OR normalize both
consistently. Keep them consistent and the math is correct.

If those tap params are missing, the endpoint still returns mechanics with
velocity = null. Mechanics never depend on the taps.

## Adding a movement later
Open `movements.py`:
1. Write `your_metrics(frames, fps, height_in)` returning {"reference_frame": i, "items": [...]}
2. Build each item with `_packaged(name, value, target, unit)`
3. Add it to the `MOVEMENTS` dict at the bottom
Done. app.py and the frontend need no changes; pass `movement=your_key`.

## Reality checks
- Validate provisional target ranges (hitting/kick) against real reps before trusting the color dots
- Lead-side landmarks in pitching assume a handedness; check L vs R for your athlete
- 2D side view makes separation an approximation, but it is consistent session to session, which is what matters for tracking progress
