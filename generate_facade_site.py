"""Write facade_site.html, a view of the three massings and their entrances."""

import json
from pathlib import Path

import apply_facade_massing as skin

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "facade_site.html"

NAMES = ("Dance studio", "Auditorium", "Restaurant")


def wall_record(segment, z0, z1, spec, segment_index, sun):
    length = skin.segment_length(segment)
    count_h = max(1, int(round(length / skin.MODULE)))
    count_v = max(1, int(round((z1 - z0) / skin.MODULE)))
    base = []
    colors = []
    for i in range(count_h + 1):
        h = i / count_h
        normal = skin.outward_at(segment, h)
        base.append(skin.point_on(segment, h, z0, 0.0, normal)[:2])
    for i in range(count_h):
        h = (i + 0.5) / count_h
        normal = skin.outward_at(segment, h)
        incidence = skin.facade.clamp(normal[0] * sun[0] + normal[1] * sun[1], 0.0, 1.0)
        aperture = skin.facade.lerp(skin.APERTURE_MAX, skin.APERTURE_MIN, incidence)
        color = skin.facade.aperture_color(aperture, skin.APERTURE_MIN, skin.APERTURE_MAX)
        column = []
        for j in range(count_v):
            z = z0 + (z1 - z0) * (j + 0.5) / count_v
            entrance = (
                segment_index == spec["segment"]
                and spec["t0"] <= h <= spec["t1"]
                and z <= z0 + spec["height"]
            )
            column.append(None if entrance else list(color))
        colors.append(column)
    entrance = None
    if segment_index == spec["segment"]:
        entrance = {
            "t0": spec["t0"],
            "t1": spec["t1"],
            "height": spec["height"],
            "kind": spec["kind"],
        }
    return {
        "base": [[round(x, 2), round(y, 2)] for x, y in base],
        "colors": colors,
        "z0": round(z0, 2),
        "z1": round(z1, 2),
        "entrance": entrance,
    }


def buildings():
    import rhino3dm

    model = rhino3dm.File3dm.Read(str(skin.SOURCE))
    sun = skin.sun_direction()
    found = []
    index = 0
    for obj in model.Objects:
        geometry = obj.Geometry
        if geometry.ObjectType != rhino3dm.ObjectType.Extrusion:
            continue
        profile = geometry.Profile3d(0, 0.0)
        spec = skin.ENTRANCES[index]
        z0 = geometry.PathStart.Z
        z1 = geometry.PathEnd.Z
        walls = [
            wall_record(profile.SegmentCurve(s), z0, z1, spec, s, sun)
            for s in range(profile.SegmentCount)
        ]
        footprint = []
        for wall in walls:
            footprint.extend(wall["base"][:-1])
        found.append({
            "name": NAMES[index],
            "kind": spec["kind"],
            "z0": round(z0, 2),
            "z1": round(z1, 2),
            "footprint": footprint,
            "walls": walls,
        })
        index += 1
    return found


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Massing facade</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    html, body { margin: 0; height: 100%; background: #070707; color: #f4f1ea; overflow: hidden; font-family: Montserrat, sans-serif; }
    canvas { display: block; width: 100vw; height: 100vh; }
    #title {
      position: absolute; z-index: 2; display: flex; flex-direction: column;
      align-items: flex-start; justify-content: flex-start;
      pointer-events: none; font-family: Montserrat, sans-serif;
      text-align: left; color: #f4f1ea;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.85);
    }
    #title h1 {
      margin: 0; font-family: Montserrat, sans-serif; font-weight: normal;
      font-size: 15px; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0;
    }
    #title p { margin: 6px 0 0; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0; }
    #title .interval {
      margin: 8px 0 0; font-size: 13px; line-height: 1.35;
      letter-spacing: 0.01em; text-transform: none; opacity: 0;
    }
    #write {
      position: absolute; left: 16px; bottom: 16px; z-index: 3;
      font: 11px Montserrat, sans-serif; letter-spacing: 0.14em; text-transform: uppercase;
      background: transparent; color: #f4f1ea; border: 1px solid rgba(255,255,255,0.45);
      padding: 6px 10px; cursor: pointer;
    }
  </style>
</head>
<body>
  <div id="title">
    <h1 id="phase">Phase 01</h1>
    <p id="precinct">Entertainment precinct</p>
    <p id="para1" class="interval">Three leaf pavilions for making, performance, and gathering.</p>
    <p id="para2" class="interval">The studio opens onto the river.</p>
  </div>
  <button type="button" id="write">Without writing</button>
  <canvas id="view"></canvas>
  <script>
    const BUILDINGS = __DATA__;
    const MAP = __MAP__;
    const canvas = document.getElementById("view");
    const ctx = canvas.getContext("2d");
    let wedgeSheet = null;
    let yaw = -0.2, pitch = 1.02, dist = 220;
    let drag = null;
    let writing = true;
    const title = document.getElementById("title");
    document.getElementById("write").addEventListener("click", () => {
      writing = !writing;
      document.getElementById("write").textContent = writing ? "Without writing" : "With writing";
    });

    const pts = [];
    BUILDINGS.forEach(b => b.footprint.forEach(p => pts.push(p)));
    const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    let radius = 20;
    BUILDINGS.forEach(b => b.footprint.forEach(p => {
      radius = Math.max(radius, Math.hypot(p[0] - cx, p[1] - cy), (b.z1 - b.z0) * 0.6);
    }));
    let targetX = MAP.focus[0], targetY = MAP.focus[1];
    const mapSpan = Math.max(MAP.span[0], MAP.span[1]);
    dist = mapSpan * 1.15;

    const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
    function resize() {
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    addEventListener("resize", resize);
    resize();

    canvas.addEventListener("pointerdown", e => { drag = { x: e.clientX, y: e.clientY, yaw, pitch }; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", e => {
      if (!drag) return;
      yaw = drag.yaw + (e.clientX - drag.x) * 0.008;
      pitch = Math.max(0.15, Math.min(1.2, drag.pitch + (e.clientY - drag.y) * 0.006));
    });
    canvas.addEventListener("pointerup", () => { drag = null; });
    canvas.addEventListener("wheel", e => { dist = Math.max(radius * 0.7, Math.min(radius * 8, dist + e.deltaY * 0.35)); e.preventDefault(); }, { passive: false });

    function stageRect() {
      const margin = Math.max(72, Math.min(innerWidth, innerHeight) * 0.08);
      const aspect = 2.35;
      let w = innerWidth - margin * 2;
      let h = w / aspect;
      if (h > innerHeight - margin * 2) {
        h = innerHeight - margin * 2;
        w = h * aspect;
      }
      return { x: (innerWidth - w) / 2, y: (innerHeight - h) / 2, w, h };
    }

    let cam = null;
    function beginFrame() {
      const stage = stageRect();
      const yawC = Math.cos(yaw), yawS = Math.sin(yaw);
      const pitchC = Math.cos(pitch), pitchS = Math.sin(pitch);
      cam = { stage, yawC, yawS, pitchC, pitchS, scale: stage.w / dist };
    }

    function project(x, y, z) {
      const dx = x - targetX, dy = y - targetY;
      const rx = dx * cam.yawC - dy * cam.yawS;
      const ry = dx * cam.yawS + dy * cam.yawC;
      const z2 = ry * cam.pitchS + z * cam.pitchC;
      const s = cam.scale;
      const anchorY = 0.52 + Math.max(0, pitch - 0.72) * 0.12;
      const screenY = cam.stage.y + cam.stage.h * anchorY - (ry * cam.pitchC + z * cam.pitchS) * s;
      return [cam.stage.x + cam.stage.w / 2 + rx * s, screenY, z2];
    }

    function quad(a, b, c, d, fill) {
      const p = [a, b, c, d].map(v => project(v[0], v[1], v[2]));
      ctx.beginPath();
      ctx.moveTo(p[0][0], p[0][1]);
      for (let i = 1; i < 4; i++) ctx.lineTo(p[i][0], p[i][1]);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
    }

    const leaves = [];
    (function seedLeaves() {
      let seed = 11;
      function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
      const tones = ["#6e8a52", "#4f6a3a", "#8aa06a", "#3f5530"];
      for (let i = 0; i < 36; i++) {
        leaves.push({
          u: rnd(), v: rnd(),
          speed: 0.018 + rnd() * 0.028,
          bob: 0.015 + rnd() * 0.03,
          spin: rnd() * Math.PI * 2,
          spinV: 0.6 + rnd() * 1.4,
          size: 4 + rnd() * 6,
          tone: tones[i % tones.length]
        });
      }
    })();

    function drawLeaf(x, y, angle, size, tone) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(0, -size);
      ctx.quadraticCurveTo(size * 0.55, -size * 0.15, 0, size * 0.85);
      ctx.quadraticCurveTo(-size * 0.55, -size * 0.15, 0, -size);
      ctx.fillStyle = tone;
      ctx.fill();
      ctx.restore();
    }

    function drawLeaves(stage, t, color) {
      const cx = stage.x + stage.w / 2;
      const cy = stage.y + stage.h / 2;
      ctx.save();
      leaves.slice(0, 11).forEach((leaf, i) => {
        const fall = ease((t - i * 0.16) / 1.7);
        if (fall <= 0 || fall >= 1) return;
        const x = cx + (leaf.u - 0.5) * stage.w * 0.18 * (1 - fall * 0.85);
        const y = stage.y - 12 + (cy - stage.y + 12) * fall;
        ctx.globalAlpha = fall < 0.86 ? 0.92 : (1 - fall) / 0.14;
        drawLeaf(x, y, leaf.spin + t * 2.2, leaf.size * (1.1 - fall * 0.25), leaf.tone);
      });
      ctx.restore();
    }

    function rippleRadius(stage, spread) {
      return Math.hypot(innerWidth, innerHeight) * 0.72 * spread;
    }

    function drawRipples(spread, t) {
      if (spread <= 0.01 || spread >= 0.992) return;
      const frame = printFrame();
      const cx = frame.mx + frame.mw / 2;
      const cy = frame.my + frame.mh / 2;
      const maxR = Math.hypot(frame.mw, frame.mh) * 0.52;
      const warp = Math.max(0, 1 - Math.max(0, spread - 0.62) / 0.34);
      ctx.save();
      for (let i = 0; i < 6; i++) {
        const ring = spread - i * 0.11;
        if (ring <= 0.02) continue;
        const rr = maxR * Math.min(1, ring);
        ctx.beginPath();
        for (let a = 0; a <= 72; a++) {
          const ang = (a / 72) * Math.PI * 2;
          const wobble = 1 + warp * (0.055 * Math.sin(ang * 4 + t * 1.6 + i) + 0.028 * Math.sin(ang * 9 - t * 2.1));
          const x = cx + Math.cos(ang) * rr * wobble;
          const y = cy + Math.sin(ang) * rr * wobble;
          if (a === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = "rgba(150, 186, 190, " + (0.42 - i * 0.05) * Math.min(1, spread * 2) + ")";
        ctx.lineWidth = i === 0 ? 1.6 : 1;
        ctx.stroke();
      }
      ctx.restore();
    }

    function paintLine(points, amount, close) {
      if (!points || points.length < 2 || amount <= 0.001) return;
      const n = points.length;
      const count = close ? n : n - 1;
      let total = 0;
      const seg = [];
      for (let i = 0; i < count; i++) {
        const a = points[i], b = points[(i + 1) % n];
        const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 0.001;
        seg.push(len);
        total += len;
      }
      let budget = total * Math.min(1, amount);
      ctx.beginPath();
      const p0 = project(points[0][0], points[0][1], 0);
      ctx.moveTo(p0[0], p0[1]);
      for (let i = 0; i < count && budget > 0; i++) {
        const a = points[i], b = points[(i + 1) % n];
        const u = Math.min(1, budget / seg[i]);
        const p = project(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 0);
        ctx.lineTo(p[0], p[1]);
        budget -= seg[i];
      }
      ctx.stroke();
    }

    function paintScheme(paint, hideOutlines) {
      const lines = MAP.lines || [];
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.strokeStyle = "#d7e6dc";
      lines.forEach((line, i) => {
        if (line.w < 1.1) return;
        const start = (i / Math.max(1, lines.length)) * 0.45;
        ctx.globalAlpha = 1;
        ctx.lineWidth = line.w;
        paintLine(line.pts, (paint - start) / 0.4, !!line.close);
      });
      const keep = ctx.globalAlpha * (1 - Math.min(1, hideOutlines || 0));
      if (keep > 0.02) {
        ctx.globalAlpha = keep;
        BUILDINGS.forEach((b, i) => {
          const start = 0.55 + i * 0.08;
          ctx.lineWidth = 1.35;
          paintLine(b.footprint, (paint - start) / 0.4, true);
        });
      }
    }

    function strokeBank(points) {
      if (points.length < 2) return;
      ctx.beginPath();
      points.forEach((pt, i) => {
        const p = project(pt[0], pt[1], 0);
        if (i === 0) ctx.moveTo(p[0], p[1]);
        else ctx.lineTo(p[0], p[1]);
      });
      ctx.stroke();
    }

    function poly(points, fill) {
      if (points.length < 3) return;
      ctx.beginPath();
      const p0 = project(points[0][0], points[0][1], 0);
      ctx.moveTo(p0[0], p0[1]);
      for (let i = 1; i < points.length; i++) {
        const p = project(points[i][0], points[i][1], 0);
        ctx.lineTo(p[0], p[1]);
      }
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
    }

    const printImg = new Image();
    let printMask = null;
    printImg.onload = () => {
      const sheet = document.createElement("canvas");
      sheet.width = printImg.naturalWidth;
      sheet.height = printImg.naturalHeight;
      const g = sheet.getContext("2d", { willReadFrequently: true });
      g.drawImage(printImg, 0, 0);
      const data = g.getImageData(0, 0, sheet.width, sheet.height);
      const px = data.data;
      const cutX = sheet.width * 0.8;
      const cutY = sheet.height * 0.18;
      for (let y = 0; y < sheet.height; y++) {
        for (let x = 0; x < sheet.width; x++) {
          const i = (y * sheet.width + x) * 4;
          if (x > cutX && y < cutY) {
            px[i + 3] = 0;
            continue;
          }
          const lit = px[i + 2] / 255;
          const a = Math.max(0, Math.min(1, (lit - 0.08) / 0.45));
          px[i] = 255;
          px[i + 1] = 255;
          px[i + 2] = 255;
          px[i + 3] = Math.round(a * 255);
        }
      }
      g.putImageData(data, 0, 0);
      printMask = sheet;
    };
    printImg.src = "print_mask.png";
    const schemeImg = new Image();
    let planSample = null;
    let schemeReady = false;
    schemeImg.onload = () => { schemeReady = true; };
    schemeImg.src = "urban_plan.png";

    function note(x, y, title, sub) {
      ctx.font = "13px Montserrat, sans-serif";
      ctx.fillText(title, x, y);
      if (!sub) return;
      ctx.font = "italic 11px Montserrat, sans-serif";
      ctx.fillText(sub, x, y + 18);
    }

    function printFrame() {
      const fit = Math.min(innerWidth / 1024, innerHeight / 561) * 0.86;
      const mw = 1024 * fit, mh = 561 * fit;
      const mx = (innerWidth - mw) / 2 - mw * 0.07;
      const my = (innerHeight - mh) / 2;
      return { fit, mw, mh, mx, my };
    }

    let bleedCanvas = null;
    function applyPrint(bleed) {
      if (!printMask) return;
      const frame = printFrame();
      const w = frame.mw, h = frame.mh, x = frame.mx, y = frame.my;
      if (!bleedCanvas) bleedCanvas = document.createElement("canvas");
      if (bleedCanvas.width !== innerWidth || bleedCanvas.height !== innerHeight) {
        bleedCanvas.width = innerWidth;
        bleedCanvas.height = innerHeight;
      }
      const b = bleedCanvas.getContext("2d");
      b.clearRect(0, 0, innerWidth, innerHeight);
      b.drawImage(printMask, x, y, w, h);
      if (bleed > 0.001) {
        b.fillStyle = "#fff";
        const rows = 6;
        for (let i = 0; i < rows; i++) {
          const u = Math.max(0, Math.min(1, (bleed - i * 0.07) / 0.62));
          if (u <= 0) continue;
          const eased = u * u * (3 - 2 * u);
          const bh = h / rows;
          const by = y + i * bh;
          const slide = eased * w * (0.22 + (i % 3) * 0.08);
          if (i % 2 === 0) b.fillRect(x - slide, by, w + slide, bh + 1);
          else b.fillRect(x, by, w + slide, bh + 1);
        }
        const cols = 5;
        for (let i = 0; i < cols; i++) {
          const u = Math.max(0, Math.min(1, (bleed - 0.16 - i * 0.06) / 0.58));
          if (u <= 0) continue;
          const eased = u * u * (3 - 2 * u);
          const bw = w / cols;
          const bx = x + i * bw;
          const slide = eased * h * (0.2 + (i % 3) * 0.07);
          if (i % 2 === 0) b.fillRect(bx, y - slide, bw + 1, h + slide);
          else b.fillRect(bx, y, bw + 1, h + slide);
        }
      }
      ctx.save();
      ctx.globalCompositeOperation = "destination-in";
      ctx.drawImage(bleedCanvas, 0, 0);
      ctx.restore();
    }

    function shadowBox() {
      ctx.fillStyle = "#070707";
      ctx.fillRect(0, 0, innerWidth, innerHeight);
    }

    function outward(a, b) {
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const len = Math.hypot(dx, dy) || 1;
      return [dy / len, -dx / len];
    }

    function drawFins(foot, z0, z1, wave, doorEdge, opening) {
      const n = foot.length;
      let area = 0;
      for (let i = 0; i < n; i++) {
        const p = foot[i], q = foot[(i + 1) % n];
        area += p[0] * q[1] - q[0] * p[1];
      }
      const flip = area < 0 ? -1 : 1;
      const faces = [];
      for (let i = 0; i < n; i++) {
        const u = i / n;
        if (doorEdge >= 0 && opening > 0.2) {
          const d = Math.abs(i - doorEdge);
          if (Math.min(d, n - d) < 4) continue;
        }
        const grow = ease((wave - u * 0.7) / 0.3);
        if (grow <= 0.01) continue;
        const a = foot[i], b = foot[(i + 1) % n];
        const stations = (i === doorEdge && opening > 0) ? [0.5 - 0.22 * opening, 0.5 + 0.22 * opening] : [0.5];
        stations.forEach(along => {
        const mx = a[0] + (b[0] - a[0]) * along, my = a[1] + (b[1] - a[1]) * along;
        let [nx, ny] = outward(a, b);
        nx *= flip; ny *= flip;
        const sun = Math.max(0, -ny);
        const ripple = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(u * Math.PI * 6 + wave * 2));
        const relief = 0.45 + 0.55 * Math.sin(u * Math.PI * 3.5 + wave * 2.4);
        const h = z0 + (z1 - z0) * grow * (0.45 + 0.55 * ripple);
        const depth = (0.55 + relief * 1.35) * grow;
        const lookX = Math.sin(yaw), lookY = Math.cos(yaw);
        const slices = 5;
        for (let s = 0; s < slices; s++) {
          const u0 = s / slices, u1 = (s + 1) / slices;
          const bulge0 = Math.sin(u0 * Math.PI);
          const bulge1 = Math.sin(u1 * Math.PI);
          const d0 = depth * (0.18 + 0.82 * bulge0 * relief);
          const d1 = depth * (0.18 + 0.82 * bulge1 * relief);
          const zA = z0 + (h - z0) * u0;
          const zB = z0 + (h - z0) * u1;
          const catchLight = Math.max(0, nx * lookX + ny * lookY);
          const lit = Math.min(1, 0.28 + catchLight * 0.9 + bulge0 * 0.22);
          const tone = sun > 0.35
            ? "rgb(" + Math.round(168 + lit * 26) + "," + Math.round(170 + lit * 26) + "," + Math.round(166 + lit * 22) + ")"
            : "rgb(" + Math.round(132 + lit * 22) + "," + Math.round(136 + lit * 22) + "," + Math.round(134 + lit * 20) + ")";
          faces.push([project(mx + nx * (d0 + d1) * 0.5, my + ny * (d0 + d1) * 0.5, (zA + zB) / 2)[2], [
            [mx, my, zA],
            [mx + nx * d0, my + ny * d0, zA],
            [mx + nx * d1, my + ny * d1, zB],
            [mx, my, zB],
            tone
          ]]);
        }
        });
      }
      return faces;
    }

    function draw(color, wave, zoom, t, opening, descend) {
      beginFrame();
      const stage = cam.stage;
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      shadowBox();
      ctx.save();
      ctx.save();
      const frame0 = printFrame();
      const originX = frame0.mx + frame0.mw / 2;
      const originY = frame0.my + frame0.mh / 2;
      const spillFar = Math.hypot(frame0.mw, frame0.mh) * 0.52;
      const spread = ease(Math.min(1, Math.max(0, (t - 0.4) / 8)));
      const plan = ease(Math.max(0, Math.min(1, (t - 104.2) / 18)));
      const still = ease(Math.max(0, Math.min(1, (t - 99.2) / 0.5))) * (1 - ease(Math.max(0, Math.min(1, (t - 101.6) / 0.9))));
      const facade = ease(Math.max(0, Math.min(1, (t - 68) / 4)));
      const widen = ease(Math.max(0, Math.min(1, (t - 62.5) / 5)));
      const reveal = ease(Math.max(0, Math.min(1, (t - 93) / 5)));
      const spillR = Math.max(1, spillFar * spread);
      if (spread < 0.995) {
        ctx.beginPath();
        ctx.arc(originX, originY, spillR, 0, Math.PI * 2);
        ctx.clip();
      }
      if (spread > 0.02) {
        ctx.globalAlpha = 1 - still;
        ctx.fillStyle = "#0c1822";
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        const pool = ctx.createRadialGradient(originX, originY, 0, originX, originY, spillR * 0.72);
        pool.addColorStop(0, "rgba(44, 100, 128, " + (0.28 * Math.min(1, spread * 2)) + ")");
        pool.addColorStop(1, "rgba(44, 100, 128, 0)");
        ctx.fillStyle = pool;
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        ctx.globalAlpha = 1;
      }
      const paint = ease(Math.max(0, Math.min(1, (t - 3.0) / 5.6)));
      const replace = ease(Math.max(0, Math.min(1, (t - 9.8) / 3.4)));
      const quiet = ease(Math.max(0, Math.min(1, (t - 33.4) / 1.6))) * (1 - ease(Math.max(0, Math.min(1, (t - 38.2) / 2.2))));
      if (color > 0.01) {
        ctx.save();
        ctx.globalAlpha = color * (0.16 + 0.84 * zoom) * (1 - quiet * 0.94) * (1 - still);
        const ground = ctx.createLinearGradient(stage.x, stage.y, stage.x, stage.y + stage.h);
        ground.addColorStop(0, "#0c1822");
        ground.addColorStop(1, "#0e1c2c");
        ctx.fillStyle = ground;
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        ctx.restore();
      }
      let openingChannel = null;
      const earlyCut = 1 - ease(Math.max(0, Math.min(1, (t - 16) / 4)));
      const riverShow = Math.max(color, paint, earlyCut) * (1 - descend * 0.8) * (1 - facade) * (1 - still);
      if (MAP.river.length > 2 && riverShow > 0.02) {
        const spanBank = (bank) => {
          if (!bank || bank.length < 2) return bank || [];
          const reach = Math.max(dist, 400) * 3.2;
          const push = (tip, inner) => {
            const dx = tip[0] - inner[0], dy = tip[1] - inner[1];
            const len = Math.hypot(dx, dy) || 1;
            return [tip[0] + dx / len * reach, tip[1] + dy / len * reach];
          };
          return [push(bank[0], bank[Math.min(8, bank.length - 1)]), ...bank, push(bank[bank.length - 1], bank[Math.max(0, bank.length - 9)])];
        };
        const south = spanBank(MAP.banks && MAP.banks[0]);
        const north = spanBank(MAP.banks && MAP.banks[1]);
        const channel = south.length > 2 && north.length > 2 ? south.concat(north.slice().reverse()) : MAP.river;
        openingChannel = channel;
        ctx.save();
        ctx.globalAlpha = riverShow;
        poly(channel, "#1a3d66");
        ctx.beginPath();
        channel.forEach((pt, i) => {
          const p = project(pt[0], pt[1], 0);
          if (i === 0) ctx.moveTo(p[0], p[1]);
          else ctx.lineTo(p[0], p[1]);
        });
        ctx.closePath();
        ctx.clip();
        const surge = 0.5 + 0.5 * Math.sin(t * 1.15);
        const pinch = (u, v) => {
          const sheet = Math.sin(u * Math.PI * 4.2 - t * 1.1) * Math.cos(v * Math.PI * 2.8 + t * 0.36);
          const fold = Math.sin(u * 8.4 + v * 5.5 - t * 0.85);
          return sheet * 0.7 + fold * 0.4;
        };
        const x0 = cam.stage.x, y0 = cam.stage.y, sw = cam.stage.w, sh = cam.stage.h;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        const lanes = 16;
        for (let n = 0; n < lanes; n++) {
          const v = (n + 0.5) / lanes;
          ctx.beginPath();
          for (let s = 0; s <= 64; s++) {
            const u = s / 64;
            const w = pinch(u, v);
            const x = x0 + u * sw;
            const y = y0 + (v + w * 0.045) * sh;
            if (s === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          const crest = 0.4 + 0.6 * Math.abs(pinch(0.2, v));
          ctx.strokeStyle = crest > 0.66 ? "#f4fbff" : "#8ecae4";
          ctx.globalAlpha = riverShow * (0.7 + surge * 0.25) * crest;
          ctx.lineWidth = 1.05 + crest * 1.45;
          ctx.stroke();
        }
        const wefts = 20;
        for (let n = 0; n < wefts; n++) {
          const u = (n + 0.5) / wefts;
          ctx.beginPath();
          for (let s = 0; s <= 28; s++) {
            const v = s / 28;
            const w = pinch(u, v);
            const x = x0 + (u + w * 0.03) * sw;
            const y = y0 + v * sh;
            if (s === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.strokeStyle = "#d7eef8";
          ctx.globalAlpha = riverShow * (0.4 + surge * 0.28);
          ctx.lineWidth = 0.85;
          ctx.stroke();
        }
        ctx.restore();
      }
      if (color > 0.01) {
        ctx.save();
        const sunIn = ease(Math.max(0, Math.min(1, (t - 34.2) / 1.2)));
        ctx.globalAlpha = color * (0.16 + sunIn * 0.55) * (1 - descend) * (1 - facade) * (1 - quiet) * (1 - still);
        ctx.strokeStyle = sunIn > 0.2 ? "#d5e4ea" : "#1e4a3c";
        ctx.lineWidth = 0.7 + sunIn * 0.55;
        (MAP.contours || []).forEach((c, i) => {
          if (i !== 0 && i !== 2) return;
          const inland = sunIn * (i === 0 ? 18 : 32);
          strokeBank(c.map(p => [p[0], p[1] - inland]));
        });
        ctx.globalAlpha = color * 0.85 * (1 - descend) * (1 - facade) * (1 - quiet) * (1 - still);
        ctx.strokeStyle = "#c9ddd2";
        ctx.lineWidth = 1.35;
        if (MAP.site) strokeBank(MAP.site);
        ctx.restore();
      }
      if (paint > 0.01) {
        const scan = ease(Math.max(0, Math.min(1, (t - 17.4) / 3.2)));
        ctx.save();
        ctx.globalAlpha = 0.9 * (1 - descend * 0.75) * (1 - facade) * (1 - scan);
        paintScheme(paint, Math.max(color, replace));
        ctx.restore();
      }
      const mass = Math.max(color, replace);
      if (mass > 0.04) {
        ctx.save();
        ctx.globalAlpha = Math.min(1, mass);
        const faces = [];
        BUILDINGS.forEach((b, bi) => {
          const lift = 0.15 + 0.85 * Math.min(1, wave * 1.4);
          const top = b.z0 + (b.z1 - b.z0) * (0.22 + 0.78 * lift);
          const isDoor = bi === DOOR.index && opening > 0.01;
          const span = 4 + Math.round(widen * 2);
          const count = b.footprint.length;
          const nearDoor = (i) => {
            const d = Math.abs(i - DOOR.edge);
            return Math.min(d, count - d);
          };
          for (let i = 0; i < count; i++) {
            const a = b.footprint[i], c = b.footprint[(i + 1) % count];
            const u = i / count;
            const waveTop = top * (0.86 + 0.14 * Math.sin(u * Math.PI * 4 + wave * 5));
            const depth = (project(a[0], a[1], b.z0)[2] + project(c[0], c[1], waveTop)[2]) / 2;
            if (isDoor && nearDoor(i) <= span) {
              const sill = b.z0 + (waveTop - b.z0) * Math.min(1, opening * 1.05);
              faces.push([depth, [[a[0], a[1], sill], [c[0], c[1], sill], [c[0], c[1], waveTop], [a[0], a[1], waveTop], "#f3efe8"]]);
              if (i === DOOR.edge && sill > b.z0 + 0.4) {
                const left = b.footprint[(DOOR.edge - span + count) % count];
                const right = b.footprint[(DOOR.edge + span + 1) % count];
                const doorH = sill;
                const nx = DOOR.nx, ny = DOOR.ny;
                const at = (u, z, depth) => {
                  const x = left[0] + (right[0] - left[0]) * u - nx * depth;
                  const y = left[1] + (right[1] - left[1]) * u - ny * depth;
                  return [x, y, z];
                };
                const push = (u0, u1, z0b, z1b, depth, tone, bias) => {
                  const quadPts = [at(u0, z0b, depth), at(u1, z0b, depth), at(u1, z1b, depth), at(u0, z1b, depth)];
                  const mid = at((u0 + u1) / 2, (z0b + z1b) / 2, depth);
                  faces.push([project(mid[0], mid[1], mid[2])[2] + bias, quadPts.concat([tone])]);
                };
                const pales = ["#f0d2a4", "#e39a4a", "#f6e2c4", "#c9843a", "#edd0a2"];
                push(0, 1, b.z0, doorH, 2.8, "#f3e0c4", 0.8);
                const slats = 34;
                for (let c = 0; c < slats; c++) {
                  const u0 = 0.015 + c * (0.97 / slats);
                  const u1 = u0 + 0.97 / slats * 0.72;
                  push(u0, u1, b.z0 + 0.08, doorH - 0.04, 1.05 + (c % 3) * 0.18, pales[c % pales.length], -0.15);
                }
                const ribs = 7;
                for (let c = 0; c < ribs; c++) {
                  const u0 = 0.08 + c * (0.84 / ribs);
                  const u1 = u0 + 0.045;
                  push(u0, u1, b.z0, doorH * 0.98, 8 + c * 1.1, pales[c % pales.length], -0.4);
                }
                push(0.06, 0.94, doorH * 0.9, doorH * 0.98, 14, "#f6e2c4", -0.8);
              }
            } else {
              faces.push([depth, [[a[0], a[1], b.z0], [c[0], c[1], b.z0], [c[0], c[1], waveTop], [a[0], a[1], waveTop], "#f3efe8"]]);
            }
          }
          const mid = b.footprint.reduce((s, p) => [s[0] + p[0] / b.footprint.length, s[1] + p[1] / b.footprint.length], [0, 0]);
          faces.push([project(mid[0], mid[1], top)[2] - 0.4, null, b.footprint, top, "#fffcf7"]);
          if (wave > 0.01) faces.push(...drawFins(b.footprint, b.z0, b.z1, wave, isDoor ? DOOR.edge : -1, isDoor ? opening : 0));
        });
        faces.sort((a, b) => b[0] - a[0]);
        faces.forEach(face => {
          if (face[1]) quad(face[1][0], face[1][1], face[1][2], face[1][3], face[1][4]);
          else {
            ctx.beginPath();
            face[2].forEach((pt, i) => {
              const und = face[3] * (0.9 + 0.1 * Math.sin(i * 0.7 + wave * 4));
              const p = project(pt[0], pt[1], und);
              if (i === 0) ctx.moveTo(p[0], p[1]);
              else ctx.lineTo(p[0], p[1]);
            });
            ctx.closePath();
            ctx.fillStyle = face[4];
            ctx.fill();
            ctx.strokeStyle = "rgba(176, 172, 164, 0.75)";
            ctx.lineWidth = 1.4;
            ctx.stroke();
          }
        });
        ctx.restore();
      }
      ctx.restore();
      const drawPulse = (amount, reach) => {
        if (amount < 0.02) return;
        const front = 22 + reach * 168;
        ctx.save();
        ctx.lineJoin = "round";
        for (let i = 1; i <= 5; i++) {
          const rad = front * (i / 5);
          const lead = i === 5;
          ctx.beginPath();
          for (let a = 0; a <= 72; a++) {
            const ang = (a / 72) * Math.PI * 2;
            const bow = 1 + 0.045 * Math.sin(ang * 3 + i);
            const p = project(cx + Math.cos(ang) * rad * bow, cy + Math.sin(ang) * rad * 0.58 * bow, 0.2);
            if (a === 0) ctx.moveTo(p[0], p[1]);
            else ctx.lineTo(p[0], p[1]);
          }
          ctx.closePath();
          ctx.strokeStyle = lead ? "#f4fbff" : "#7ec8ea";
          ctx.globalAlpha = amount * (lead ? 0.9 : 0.22 + (i / 5) * 0.2);
          ctx.lineWidth = lead ? 1.7 : 0.65;
          ctx.stroke();
        }
        ctx.restore();
      };
      const pulseIn = ease(Math.max(0, Math.min(1, (t - 14.4) / 0.35)));
      const pulseOut = ease(Math.max(0, Math.min(1, (t - 16.8) / 1.4)));
      const pulse = pulseIn * (1 - pulseOut);
      drawPulse(pulse, ease(Math.max(0, Math.min(1, (t - 14.4) / 2.2))));
      const returnIn = ease(Math.max(0, Math.min(1, (t - 96.4) / 0.4)));
      const returnOut = ease(Math.max(0, Math.min(1, (t - 99.6) / 1.1)));
      const returnPulse = returnIn * (1 - returnOut) * (1 - plan);
      drawPulse(returnPulse, ease(Math.max(0, Math.min(1, (t - 96.4) / 2.6))));
      if (spread > 0.02 && spread < 0.995) {
        const edge = spillR;
        const feather = ctx.createRadialGradient(originX, originY, edge * 0.82, originX, originY, edge);
        feather.addColorStop(0, "rgba(17,17,17,0)");
        feather.addColorStop(1, "rgba(17,17,17,1)");
        ctx.fillStyle = feather;
        ctx.beginPath();
        ctx.arc(originX, originY, edge, 0, Math.PI * 2);
        ctx.fill();
      }
      drawRipples(spread, t);
      const treeGrow = ease(Math.max(0, Math.min(1, (t - 93.2) / 3.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 99.4) / 1.6))));
      if (treeGrow > 0.02 && plan < 0.85) {
        const groves = [[30, 72], [12, 90], [-18, 76], [46, 98], [-52, 68], [22, 108]];
        ctx.save();
        ctx.globalAlpha = Math.min(1, treeGrow * 1.2);
        groves.forEach((p, i) => {
          const h = (5.5 + (i % 3) * 2.2) * treeGrow;
          const crown = 3.2 + (i % 2) * 1.4;
          quad([p[0] - 0.35, p[1], 0], [p[0] + 0.35, p[1], 0], [p[0] + 0.35, p[1], h * 0.55], [p[0] - 0.35, p[1], h * 0.55], "#6a5a42");
          const ring = [];
          for (let a = 0; a < 14; a++) {
            const ang = (a / 14) * Math.PI * 2;
            ring.push([p[0] + Math.cos(ang) * crown, p[1] + Math.sin(ang) * crown * 0.7]);
          }
          for (let k = 1; k < ring.length - 1; k++) {
            quad([ring[0][0], ring[0][1], h], [ring[k][0], ring[k][1], h], [ring[k + 1][0], ring[k + 1][1], h], [ring[0][0], ring[0][1], h], i % 2 ? "#7d9a58" : "#4f6a3a");
          }
        });
        ctx.restore();
      }
      const enterLeaves = 1 - ease(Math.max(0, Math.min(1, (t - 66.8) / 1.6)));
      if (plan < 0.98 && enterLeaves > 0.02) drawLeaves(stage, Math.max(0, t - 9), color * (1 - plan) * enterLeaves * (1 - quiet * 0.9));
      const roadsIn = ease(Math.max(0, Math.min(1, (t - 101.4) / 1.8))) * (1 - ease(Math.max(0, Math.min(1, (t - 104.2) / 0.8))));
      if (roadsIn > 0.02 && MAP.roads) {
        ctx.save();
        ctx.globalAlpha = roadsIn;
        ctx.fillStyle = "#070707";
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = "#f7f7f5";
        ctx.lineWidth = 1.05;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        const stream = ease(Math.max(0, Math.min(1, (t - 101.4) / 1.8)));
        MAP.roads.forEach((pts, i) => {
          const start = (i / MAP.roads.length) * 0.35;
          paintLine(pts, (stream - start) / 0.65, false);
        });
        if (MAP.rail) {
          ctx.strokeStyle = "#f2d15a";
          ctx.lineWidth = 2.1;
          MAP.rail.forEach((pts, i) => {
            const start = 0.15 + (i / MAP.rail.length) * 0.2;
            paintLine(pts, (stream - start) / 0.7, false);
          });
          const track = MAP.rail.reduce((a, b) => b.length > a.length ? b : a);
          if (track && track.length > 2) {
            const head = stream;
            const tail = Math.max(0, head - 0.04);
            ctx.strokeStyle = "#fff6c8";
            ctx.lineWidth = 3.4;
            ctx.beginPath();
            let moved = false;
            for (let i = 0; i < track.length; i++) {
              const u = i / (track.length - 1);
              if (u < tail || u > head) continue;
              const p = project(track[i][0], track[i][1], 0);
              if (!moved) { ctx.moveTo(p[0], p[1]); moved = true; }
              else ctx.lineTo(p[0], p[1]);
            }
            ctx.stroke();
            const hi = Math.min(track.length - 1, Math.round(head * (track.length - 1)));
            const hp = project(track[hi][0], track[hi][1], 0);
            ctx.fillStyle = "#fff6c8";
            ctx.beginPath();
            ctx.arc(hp[0], hp[1], 3.2, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.restore();
      }
      if (plan > 0.02 && schemeReady) {
        ctx.save();
        const nw = schemeImg.naturalWidth || 1024, nh = schemeImg.naturalHeight || 723;
        const frame = printFrame();
        const mw = frame.mw, mh = frame.mh, mx = frame.mx, my = frame.my;
        const cover = Math.max(mw / nw, mh / nh) * 1.35;
        const to02 = ease(Math.max(0, Math.min(1, (t - 122.2) / 1.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 124.4) / 1.0))));
        const to03 = ease(Math.max(0, Math.min(1, (t - 125.6) / 1.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 128.0) / 1.0))));
        const toSun = ease(Math.max(0, Math.min(1, (t - 129.2) / 1.4)));
        const rest = Math.max(0, 1 - to02 - to03 - toSun);
        const sum = rest + to02 + to03 + toSun;
        const fx = (580.4 * rest + 455 * to02 + 730 * to03 + 662 * toSun) / sum;
        const fy = (425.5 * rest + 412 * to02 + 445 * to03 + 426 * toSun) / sum;
        const viewCover = cover * (rest + 2.25 * to02 + 2.25 * to03 + 1.2 * toSun) / sum;
        const dw = nw * viewCover, dh = nh * viewCover;
        const dx = mx + mw / 2 - fx * viewCover;
        const dy = my + mh / 2 - fy * viewCover;
        const bleed = ease(Math.max(0, Math.min(1, (t - 104.2) / 22))) * (1 - ease(Math.max(0, Math.min(1, (t - 136) / 7.2))));
        const slideX = bleed * mw * 0.46;
        const slideY = bleed * mh * 0.42;
        ctx.beginPath();
        ctx.rect(mx - slideX, my - slideY, mw + slideX * 2, mh + slideY * 2);
        ctx.clip();
        ctx.globalAlpha = plan;
        ctx.drawImage(schemeImg, dx, dy, dw, dh);
        ctx.globalAlpha = plan * 0.38;
        ctx.fillStyle = "#06140f";
        ctx.fillRect(mx - slideX, my - slideY, mw + slideX * 2, mh + slideY * 2);
        const atImg = (px, py) => [dx + px * viewCover, dy + py * viewCover];
        const lift = (px, py, rw, rh, alpha) => {
          if (alpha < 0.02) return;
          const s = atImg(px, py);
          const glow = ctx.createRadialGradient(s[0], s[1], 0, s[0], s[1], Math.max(rw, rh) * viewCover);
          glow.addColorStop(0, "rgba(244, 241, 234, " + alpha + ")");
          glow.addColorStop(1, "rgba(244, 241, 234, 0)");
          ctx.fillStyle = glow;
          ctx.beginPath();
          ctx.ellipse(s[0], s[1], rw * viewCover, rh * viewCover, 0, 0, Math.PI * 2);
          ctx.fill();
        };
        const sweep = ease(Math.max(0, Math.min(1, (t - 108) / 2.8)));
        const sweepA = ease(Math.max(0, Math.min(1, (t - 108) / 0.6))) * (1 - ease(Math.max(0, Math.min(1, (t - 110.6) / 1.1))));
        const phase2 = ease(Math.max(0, Math.min(1, (t - 111.4) / 1.6)));
        const phase3 = ease(Math.max(0, Math.min(1, (t - 118.2) / 1.8)));
        const cloudSoon = ease(Math.max(0, Math.min(1, (t - 136) / 3.4)));
        lift(580, 426, 48, 28, sweepA * 0.22 * plan);
        const p2scale = 1 - phase3 * 0.28 * (1 - to02);
        const p2wide = 1 + to02 * 0.72;
        const boxes = [];
        if (sweep > 0.35) boxes.push({ x0: 532, y0: 388, x1: 632, y1: 470, hot: Math.max(0.35, sweepA), tone: "#f7f4ee" });
        if (phase2 > 0.08) {
          const cx = 455 - 36 * phase3 * (1 - to02);
          const cy = 412.5;
          const hx = 65 * p2scale * p2wide;
          const hy = 57.5 * p2scale;
          boxes.push({ x0: cx - hx, y0: cy - hy, x1: cx + hx, y1: cy + hy, hot: Math.max(0.4, to02), tone: "#f3e2c4" });
        }
        if (toSun > 0.08) boxes.push({ x0: 624, y0: 392, x1: 708, y1: 468, hot: toSun, tone: "#ffffff" });
        if (phase3 > 0.08) {
          const p3scale = 0.62 + 0.38 * phase3;
          const cx = 730 + 22 * (1 - phase3);
          const cy = 445;
          const hx = 118 * p3scale;
          const hy = 55 * p3scale;
          boxes.push({ x0: cx - hx, y0: cy - hy, x1: cx + hx, y1: cy + hy, hot: Math.max(0.4, to03), tone: "#e7b15a" });
        }
        if (boxes.length && cloudSoon < 0.98) {
          ctx.save();
          ctx.globalAlpha = (0.42 + 0.28 * Math.max(phase2, phase3, toSun)) * (1 - cloudSoon) * plan;
          ctx.fillStyle = "#020806";
          ctx.beginPath();
          ctx.rect(mx - slideX, my - slideY, mw + slideX * 2, mh + slideY * 2);
          boxes.forEach(box => {
            const a = atImg(box.x0, box.y0), b = atImg(box.x1, box.y1);
            ctx.rect(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]));
          });
          ctx.fill("evenodd");
          ctx.lineWidth = 2.6;
          boxes.forEach(box => {
            const a = atImg(box.x0, box.y0), b = atImg(box.x1, box.y1);
            ctx.globalAlpha = (0.45 + 0.55 * box.hot) * (1 - cloudSoon) * plan;
            ctx.strokeStyle = box.tone;
            ctx.strokeRect(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]));
          });
          if (boxes.length > 1) {
            ctx.beginPath();
            boxes.forEach((box, i) => {
              const p = atImg((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2);
              if (i === 0) ctx.moveTo(p[0], p[1]);
              else ctx.lineTo(p[0], p[1]);
            });
            ctx.globalAlpha = 0.55 * (1 - cloudSoon) * plan;
            ctx.strokeStyle = "#e7eef2";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
          ctx.restore();
        }
        if (writing) {
          ctx.fillStyle = "#f4f1ea";
          ctx.font = "13px Montserrat, sans-serif";
          if (phase2 > 0.04 && phase3 < 0.92 || to02 > 0.04) {
            const p2scale = 1 - phase3 * 0.28 * (1 - to02);
            const p2wide = 1 + to02 * 0.72;
            const s = atImg(455 - 65 * p2scale * p2wide - 36 * phase3 * (1 - to02), 412.5 - 57.5 * p2scale);
            ctx.globalAlpha = Math.max(phase2 * (1 - phase3), to02) * plan;
            note(s[0], s[1] - 26, "Phase 02", "Residential riverfront, grocery at grade");
          }
          if (phase3 > 0.04) {
            const p3scale = 0.62 + 0.38 * phase3;
            const s = atImg(730 + 22 * (1 - phase3) - 118 * p3scale, 445 + 55 * p3scale);
            ctx.globalAlpha = phase3 * (1 - cloudSoon) * plan;
            note(s[0], s[1] + 28, "Phase 03", "Civic and cultural precinct");
          }
          if (toSun > 0.08) {
            const s = atImg(420, 360);
            ctx.globalAlpha = toSun * plan * (1 - ease(Math.max(0, Math.min(1, (t - 136) / 4.6))));
            note(s[0], s[1], "Solarium and conservatory", "with maker spaces");
          }
        }
        const cloud = ease(Math.max(0, Math.min(1, (t - 136) / 7.2)));
        if (cloud > 0.02) {
          ctx.save();
          const born = Math.floor(cloud * 260);
          const fade = 1 - ease(Math.max(0, Math.min(1, (cloud - 0.72) / 0.28)));
          if (!planSample && schemeImg.naturalWidth) {
            const sample = document.createElement("canvas");
            sample.width = 160;
            sample.height = 110;
            const g = sample.getContext("2d");
            g.drawImage(schemeImg, 0, 0, 160, 110);
            planSample = g.getImageData(0, 0, 160, 110).data;
          }
          ctx.globalAlpha = ease(Math.max(0, Math.min(1, (cloud - 0.35) / 0.5))) * plan;
          ctx.fillStyle = "#070707";
          ctx.fillRect(mx - slideX, my - slideY, mw + slideX * 2, mh + slideY * 2);
          for (let i = 0; i < born; i++) {
            const u = ((i * 47) % 100) / 100;
            const v = ((i * 73) % 100) / 100;
            const ox = dx + u * dw;
            const oy = dy + v * dh;
            const drift = ((i * 13) % 17) / 17 - 0.5;
            const ang = -Math.PI / 2 + drift * 1.6;
            const travel = cloud * cloud * (90 + (i % 11) * 36);
            const wobble = Math.sin(i * 1.7 + cloud * 8) * 14 * cloud;
            const size = 4 + (i % 5) * 3.5;
            let tone = "#0c1612";
            if (planSample) {
              const sx = Math.min(159, Math.floor(u * 160));
              const sy = Math.min(109, Math.floor(v * 110));
              const pi = (sy * 160 + sx) * 4;
              tone = "rgb(" + planSample[pi] + "," + planSample[pi + 1] + "," + planSample[pi + 2] + ")";
            }
            ctx.globalAlpha = plan * fade * (0.7 + (i % 5) * 0.06);
            ctx.fillStyle = tone;
            ctx.fillRect(ox + Math.cos(ang) * travel + wobble - size / 2, oy + Math.sin(ang) * travel - size / 2, size, size);
          }
          ctx.restore();
        }
        ctx.restore();
      }
      const echo = ease(Math.max(0, Math.min(1, (t - 97) / 2.4)));
      if (echo > 0.02 && MAP.site && MAP.site.length > 2) {
        const pts = MAP.site.map(p => project(p[0], p[1], 0));
        const n = pts.length;
        const seg = [];
        let perim = 0;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n;
          const len = Math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]) || 0.001;
          seg.push(len);
          perim += len;
        }
        ctx.save();
        const gone = ease(Math.max(0, Math.min(1, (t - 136) / 7.2)));
        ctx.strokeStyle = "#e7eef2";
        ctx.fillStyle = "#f7fafc";
        ctx.lineWidth = 1.2;
        ctx.lineJoin = "round";
        ctx.globalAlpha = Math.min(0.9, echo) * (1 - gone);
        ctx.beginPath();
        let drawn = 0;
        const budget = perim * echo;
        for (let i = 0; i < n && drawn < budget; i++) {
          const j = (i + 1) % n;
          const use = Math.min(1, (budget - drawn) / seg[i]);
          const x1 = pts[i][0] * (1 - use) + pts[j][0] * use;
          const y1 = pts[i][1] * (1 - use) + pts[j][1] * use;
          if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
          ctx.lineTo(x1, y1);
          drawn += seg[i] * use;
        }
        ctx.stroke();
        const count = 28;
        for (let i = 0; i < count; i++) {
          let dist = (i / count) * perim * echo;
          let a = 0;
          while (a < n - 1 && dist > seg[a]) { dist -= seg[a]; a++; }
          const b = (a + 1) % n;
          const k = seg[a] > 0 ? dist / seg[a] : 0;
          ctx.globalAlpha = echo * (1 - gone) * (0.45 + (i % 3) * 0.15);
          ctx.beginPath();
          ctx.arc(pts[a][0] * (1 - k) + pts[b][0] * k, pts[a][1] * (1 - k) + pts[b][1] * k, 1.35, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
      const centreOf = (b) => {
        const n = b.footprint.length;
        return b.footprint.reduce((s, p) => [s[0] + p[0] / n, s[1] + p[1] / n], [0, 0]);
      };
      const screenOf = (b) => {
        let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
        b.footprint.forEach(p => {
          [b.z0, b.z1].forEach(z => {
            const s = project(p[0], p[1], z);
            minX = Math.min(minX, s[0]);
            maxX = Math.max(maxX, s[0]);
            minY = Math.min(minY, s[1]);
            maxY = Math.max(maxY, s[1]);
          });
        });
        return { minX: minX - 28, minY: minY - 28, maxX: maxX + 28, maxY: maxY + 28 };
      };
      const placed = printFrame();
      const mw = placed.mw, mh = placed.mh, mx = placed.mx, my = placed.my;
      const callout = (building, lines, alpha) => {
        if (alpha < 0.02 || !writing) return;
        ctx.save();
        const measure = (line, i) => {
          ctx.font = (i > 0 && lines[0].indexOf("Pale timber") !== 0 ? "italic 11px " : "13px ") + "Montserrat, sans-serif";
          return ctx.measureText(line).width;
        };
        const tw = Math.max.apply(null, lines.map(measure));
        const lh = 18, th = lines.length * lh, gap = 118;
        const focus = screenOf(building);
        let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
        BUILDINGS.forEach(b => {
          const box = screenOf(b);
          minX = Math.min(minX, box.minX);
          maxX = Math.max(maxX, box.maxX);
          minY = Math.min(minY, box.minY);
          maxY = Math.max(maxY, box.maxY);
        });
        const midX = (focus.minX + focus.maxX) / 2;
        const midY = (focus.minY + focus.maxY) / 2;
        const high = lines[0] === "Auditorium";
        const spots = [
          { x: focus.minX - gap - tw, y: midY - th / 2 - (high ? 48 : 0) },
          { x: focus.maxX + gap, y: midY - th / 2 - (high ? 48 : 0) },
          { x: midX - tw / 2, y: focus.minY - gap - th - (high ? 28 : 0) }
        ];
        if (!high) spots.push({ x: midX - tw / 2, y: focus.maxY + gap });
        const placed = spots.map(s => ({
          x: Math.max(mx + mw * 0.18, Math.min(mx + mw * 0.68 - tw, s.x)),
          y: Math.max(my + mh * 0.32, Math.min(my + mh * (high ? 0.44 : 0.52) - th, s.y))
        }));
        const clear = (s) => s.x + tw < minX - 36 || s.x > maxX + 36 || s.y + th < minY - 36 || s.y > maxY + 36;
        const room = (s) => {
          const cx = s.x + tw / 2, cy = s.y + th / 2;
          const dx = cx < minX ? minX - (s.x + tw) : cx > maxX ? s.x - maxX : 0;
          const dy = cy < minY ? minY - (s.y + th) : cy > maxY ? s.y - maxY : 0;
          return Math.hypot(dx, dy);
        };
        const open = placed.filter(clear).sort((a, b) => room(b) - room(a));
        let spot = open[0] || placed.slice().sort((a, b) => room(b) - room(a))[0];
        if (lines[0] === "Movement studio") {
          spot = { x: mx + mw * 0.22, y: my + mh * 0.46 };
        }
        if (lines[0].indexOf("Pale timber") === 0) {
          const pad = 64;
          let x = minX - pad - tw;
          let y = midY - th;
          if (x < mx + mw * 0.1) {
            x = mx + mw * 0.16;
            y = minY - pad - th;
          }
          spot = {
            x: Math.max(mx + mw * 0.18, Math.min(mx + mw * 0.62 - tw, x)),
            y: Math.max(my + mh * 0.32, Math.min(my + mh * 0.46, y))
          };
        }
        const ax = Math.max(focus.minX, Math.min(focus.maxX, spot.x + tw / 2));
        const ay = Math.max(focus.minY, Math.min(focus.maxY, spot.y + th / 2));
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = "#f4f1ea";
        ctx.lineWidth = 0.8;
        const lx = spot.x + tw / 2, ly = spot.y + th / 2;
        if (Math.max(ay, ly) < my + mh * 0.58) {
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(lx, ly);
          ctx.stroke();
        }
        ctx.fillStyle = "#f4f1ea";
        lines.forEach((line, i) => {
          const sub = i > 0 && lines[0].indexOf("Pale timber") !== 0;
          ctx.font = (sub ? "italic 11px " : "13px ") + "Montserrat, sans-serif";
          ctx.fillText(line, spot.x, spot.y + 13 + i * lh);
        });
        ctx.restore();
      };
      const bell = (t0, t1) => {
        const u = (t - t0) / (t1 - t0);
        if (u <= 0 || u >= 1) return 0;
        const edge = u < 0.22 ? u / 0.22 : u > 0.7 ? (1 - u) / 0.3 : 1;
        return ease(Math.max(0, Math.min(1, edge)));
      };
      const spots = [
        [bell(21.2, 26.6), 1, "Pale timber fins, rounded where the light catches"],
        [bell(26.8, 34.2), 0, "Movement studio"],
        [bell(40.6, 44.4), 1, "Auditorium"],
        [bell(44.8, 48.6), 2, "Restaurant / café"]
      ];
      const live = spots.reduce((best, s) => s[0] > best[0] ? s : best, [0, 1, ""]);
      if (live[0] > 0.04 && descend < 0.2) {
        const at = project(centreOf(BUILDINGS[live[1]])[0], centreOf(BUILDINGS[live[1]])[1], 4);
        ctx.save();
        ctx.globalAlpha = live[0] * 0.72;
        const shade = ctx.createRadialGradient(at[0], at[1], 46, at[0], at[1], stage.w * 0.55);
        shade.addColorStop(0, "rgba(6,14,12,0)");
        shade.addColorStop(0.22, "rgba(6,14,12,0)");
        shade.addColorStop(0.55, "rgba(6,10,18,0.78)");
        shade.addColorStop(1, "rgba(6,10,18,0.9)");
        ctx.fillStyle = shade;
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        ctx.restore();
        const aside = {
          "Movement studio": "dance and rehearsal by the river",
          "Auditorium": "performances and gatherings",
          "Restaurant / café": "dining on the promenade"
        };
        const lines = live[2].indexOf("Pale timber") >= 0
          ? ["Pale timber fins,", "rounded where the light catches"]
          : aside[live[2]]
            ? [live[2], aside[live[2]]]
            : [live[2]];
        callout(BUILDINGS[live[1]], lines, live[0]);
      }
      const bridgeThere = Math.min(1, mass) * (1 - ease(Math.max(0, Math.min(1, (t - 63.2) / 2.2)))) * (1 - still);
      if (bridgeThere > 0.02 && plan < 0.2) {
        const anchors = [[46, 134, 2.2], [30, 156, 2.8], [36, 178, 3.0], [56, 200, 2.4], [44, 218, 2.0], [50, 244, 1.6], [42, 274, 1.4], [34, 308, 1.3]];
        const cr = (p0, p1, p2, p3, t) => {
          const t2 = t * t, t3 = t2 * t;
          return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
        };
        const deck = [];
        const spans = anchors.length - 1;
        const steps = 6;
        for (let s = 0; s < spans; s++) {
          const p0 = anchors[Math.max(0, s - 1)];
          const p1 = anchors[s];
          const p2 = anchors[s + 1];
          const p3 = anchors[Math.min(anchors.length - 1, s + 2)];
          for (let i = 0; i < steps; i++) {
            const t = i / steps;
            deck.push([cr(p0[0], p1[0], p2[0], p3[0], t), cr(p0[1], p1[1], p2[1], p3[1], t), cr(p0[2], p1[2], p2[2], p3[2], t)]);
          }
        }
        deck.push(anchors[anchors.length - 1]);
        const rails = (pts) => {
          const n = pts.length;
          const left = [], right = [];
          for (let i = 0; i < n; i++) {
            const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
            let dx = b[0] - a[0], dy = b[1] - a[1];
            const len = Math.hypot(dx, dy) || 1;
            dx /= len; dy /= len;
            const p = pts[i], w = p[2];
            left.push([p[0] - dy * w, p[1] + dx * w]);
            right.push([p[0] + dy * w, p[1] - dx * w]);
          }
          return [left, right];
        };
        const [left, right] = rails(deck);
        const zTop = 8.2, zBot = 6.6;
        ctx.save();
        ctx.globalAlpha = bridgeThere;
        for (let i = 0; i < left.length - 1; i++) {
          quad([left[i][0], left[i][1], zTop], [right[i][0], right[i][1], zTop], [right[i + 1][0], right[i + 1][1], zTop], [left[i + 1][0], left[i + 1][1], zTop], "#f7f4ee");
          quad([left[i][0], left[i][1], zBot], [left[i + 1][0], left[i + 1][1], zBot], [left[i + 1][0], left[i + 1][1], zTop], [left[i][0], left[i][1], zTop], "#e4dfd6");
          quad([right[i][0], right[i][1], zTop], [right[i][0], right[i][1], zBot], [right[i + 1][0], right[i + 1][1], zBot], [right[i + 1][0], right[i + 1][1], zTop], "#d4cfc6");
        }
        const flare = [[18, 128], [36, 116], [62, 110], [84, 118], [58, 128], [46, 140]];
        for (let i = 1; i < flare.length - 1; i++) {
          quad([flare[0][0], flare[0][1], zTop], [flare[i][0], flare[i][1], zTop], [flare[i + 1][0], flare[i + 1][1], zTop], [flare[0][0], flare[0][1], zTop], "#f7f4ee");
        }
        const fork = [[44, 218], [30, 226], [16, 236]];
        for (let i = 0; i < fork.length - 1; i++) {
          const a = fork[i], b = fork[i + 1];
          let dx = b[0] - a[0], dy = b[1] - a[1];
          const len = Math.hypot(dx, dy) || 1;
          dx /= len; dy /= len;
          const w = 1.8;
          quad([a[0] - dy * w, a[1] + dx * w, zTop], [b[0] - dy * w, b[1] + dx * w, zTop], [b[0] + dy * w, b[1] - dx * w, zTop], [a[0] + dy * w, a[1] - dx * w, zTop], "#f7f4ee");
        }
        const pad = [[2, 252], [0, 234], [18, 226], [26, 244]];
        for (let i = 1; i < pad.length - 1; i++) {
          quad([pad[0][0], pad[0][1], zTop], [pad[i][0], pad[i][1], zTop], [pad[i + 1][0], pad[i + 1][1], zTop], [pad[0][0], pad[0][1], zTop], "#f4f1ea");
        }
        const travel = ease(Math.max(0, Math.min(1, (t - 50.0) / 2.4)));
        const cross = ease(Math.max(0, Math.min(1, (t - 50.0) / 0.35))) * (1 - ease(Math.max(0, Math.min(1, (t - 54.4) / 0.7))));
        if (cross > 0.02) {
          const idx = Math.min(0.999, travel) * (deck.length - 1);
          const a = Math.min(deck.length - 2, Math.floor(idx));
          const k = idx - a;
          const x = deck[a][0] * (1 - k) + deck[a + 1][0] * k;
          const y = deck[a][1] * (1 - k) + deck[a + 1][1] * k;
          for (let s = 4; s >= 0; s--) {
            const back = Math.max(0, idx - s * 1.4);
            const ia = Math.min(deck.length - 2, Math.floor(back));
            const kb = back - ia;
            const px = deck[ia][0] * (1 - kb) + deck[ia + 1][0] * kb;
            const py = deck[ia][1] * (1 - kb) + deck[ia + 1][1] * kb;
            const p = project(px, py, 8.6);
            ctx.globalAlpha = cross * bridgeThere * (s === 0 ? 0.95 : 0.28);
            ctx.fillStyle = s === 0 ? "#f4fbff" : "#7ec8ea";
            ctx.beginPath();
            ctx.arc(p[0], p[1], s === 0 ? 3.2 : 1.6, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.restore();
      }
      const bridgeNote = bell(49.2, 54.6);
      if (bridgeNote > 0.02 && writing && plan < 0.15) {
        ctx.save();
        ctx.globalAlpha = bridgeNote;
        ctx.fillStyle = "#f4f1ea";
        ctx.textAlign = "right";
        note(mx + mw * 0.72, my + mh * 0.64, "Curved crossing", "to the opposite bank, forking to an overlook");
        ctx.textAlign = "left";
        ctx.restore();
      }
      const hush = bell(22.6, 24.0);
      if (hush > 0.02 && descend < 0.2) {
        ctx.save();
        ctx.lineWidth = 1;
        BUILDINGS.forEach(b => {
          const c = centreOf(b);
          const p = project(c[0], c[1], 3);
          for (let i = 0; i < 16; i++) {
            const side = i < 8 ? -1 : 1;
            const ox = side * (78 + (i % 8) * 3.4);
            ctx.globalAlpha = hush * (0.12 + (i % 4) * 0.08);
            ctx.strokeStyle = i % 2 ? "#07140f" : "#1a4030";
            ctx.beginPath();
            ctx.moveTo(p[0] + ox, p[1] - 70);
            ctx.lineTo(p[0] + ox, p[1] + 64);
            ctx.stroke();
          }
        });
        ctx.restore();
      }
      const vignette = ctx.createRadialGradient(
        stage.x + stage.w / 2, stage.y + stage.h / 2, stage.w * 0.18,
        stage.x + stage.w / 2, stage.y + stage.h / 2, stage.w * 0.62
      );
      vignette.addColorStop(0, "rgba(0,0,0,0)");
      vignette.addColorStop(1, "rgba(28, 24, 20, 0.22)");
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, innerWidth, innerHeight);
      ctx.restore();
      const remain = bell(65.0, 70.6);
      if (remain > 0.02 && writing && plan < 0.4) {
        ctx.save();
        ctx.globalAlpha = remain;
        ctx.font = "13px Montserrat, sans-serif";
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(28, 18, 10, 0.82)";
        ctx.fillStyle = "#f7f4ee";
        ctx.textAlign = "center";
        const roofBuilding = BUILDINGS.reduce((a, b) => b.z1 < a.z1 ? b : a);
        const roof = centreOf(roofBuilding);
        const onRoof = project(roof[0], roof[1], roofBuilding.z1);
        const tx = onRoof[0];
        const ty = onRoof[1] - 6;
        ctx.strokeText("Glulam timber interiors", tx, ty);
        ctx.fillText("Glulam timber interiors", tx, ty);
        ctx.font = "italic 11px Montserrat, sans-serif";
        ctx.strokeText("with soaring ceilings.", tx, ty + 18);
        ctx.fillText("with soaring ceilings.", tx, ty + 18);
        ctx.restore();
      }
      const parkNote = bell(93.8, 102.4);
      if (parkNote > 0.02 && writing && plan < 0.35) {
        ctx.save();
        ctx.globalAlpha = parkNote;
        ctx.fillStyle = "#f4f1ea";
        note(mx + mw * 0.18, my + mh * 0.56, "Negative space", "left open so greenery and trees can thrive as a park");
        ctx.restore();
      }
      const coverIn = ease(Math.max(0, Math.min(1, (t - 34.2) / 1.2)));
      const coverOut = ease(Math.max(0, Math.min(1, (t - 37.2) / 1.6)));
      const coverA = coverIn * (1 - coverOut);
      const hatchR = Math.min(mw, mh) * 0.05;
      const edgeMaskY = (maskX) => {
        if (maskX < 140) return 190 + 11 * (maskX / 140);
        if (maskX < 360) return 201 + (151 - 201) * ((maskX - 140) / 220);
        return 151;
      };
      const above = (maskX) => {
        const y = edgeMaskY(maskX);
        return [mx + mw * (maskX / 1024), my + mh * (y / 561) - hatchR - 8];
      };
      const spot0 = above(108);
      const hatchX = spot0[0], hatchY = spot0[1];
      const turrell = ease(Math.max(0, Math.min(1, (t - 76.4) / 1.1))) * (1 - ease(Math.max(0, Math.min(1, (t - 80.8) / 1.3))));
      if (turrell > 0.02) {
        ctx.save();
        const glow = ctx.createLinearGradient(0, hatchY, mx + mw * 0.55, hatchY);
        glow.addColorStop(0, "rgba(255, 214, 168, " + (0.92 * turrell) + ")");
        glow.addColorStop(0.42, "rgba(232, 126, 74, " + (0.55 * turrell) + ")");
        glow.addColorStop(1, "rgba(232, 126, 74, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, mx + mw * 0.62, innerHeight);
        ctx.globalAlpha = turrell;
        ctx.fillStyle = "#070707";
        ctx.beginPath();
        ctx.arc(hatchX, hatchY, hatchR * 0.72, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      const burst = 0;
      if (burst > 0.02) {
        const entryX = mx + mw * (150 / 1024);
        const entryY = my + mh * (188 / 561);
        ctx.save();
        [[-0.4, 0.55, "227, 154, 74"], [0.9, -0.38, "242, 196, 122"], [2.1, 0.82, "196, 98, 42"], [1.4, -0.22, "255, 214, 160"], [3.4, 0.31, "168, 86, 48"]].forEach((shaft, i) => {
          const ang = shaft[0] + t * shaft[1];
          const reach = mw * (0.55 + burst * 0.7);
          const spread = 0.04 + (i % 3) * 0.03;
          const tone = ctx.createLinearGradient(entryX, entryY, entryX + Math.cos(ang) * reach, entryY + Math.sin(ang) * reach);
          tone.addColorStop(0, "rgba(" + shaft[2] + ",0)");
          tone.addColorStop(0.2, "rgba(" + shaft[2] + "," + (0.34 * burst) + ")");
          tone.addColorStop(1, "rgba(" + shaft[2] + ",0)");
          ctx.fillStyle = tone;
          ctx.beginPath();
          ctx.moveTo(entryX, entryY);
          ctx.lineTo(entryX + Math.cos(ang - spread) * reach, entryY + Math.sin(ang - spread) * reach);
          ctx.lineTo(entryX + Math.cos(ang + spread) * reach, entryY + Math.sin(ang + spread) * reach);
          ctx.closePath();
          ctx.fill();
        });
        for (let i = 0; i < 16; i++) {
          const ang = -0.3 + (i / 16) * 2.4 + Math.sin(t * 0.8 + i) * 0.08;
          const d = mw * (0.08 + (i % 5) * 0.09) * (0.4 + burst * 0.6);
          const x = entryX + Math.cos(ang) * d;
          const y = entryY + Math.sin(ang) * d;
          ctx.globalAlpha = burst * (0.4 + (i % 3) * 0.18);
          ctx.fillStyle = i % 2 ? "#d5e7a4" : "#f0d2a4";
          ctx.beginPath();
          ctx.ellipse(x, y, 8 + (i % 4) * 3, 3.6, ang + 0.4, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
      applyPrint(ease(Math.max(0, Math.min(1, (t - 104.2) / 22))) * (1 - ease(Math.max(0, Math.min(1, (t - 136) / 7.2)))));
      if (openingChannel && earlyCut > 0.04) {
        ctx.save();
        const midX = originX;
        const half = Math.max(2, spillR);
        ctx.beginPath();
        ctx.rect(midX - half, 0, half * 2, innerHeight);
        ctx.clip();
        ctx.globalAlpha = earlyCut;
        poly(openingChannel, "#1a3d66");
        ctx.strokeStyle = "#d5e4ea";
        ctx.lineWidth = 1.35;
        ctx.globalAlpha = earlyCut * 0.9;
        const mid = Math.floor(openingChannel.length / 2);
        [openingChannel.slice(0, mid), openingChannel.slice(mid).reverse()].forEach(bank => {
          ctx.beginPath();
          bank.forEach((pt, i) => {
            const p = project(pt[0], pt[1], 0);
            if (i === 0) ctx.moveTo(p[0], p[1]);
            else ctx.lineTo(p[0], p[1]);
          });
          ctx.stroke();
        });
        ctx.restore();
      }
      const room = opening;
      document.body.style.background = "rgb(" + Math.round(7 + 233 * room) + "," + Math.round(7 + 203 * room) + "," + Math.round(7 + 157 * room) + ")";
      if (room > 0.02) {
        ctx.save();
        ctx.globalCompositeOperation = "destination-over";
        ctx.fillStyle = "rgb(240, 210, 164)";
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        const boards = 16;
        const drift = Math.sin(t * 0.35) * innerWidth * 0.04;
        for (let i = 0; i < boards; i++) {
          const band = innerHeight / boards;
          const y = i * band;
          const fromLeft = i % 2 === 0;
          const slide = room * (innerWidth + 40);
          const x = fromLeft ? -innerWidth - 20 + slide + drift : innerWidth + 20 - slide + drift;
          ctx.globalAlpha = 0.55 + (i % 4 === 0 ? 0.35 : 0);
          ctx.fillStyle = i % 4 === 0 ? "rgb(214, 176, 128)" : "rgb(232, 198, 154)";
          ctx.fillRect(x, y, innerWidth, band - 2);
        }
        ctx.restore();
      }
      const beam = 0;
      const grid = ease(Math.max(0, Math.min(1, (t - 64.8) / 2.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 72.4) / 1.6))));
      if (coverA > 0.02) {
        const ignite = ease(Math.max(0, Math.min(1, (t - 36.2) / 0.55)));
        const surge = 1 + ignite * 0.32;
        ctx.save();
        ctx.globalAlpha = Math.min(1, coverA * (1 + ignite * 0.35));
        const glow = ctx.createRadialGradient(hatchX, hatchY, 0, hatchX, hatchY, hatchR * 1.8 * surge);
        glow.addColorStop(0, "rgba(227, 154, 74, 0.55)");
        glow.addColorStop(1, "rgba(227, 154, 74, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(hatchX, hatchY, hatchR * 1.8 * surge, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#e39a4a";
        ctx.lineWidth = 1.2;
        for (let ring = 1; ring <= 4; ring++) {
          ctx.globalAlpha = coverA;
          ctx.beginPath();
          ctx.arc(hatchX, hatchY, hatchR * (0.28 + ring * 0.18) * surge, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();
      }
      const tokens = ease(Math.max(0, Math.min(1, (t - 37.6) / 1.1))) * (1 - ease(Math.max(0, Math.min(1, (t - 42.4) / 2.2))));
      const wrap = ease(Math.max(0, Math.min(1, (t - 37.6) / 1.8)));
      if (tokens > 0.02) {
        ctx.save();
        const count = 52;
        const rim = [329,151,951,151,972,156,984,164,996,177,1003,191,1006,208,1006,370,1001,391,991,406,981,415,973,420,949,426,891,426,697,417,687,415,648,415,641,413,634,414,392,403,372,399,352,399,340,396,320,395,263,387,251,383,240,383,228,379,188,372,177,367,169,367,144,360,124,354,120,351,103,347,91,341,56,329,37,319,27,309,20,298,14,277,14,199,16,196,16,189,26,182,42,182,63,190,64,192,70,192,91,198,118,201,152,200,198,192,202,189,226,181,234,176,239,176,245,172,275,163,279,160,287,160,297,156];
        const n = rim.length / 2;
        const seg = [];
        let perim = 0;
        for (let s = 0; s < n; s++) {
          const j = (s + 1) % n;
          const len = Math.hypot(rim[j * 2] - rim[s * 2], rim[j * 2 + 1] - rim[s * 2 + 1]);
          seg.push(len);
          perim += len;
        }
        let start = 0;
        let best = 1e9;
        for (let s = 0; s < n; s++) {
          const dx = rim[s * 2] - 108;
          const dy = rim[s * 2 + 1] - 200;
          const d2 = dx * dx + dy * dy;
          if (d2 < best) { best = d2; start = s; }
        }
        ctx.strokeStyle = "#e39a4a";
        ctx.lineWidth = 1.15;
        ctx.globalAlpha = tokens * 0.85;
        ctx.beginPath();
        let drawn = 0;
        const budget = perim * wrap;
        for (let s = 0; s < n && drawn < budget; s++) {
          const i = (start + s) % n;
          const j = (i + 1) % n;
          const use = Math.min(1, (budget - drawn) / (seg[i] || 1));
          const x0 = mx + mw * (rim[i * 2] / 1024);
          const y0 = my + mh * (rim[i * 2 + 1] / 561);
          const x1 = mx + mw * ((rim[i * 2] * (1 - use) + rim[j * 2] * use) / 1024);
          const y1 = my + mh * ((rim[i * 2 + 1] * (1 - use) + rim[j * 2 + 1] * use) / 561);
          if (s === 0) ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
          drawn += seg[i] * use;
        }
        ctx.stroke();
        let origin = 0;
        for (let s = 0; s < start; s++) origin += seg[s];
        for (let i = 0; i < count; i++) {
          let dist = (origin + (i / count) * perim * wrap) % perim;
          let a = 0;
          while (a < n - 1 && dist > seg[a]) { dist -= seg[a]; a++; }
          const b = (a + 1) % n;
          const k = seg[a] > 0 ? dist / seg[a] : 0;
          const maskX = rim[a * 2] * (1 - k) + rim[b * 2] * k;
          const maskY = rim[a * 2 + 1] * (1 - k) + rim[b * 2 + 1] * k;
          const sx = mx + mw * (maskX / 1024);
          const sy = my + mh * (maskY / 561);
          ctx.globalAlpha = tokens * (0.45 + (i % 3) * 0.15);
          ctx.fillStyle = "#e39a4a";
          ctx.beginPath();
          ctx.arc(sx, sy, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
      if (beam > 0.02) {
        const shafts = [
          { spin: 0.55, phase: -0.4, width: 0.045, reach: 1.15, tone: "227, 154, 74", alpha: 0.72 },
          { spin: -0.38, phase: 0.9, width: 0.11, reach: 0.92, tone: "242, 196, 122", alpha: 0.38 },
          { spin: 0.82, phase: 2.1, width: 0.018, reach: 1.35, tone: "196, 98, 42", alpha: 0.8 },
          { spin: -0.22, phase: 1.4, width: 0.16, reach: 0.7, tone: "255, 228, 186", alpha: 0.28 },
          { spin: 0.31, phase: 3.4, width: 0.03, reach: 1.05, tone: "168, 86, 48", alpha: 0.55 }
        ];
        ctx.save();
        shafts.forEach((shaft) => {
          const ang = shaft.phase + t * shaft.spin;
          const reach = Math.hypot(innerWidth, innerHeight) * shaft.reach * (0.45 + beam * 0.7);
          const spread = shaft.width * (0.6 + beam * 1.4);
          const tipX = hatchX + Math.cos(ang) * reach;
          const tipY = hatchY + Math.sin(ang) * reach;
          const beamTone = ctx.createLinearGradient(hatchX, hatchY, tipX, tipY);
          beamTone.addColorStop(0, "rgba(" + shaft.tone + "," + shaft.alpha + ")");
          beamTone.addColorStop(0.55, "rgba(" + shaft.tone + "," + (shaft.alpha * 0.35) + ")");
          beamTone.addColorStop(1, "rgba(" + shaft.tone + ",0)");
          ctx.globalAlpha = Math.min(0.9, beam * 1.15);
          ctx.fillStyle = beamTone;
          ctx.beginPath();
          ctx.moveTo(hatchX, hatchY);
          ctx.lineTo(hatchX + Math.cos(ang - spread) * reach, hatchY + Math.sin(ang - spread) * reach);
          ctx.lineTo(hatchX + Math.cos(ang + spread) * reach, hatchY + Math.sin(ang + spread) * reach);
          ctx.closePath();
          ctx.fill();
        });
        ctx.globalAlpha = beam;
        ctx.strokeStyle = "#e39a4a";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(hatchX, hatchY, hatchR * 0.7, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
      if (grid > 0.02) {
        const stream = ease(Math.max(0, Math.min(1, (t - 64.8) / 2.2)));
        const held = ease(Math.max(0, Math.min(1, (t - 67.2) / 0.45))) * (1 - ease(Math.max(0, Math.min(1, (t - 72.4) / 1.2))));
        if (held > 0.02) {
          if (!wedgeSheet) wedgeSheet = document.createElement("canvas");
          wedgeSheet.width = canvas.width;
          wedgeSheet.height = canvas.height;
          wedgeSheet.getContext("2d").drawImage(canvas, 0, 0);
          const wedges = [
            { pts: [[0, 0], [innerWidth * 0.48, 0], [0, innerHeight * 0.58]], filter: "grayscale(1) brightness(0.22) contrast(1.2)" },
            { pts: [[innerWidth, 0], [innerWidth * 0.55, 0], [innerWidth, innerHeight * 0.4]], filter: "grayscale(1) brightness(0.46) contrast(1.05)" },
            { pts: [[innerWidth, innerHeight], [innerWidth * 0.5, innerHeight], [innerWidth, innerHeight * 0.46]], filter: "grayscale(1) brightness(0.14) contrast(1.25)" },
            { pts: [[0, innerHeight], [innerWidth * 0.4, innerHeight], [0, innerHeight * 0.42]], filter: "grayscale(1) brightness(0.34) contrast(1.1)" }
          ];
          wedges.forEach((wedge) => {
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(wedge.pts[0][0], wedge.pts[0][1]);
            ctx.lineTo(wedge.pts[1][0], wedge.pts[1][1]);
            ctx.lineTo(wedge.pts[2][0], wedge.pts[2][1]);
            ctx.closePath();
            ctx.clip();
            ctx.filter = wedge.filter;
            ctx.globalAlpha = held;
            ctx.drawImage(wedgeSheet, 0, 0, innerWidth, innerHeight);
            ctx.restore();
          });
        }
        const runs = [
          { ang: -0.15, reach: 1.25, weight: 1.6 },
          { ang: 0.42, reach: 0.95, weight: 0.6 },
          { ang: 1.05, reach: 1.4, weight: 0.8 },
          { ang: 1.7, reach: 0.8, weight: 2.4 },
          { ang: 2.45, reach: 1.1, weight: 0.5 }
        ];
        ctx.save();
        ctx.globalAlpha = Math.min(0.9, grid);
        ctx.lineCap = "square";
        runs.forEach((run) => {
          const reach = Math.hypot(innerWidth, innerHeight) * run.reach * stream;
          const x2 = hatchX + Math.cos(run.ang) * reach;
          const y2 = hatchY + Math.sin(run.ang) * reach;
          ctx.strokeStyle = run.weight > 1.5 ? "#d7f4ff" : "#7ec8ea";
          ctx.lineWidth = run.weight;
          ctx.beginPath();
          ctx.moveTo(hatchX, hatchY);
          ctx.lineTo(x2, y2);
          ctx.stroke();
          for (let s = 1; s <= 4; s++) {
            const u = s / 5;
            const nx = hatchX + (x2 - hatchX) * u;
            const ny = hatchY + (y2 - hatchY) * u;
            ctx.strokeStyle = "#f4fbff";
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(nx - Math.sin(run.ang) * 7, ny + Math.cos(run.ang) * 7);
            ctx.lineTo(nx + Math.sin(run.ang) * 7, ny - Math.cos(run.ang) * 7);
            ctx.stroke();
          }
        });
        ctx.fillStyle = "#eaf8ff";
        ctx.beginPath();
        ctx.arc(hatchX, hatchY, hatchR * 0.35, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      const glass = 0;
      if (glass > 0.02) {
        const ribs = [-0.35, 0.15, 0.7, 1.25, 1.85, 2.5];
        ctx.save();
        ctx.lineCap = "round";
        ribs.forEach((ang, i) => {
          const reach = Math.hypot(innerWidth, innerHeight) * (0.55 + (i % 3) * 0.18) * glass;
          const tipX = hatchX + Math.cos(ang) * reach;
          const tipY = hatchY + Math.sin(ang) * reach;
          const bow = 70 + (i % 2) * 46;
          const cx = hatchX + Math.cos(ang) * reach * 0.5 - Math.sin(ang) * bow;
          const cy = hatchY + Math.sin(ang) * reach * 0.5 + Math.cos(ang) * bow;
          ctx.globalAlpha = Math.min(0.85, glass);
          ctx.strokeStyle = i % 2 ? "#e7f0d4" : "#b7d39a";
          ctx.lineWidth = i % 3 === 0 ? 1.6 : 0.7;
          ctx.beginPath();
          ctx.moveTo(hatchX, hatchY);
          ctx.quadraticCurveTo(cx, cy, tipX, tipY);
          ctx.stroke();
          ctx.fillStyle = i % 2 ? "#dfe8c8" : "#9cbf78";
          ctx.beginPath();
          ctx.ellipse(tipX, tipY, 11 + (i % 3) * 4, 5, ang, 0, Math.PI * 2);
          ctx.fill();
        });
        ctx.globalAlpha = glass * 0.16;
        ctx.fillStyle = "#e4f0c8";
        ctx.beginPath();
        ctx.moveTo(hatchX, hatchY);
        ctx.arc(hatchX, hatchY, Math.min(mw, mh) * 0.42 * glass, -0.2, 1.6);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
      const s = mh * 0.12;
      const ax = mx + mw + s * 0.55;
      const hy = my + mh * 0.34;
      const hydrantH = s;
      const plateH = s * 0.92;
      const py = my + mh * 0.4 + s * 1.42;
      const px = ax;
      const walkAway = ease(Math.max(0, Math.min(1, (t - 104) / 1.4)));
      const stride = ease(Math.max(0, Math.min(1, (t - 105.2) / 7)));
      ctx.save();
      ctx.globalAlpha = 1 - walkAway;
      ctx.fillStyle = "#e4ece6";
      ctx.strokeStyle = "#c9d4cc";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(ax, hy + s * 0.12, s * 0.09, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(ax - s * 0.045, hy + s * 0.2, s * 0.09, s * 0.72);
      ctx.fillRect(ax - s * 0.16, hy + s * 0.32, s * 0.1, s * 0.07);
      ctx.fillRect(ax + s * 0.06, hy + s * 0.32, s * 0.1, s * 0.07);
      ctx.globalAlpha = 1;
      ctx.strokeRect(px - s * 0.22, py, s * 0.5, plateH);
      ctx.beginPath();
      ctx.moveTo(px - s * 0.02, py + plateH * 0.12);
      ctx.quadraticCurveTo(px + s * 0.16, py + plateH * 0.4, px, py + plateH * 0.82);
      ctx.stroke();
      ctx.restore();
      if (walkAway > 0.02) {
        const fx = ax + stride * (innerWidth - ax + s);
        const fy = hy + s * 0.55;
        const swing = Math.sin(t * 7) * stride;
        ctx.save();
        ctx.globalAlpha = walkAway;
        ctx.strokeStyle = "#f2d15a";
        ctx.fillStyle = "#f2d15a";
        ctx.lineWidth = 1.4;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.arc(fx, fy - s * 0.42, s * 0.08, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(fx, fy - s * 0.32);
        ctx.lineTo(fx, fy);
        ctx.moveTo(fx, fy - s * 0.2);
        ctx.lineTo(fx - s * 0.16 * (0.6 + swing), fy - s * 0.02);
        ctx.moveTo(fx, fy - s * 0.2);
        ctx.lineTo(fx + s * 0.16 * (0.6 - swing), fy - s * 0.02);
        ctx.moveTo(fx, fy);
        ctx.lineTo(fx - s * 0.12 * (0.5 - swing), fy + s * 0.22);
        ctx.moveTo(fx, fy);
        ctx.lineTo(fx + s * 0.12 * (0.5 + swing), fy + s * 0.22);
        ctx.stroke();
        ctx.restore();
      }
      const sideLight = ease(Math.max(0, Math.min(1, (t - 82) / 1.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 98.6) / 2.2))));
      if (sideLight > 0.02) {
        const washHue = (t * 28) % 360;
        const bodyY = hy + s * 0.48;
        const wash = ctx.createRadialGradient(ax, bodyY, s * 0.04, ax, bodyY, s * 1.45);
        wash.addColorStop(0, "hsla(" + washHue + ", 62%, 78%, " + (0.62 * sideLight) + ")");
        wash.addColorStop(0.4, "hsla(" + ((washHue + 48) % 360) + ", 55%, 62%, " + (0.28 * sideLight) + ")");
        wash.addColorStop(1, "hsla(" + washHue + ", 40%, 50%, 0)");
        ctx.save();
        ctx.fillStyle = wash;
        ctx.beginPath();
        ctx.ellipse(ax, bodyY, s * 0.85, s * 1.55, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        const waves = 7;
        ctx.save();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        const inset = Math.min(innerWidth, innerHeight) * 0.1;
        const x0 = inset, y0 = inset, x1 = innerWidth - inset, y1 = innerHeight - inset;
        const spanX = x1 - x0, spanY = y1 - y0;
        const loop = spanX * 2 + spanY * 2;
        const at = (d) => {
          let u = ((d % loop) + loop) % loop;
          if (u < spanX) return [x0 + u, y0, 0, -1];
          u -= spanX;
          if (u < spanY) return [x1, y0 + u, 1, 0];
          u -= spanY;
          if (u < spanX) return [x1 - u, y1, 0, 1];
          u -= spanX;
          return [x0, y1 - u, -1, 0];
        };
        for (let i = 0; i < waves; i++) {
          ctx.globalAlpha = sideLight * (0.34 + (i % 3) * 0.14);
          ctx.strokeStyle = i % 2 ? "#8ec6ea" : "#e7c48a";
          ctx.lineWidth = i % 3 === 0 ? 1.35 : 0.7;
          ctx.beginPath();
          const steps = 220;
          for (let s = 0; s <= steps; s++) {
            const d = (s / steps) * loop + i * 18;
            const p = at(d);
            const wave = 6 + Math.sin(s * 0.22 + t * 1.4 + i * 0.8) * (6 + (i % 3) * 3);
            const wx = p[0] - p[2] * wave;
            const wy = p[1] - p[3] * wave;
            if (s === 0) ctx.moveTo(wx, wy);
            else ctx.lineTo(wx, wy);
          }
          ctx.stroke();
        }
        ctx.restore();
      }
      if (grid > 0.02) {
        const hydrantNode = [ax, hy + hydrantH * 0.55];
        ctx.save();
        ctx.globalAlpha = Math.min(0.9, grid);
        ctx.lineCap = "round";
        ctx.strokeStyle = "#7ec8ea";
        ctx.lineWidth = 0.8;
        for (let i = 0; i < 22; i++) {
          const ang = i * 1.37 + t * 0.6;
          const rad = s * (0.22 + (i % 5) * 0.06) * grid;
          const wobble = Math.sin(i * 2.1 + t) * s * 0.08;
          ctx.strokeStyle = i % 3 === 0 ? "#f4fbff" : "#7ec8ea";
          ctx.lineWidth = i % 4 === 0 ? 1.1 : 0.45;
          ctx.beginPath();
          ctx.arc(hydrantNode[0] + wobble, hydrantNode[1] + wobble * 0.4, rad, ang, ang + 1.15 + (i % 3) * 0.35);
          ctx.stroke();
        }
        for (let i = 0; i < 9; i++) {
          const ang = i * 0.9 + 0.4;
          ctx.fillStyle = "#d7f4ff";
          ctx.globalAlpha = grid * (0.45 + (i % 2) * 0.35);
          ctx.beginPath();
          ctx.arc(hydrantNode[0] + Math.cos(ang) * s * 0.22 * grid, hydrantNode[1] + Math.sin(ang) * s * 0.16 * grid, 1.1, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = Math.min(0.9, grid);
        ctx.restore();
      }
      const nebula = ease(Math.max(0, Math.min(1, (t - 93) / 2.2))) * (1 - ease(Math.max(0, Math.min(1, (t - 120) / 4.2)))) * (1 - still);
      if (nebula > 0.02) {
        const tones = ["#ff3b2e", "#2f7bff", "#ffe14a", "#3dffb0", "#e040ff", "#ff4fa3"];
        ctx.save();
        ctx.lineCap = "round";
        ctx.globalAlpha = Math.min(1, nebula);
        for (let i = 0; i < 36; i++) {
          const ang = i * 2.399 + t * 0.55;
          const breathe = 0.55 + 0.45 * Math.sin(t * 1.3 + i * 0.8);
          const len = mh * 0.05 * breathe * (0.45 + nebula * 0.55);
          const x2 = hatchX + Math.cos(ang) * len;
          const y2 = hatchY + Math.sin(ang + Math.sin(t + i) * 0.4) * len * 0.8;
          const tone = tones[i % tones.length];
          ctx.strokeStyle = tone;
          ctx.lineWidth = 1.6 + (i % 3) * 0.7;
          ctx.globalAlpha = nebula * 0.55;
          ctx.beginPath();
          ctx.moveTo(hatchX, hatchY);
          ctx.quadraticCurveTo(
            hatchX + Math.cos(ang + t * 0.3) * len * 0.45,
            hatchY + Math.sin(ang - t * 0.25) * len * 0.35,
            x2, y2
          );
          ctx.stroke();
          ctx.globalAlpha = nebula;
          ctx.lineWidth = 0.7 + (i % 2) * 0.35;
          ctx.stroke();
        }
        ctx.restore();
      }
      const settle = ease(Math.max(0, Math.min(1, (t - 143.4) / 0.9)));
      if (settle > 0.02) {
        ctx.save();
        ctx.globalAlpha = settle;
        ctx.fillStyle = "#070707";
        ctx.fillRect(0, 0, innerWidth, innerHeight);
        ctx.restore();
      }
      const reprise = ease(Math.max(0, Math.min(1, (t - 150.2) / 1.6)));
      if (reprise > 0.02) {
        ctx.save();
        const yN = innerHeight * 0.38;
        const yS = innerHeight * 0.56;
        const reach = innerWidth * reprise;
        ctx.beginPath();
        ctx.moveTo(0, yN);
        for (let x = 0; x <= reach; x += 14) {
          ctx.lineTo(x, yN + Math.sin(x * 0.007) * innerHeight * 0.035);
        }
        for (let x = reach; x >= 0; x -= 14) {
          ctx.lineTo(x, yS + Math.sin(x * 0.007 + 1.2) * innerHeight * 0.03);
        }
        ctx.closePath();
        ctx.globalAlpha = reprise;
        ctx.fillStyle = "#1a3d66";
        ctx.fill();
        ctx.strokeStyle = "#d5e4ea";
        ctx.lineWidth = 1.35;
        ctx.beginPath();
        for (let x = 0; x <= reach; x += 14) {
          const y = yN + Math.sin(x * 0.007) * innerHeight * 0.035;
          if (x === 0) ctx.moveTo(0, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.beginPath();
        for (let x = 0; x <= reach; x += 14) {
          const y = yS + Math.sin(x * 0.007 + 1.2) * innerHeight * 0.03;
          if (x === 0) ctx.moveTo(0, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        [[0.36, -0.5, 0.9], [0.46, 0.2, 1.15], [0.56, 0.7, 1]].forEach((leaf, i) => {
          const pop = ease(Math.max(0, Math.min(1, (reprise - 0.35 - i * 0.12) / 0.4)));
          if (pop <= 0) return;
          ctx.globalAlpha = reprise * pop;
          drawLeaf(innerWidth * leaf[0], yN - innerHeight * 0.08, leaf[1], innerHeight * 0.055 * leaf[2], "#f7f4ee");
        });
        ctx.restore();
      }
    }

    function ease(t) {
      t = Math.max(0, Math.min(1, t));
      return t * t * (3 - 2 * t);
    }

    const DOOR = (function () {
      const b = BUILDINGS[1];
      const foot = b.footprint;
      let area = 0, edge = 0, best = -1;
      for (let i = 0; i < foot.length; i++) {
        const p = foot[i], q = foot[(i + 1) % foot.length];
        area += p[0] * q[1] - q[0] * p[1];
        const len = Math.hypot(q[0] - p[0], q[1] - p[1]);
        if (len > best) { best = len; edge = i; }
      }
      const a = foot[edge], c = foot[(edge + 1) % foot.length];
      let [nx, ny] = outward(a, c);
      if (area < 0) { nx *= -1; ny *= -1; }
      return { index: 1, edge, nx, ny, x: (a[0] + c[0]) / 2, y: (a[1] + c[1]) / 2 };
    })();

    const phaseEl = document.getElementById("phase");
    const precinctEl = document.getElementById("precinct");
    const para1El = document.getElementById("para1");
    const para2El = document.getElementById("para2");
    const started = performance.now();
    function frame(now) {
      const t = (now - started) / 640;
      const zoom = ease(Math.max(0, Math.min(1, (t - 9.2) / 6.2)));
      const color = ease(Math.max(0, Math.min(1, (t - 11.2) / 4.4)));
      const wave = ease(Math.max(0, Math.min(1, (t - 16.8) / 7)));
      const descend = ease(Math.max(0, Math.min(1, (t - 66.2) / 4.4)));
      const walk = ease(Math.max(0, Math.min(1, (t - 62.5) / 5)));
      const opening = ease(Math.max(0, Math.min(1, (t - 66.2) / 3.6))) * (1 - ease(Math.max(0, Math.min(1, (t - 86.8) / 2))));
      const facade = ease(Math.max(0, Math.min(1, (t - 68) / 4)));
      const plan = ease(Math.max(0, Math.min(1, (t - 104.2) / 18)));
      const pan = ease(Math.max(0, Math.min(1, (t - 54.5) / 7)));
      if (!drag) {
        const u = Math.max(0, Math.min(1, (t - 18.6) / 34));
        const p = u * u * (3 - 2 * u);
        const fly = ease(Math.max(0, Math.min(1, (t - 18.6) / 6.4)));
        const show = ease(Math.max(0, Math.min(1, (t - 16.5) / 3.6)));
        const sweep = Math.PI * 1.05;
        const handoff = Math.sin((18.6 - 16) * 0.55) * 0.22;
        const flightPitch = 0.58 + 0.14 * Math.sin(p * Math.PI);
        const basePitch = 0.02 + zoom * 0.06 + show * 0.48;
        pitch = basePitch * (1 - fly) + flightPitch * fly;
        pitch = pitch + (1.4 - pitch) * descend;
        const siteDist = mapSpan * 0.40;
        const held = radius * 5.2;
        const approach = radius * 1.45;
        const flightDist = radius * (5.35 + 0.85 * Math.sin(p * Math.PI));
        dist = siteDist + (held - siteDist) * zoom;
        dist = dist + (flightDist - dist) * fly * (1 - descend);
        dist = dist + (approach - dist) * descend;
        dist = dist + (radius * 0.92 - dist) * walk * (1 - facade);
        dist = dist + (radius * 0.52 - dist) * facade;
        const lift = ease(Math.max(0, Math.min(1, (t - 64.6) / 2.2)));
        dist = dist + (radius * 0.96 - dist) * lift;
        pitch = pitch + (1.05 - pitch) * lift;
        const sway = Math.sin((t - 16) * 0.55) * 0.22 * (1 - descend) * ease(Math.min(1, Math.max(0, (t - 15.5) / 2.2)));
        const carried = t < 18.6 ? sway : handoff;
        yaw = carried * (1 - fly) + (handoff + sweep * p) * fly + pan * 0.55 * descend;
        yaw += ease(Math.max(0, Math.min(1, (t - 65) / 3.2))) * 0.42;
        const around = Math.sin(p * Math.PI);
        const aimX = cx + (MAP.bank[0] - cx) * 0.16 * around;
        const aimY = cy + (MAP.bank[1] - cy) * 0.16 * around;
        const lookX = MAP.focus[0] + (cx - MAP.focus[0]) * zoom;
        const lookY = MAP.focus[1] + (cy - MAP.focus[1]) * zoom;
        const bridgeHold = ease(Math.max(0, Math.min(1, (t - 47.6) / 1.8))) * (1 - ease(Math.max(0, Math.min(1, (t - 59.2) / 1.8))));
        const home = ease(Math.max(0, Math.min(1, (t - 59.4) / 5.4))) * (1 - ease(Math.max(0, Math.min(1, (t - 66.2) / 1.6))));
        const toDoor = Math.max(descend, ease(Math.max(0, Math.min(1, (t - 46) / 4))) * fly * (1 - Math.max(bridgeHold, home)));
        targetX = lookX + (aimX - lookX) * fly;
        targetY = lookY + (aimY - lookY) * fly;
        targetX = targetX + (DOOR.x - targetX) * toDoor;
        targetY = targetY + (DOOR.y - targetY) * toDoor;
        targetX = targetX + (16 - targetX) * bridgeHold;
        targetY = targetY + (236 - targetY) * bridgeHold;
        dist = dist + (radius * 4.15 - dist) * bridgeHold;
        pitch = pitch + (0.92 - pitch) * bridgeHold;
        targetX = targetX + (cx - targetX) * home;
        targetY = targetY + (cy - targetY) * home;
        dist = dist + (radius * 2.7 - dist) * home;
        pitch = pitch + (0.82 - pitch) * home;
        const pass = ease(Math.max(0, Math.min(1, (t - 72.6) / 4.6)));
        const leave = ease(Math.max(0, Math.min(1, (t - 86.2) / 3.2)));
        const inward = pass * (1 - leave * 0.65);
        targetX -= DOOR.nx * radius * 0.9 * inward;
        targetY -= DOOR.ny * radius * 0.9 * inward;
        dist = dist * (1 - pass) + radius * 0.16 * pass;
        dist = dist + (radius * 0.78 - dist) * leave;
        const lookUp = ease(Math.max(0, Math.min(1, (t - 74.6) / 2.4))) * (1 - leave);
        pitch = pitch + (0.62 - pitch) * lookUp;
        const turrell = ease(Math.max(0, Math.min(1, (t - 76.4) / 1.1))) * (1 - ease(Math.max(0, Math.min(1, (t - 80.8) / 1.3))));
        targetX = targetX + (DOOR.x - 22 - targetX) * turrell;
        targetY = targetY + (DOOR.y - 8 - targetY) * turrell;
        dist = dist + (radius * 0.48 - dist) * turrell;
        pitch = pitch + (1.18 - pitch) * turrell;
        const withdraw = ease(Math.max(0, Math.min(1, (t - 89.4) / 4.2)));
        dist = dist + (radius * 1.08 - dist) * withdraw;
        pitch = pitch + (0.92 - pitch) * pass * (1 - inward);
        const orient = ease(Math.max(0, Math.min(1, (t - 90.5) / 8)));
        const pull = ease(Math.max(0, Math.min(1, (t - 96) / 5.6)));
        const north = Math.round(yaw / (Math.PI * 2)) * Math.PI * 2;
        yaw = yaw + (north - yaw) * Math.max(orient, pull);
        pitch = pitch + (0 - pitch) * Math.max(orient, pull);
        targetX = targetX + (cx - targetX) * orient;
        targetY = targetY + (cy - targetY) * orient;
        const frame = printFrame();
        const fit = frame.fit;
        const cover = fit * 1.35;
        const view = stageRect();
        const planDist = view.w / (83 * cover / 93.9);
        dist = dist + (radius * 2.35 - dist) * orient * (1 - pull);
        dist = dist + (planDist - dist) * pull;
        const mwA = frame.mw, mhA = frame.mh;
        const mxA = frame.mx, myA = frame.my;
        const leafX = mxA + mwA / 2;
        const leafY = myA + mhA / 2;
        const scale = view.w / dist;
        const wantX = cx - (leafX - (view.x + view.w / 2)) / scale;
        const wantY = cy - ((view.y + view.h * 0.52) - leafY) / scale;
        targetX = targetX + (wantX - targetX) * pull;
        targetY = targetY + (wantY - targetY) * pull;
      }
      const stage = stageRect();
      const placed = printFrame();
      const mw = placed.mw, mh = placed.mh, mx = placed.mx, my = placed.my;
      title.style.left = (mx + mw * 0.18) + "px";
      title.style.top = (my + mh * 0.38) + "px";
      title.style.width = (mw * 0.145) + "px";
      const fadeIn = ease(Math.max(0, Math.min(1, (t - 11.2) / 3.4)));
      const fadeOut = 1 - ease(Math.max(0, Math.min(1, (t - 17.6) / 4.2)));
      const text = writing ? fadeIn * fadeOut * (1 - plan) : 0;
      const line = (delay) => text * ease(Math.max(0, Math.min(1, (t - 11.2 - delay) / 2.6)));
      phaseEl.style.opacity = String(line(0));
      precinctEl.style.opacity = String(line(0.55));
      para1El.style.opacity = String(line(1.1));
      para2El.style.opacity = String(line(1.7));
      draw(color, wave, zoom, t, opening, descend);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  </script>
</body>
</html>
"""


def decimate(points, count=40):
    if len(points) <= count:
        return [[round(p[0], 1), round(p[1], 1)] for p in points]
    step = len(points) / count
    return [[round(points[int(i * step)][0], 1), round(points[int(i * step)][1], 1)] for i in range(count)]


def extend_bank(points, extra=1600.0):
    line = [[round(p[0], 1), round(p[1], 1)] for p in points]
    if line[0][0] > line[-1][0]:
        line = list(reversed(line))

    def outward(tip, inner):
        dx, dy = tip[0] - inner[0], tip[1] - inner[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        return [round(tip[0] + dx / length * extra, 1), round(tip[1] + dy / length * extra, 1)]

    left = outward(line[0], line[min(5, len(line) - 1)])
    right = outward(line[-1], line[max(0, len(line) - 6)])
    return [left] + line + [right]


def valley_contours(south_bank, x0, x1, steps=5, gap=38.0):
    bank = sorted(south_bank, key=lambda p: p[0])
    xs = [p[0] for p in bank]

    def bank_y(x):
        if x <= xs[0]:
            return bank[0][1]
        if x >= xs[-1]:
            return bank[-1][1]
        for i in range(1, len(xs)):
            if xs[i] >= x:
                span = xs[i] - xs[i - 1] or 1
                t = (x - xs[i - 1]) / span
                return bank[i - 1][1] + (bank[i][1] - bank[i - 1][1]) * t
        return bank[-1][1]

    samples = []
    x = x0
    while x <= x1:
        samples.append(x)
        x += 42
    return [
        [[round(sx, 1), round(bank_y(sx) - gap * i, 1)] for sx in samples]
        for i in range(1, steps + 1)
    ]


def scheme_lines(raw, site, south_bank):
    lines = []

    def add(pts, weight, close=False, limit=48):
        if len(pts) < 2:
            return
        lines.append({"pts": decimate(pts, limit), "w": weight, "close": close})

    for bank in (south_bank, raw["water"]["north"]):
        add(bank, 1.35, limit=len(bank) + 1)
    for contour in valley_contours(south_bank, min(p[0] for p in site), max(p[0] for p in site)):
        add(contour, 0.65, limit=36)
    add(site, 1.2, close=True, limit=80)
    kept = []
    for key in ("crowchild", "bow_trail", "memorial", "st11"):
        for part in raw["roads"].get(key, []):
            if len(part) < 2:
                continue
            span = ((part[-1][0] - part[0][0]) ** 2 + (part[-1][1] - part[0][1]) ** 2) ** 0.5
            if span > 180:
                kept.append((span, part))
    for part in raw["rail"]:
        if len(part) >= 2:
            span = ((part[-1][0] - part[0][0]) ** 2 + (part[-1][1] - part[0][1]) ** 2) ** 0.5
            if span > 180:
                kept.append((span, part))
    for span, part in sorted(kept, reverse=True)[:10]:
        add(part, 0.9, limit=32)
    return lines


def figure_ground():
    raw = json.loads((ROOT / "westvillage.json").read_text())
    site = raw["site"]
    xs = [p[0] for p in site]
    ys = [p[1] for p in site]
    south = extend_bank(raw["water"]["south"])
    north = extend_bank(raw["water"]["north"])
    focus_x = (min(xs) + max(xs)) / 2
    bank_pts = sorted(raw["water"]["south"], key=lambda p: p[0])
    bank = min(bank_pts, key=lambda p: abs(p[0] - focus_x))
    return {
        "focus": [round(focus_x, 1), round((min(ys) + max(ys)) / 2, 1)],
        "span": [round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)],
        "banks": [south, north],
        "river": south + list(reversed(north)),
        "site": decimate(site, 80),
        "contours": valley_contours(raw["water"]["south"], min(xs), max(xs)),
        "bank": [round(bank[0], 1), round(bank[1], 1)],
        "lines": scheme_lines(raw, site, raw["water"]["south"]),
        "roads": [
            decimate(part, 28)
            for parts in list(raw["roads"].values()) + [raw["rail"]]
            for part in parts
            if len(part) >= 2
        ],
        "rail": [decimate(part, 36) for part in raw["rail"] if len(part) >= 2],
        "buildings": [
            {
                "cx": round(b["cx"], 1),
                "cy": round(b["cy"], 1),
                "pts": decimate(b["pts"], 12),
            }
            for b in raw["buildings"]
        ],
    }


def place_lenses(found, focus):
    centers = []
    for b in found:
        fp = b["footprint"]
        centers.append((sum(p[0] for p in fp) / len(fp), sum(p[1] for p in fp) / len(fp)))
    mx = sum(c[0] for c in centers) / len(centers)
    my = sum(c[1] for c in centers) / len(centers)
    size = 0.46
    placed = []
    for b, (cx, cy) in zip(found, centers):
        height = b["z1"] - b["z0"]
        ox = (cx - mx) * size + focus[0]
        oy = (cy - my) * size + focus[1]
        placed.append({
            "z0": 0,
            "z1": round(height * size, 1),
            "footprint": decimate(
                [[(p[0] - cx) * size + ox, (p[1] - cy) * size + oy] for p in b["footprint"]],
                36,
            ),
        })
    return placed


def main():
    ground = figure_ground()
    data = place_lenses(buildings(), ground["focus"])
    page = PAGE.replace("__DATA__", json.dumps(data)).replace("__MAP__", json.dumps(ground))
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(data)} buildings)")


if __name__ == "__main__":
    main()
