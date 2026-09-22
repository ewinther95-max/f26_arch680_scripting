"""
ARCH 680 — 10 x 30 grid (same 300 points as 30 x 10).

Nested loops build a uniform Cartesian field of points.
Next workshop these become Turbulence.
"""

from pathlib import Path

COLS = 30
ROWS = 10

WIDTH = 1600
HEIGHT = 620
MARGIN_X = 70
MARGIN_Y = 90
POINT_RADIUS = 5
GLOW_RADIUS = 16


def make_grid(cols=COLS, rows=ROWS, width=WIDTH, height=HEIGHT):
    """Return a list of (x, y) centers for a cols-by-rows grid."""
    usable_w = width - 2 * MARGIN_X
    usable_h = height - 2 * MARGIN_Y
    step_x = usable_w / (cols - 1)
    step_y = usable_h / (rows - 1)
    points = []
    for row in range(rows):
        for col in range(cols):
            x = MARGIN_X + col * step_x
            y = MARGIN_Y + row * step_y
            points.append((x, y))
    return points


def _add_glow(pixels, cx, cy, width, height):
    r = GLOW_RADIUS
    x0 = max(0, int(cx) - r)
    x1 = min(width, int(cx) + r + 1)
    y0 = max(0, int(cy) - r)
    y1 = min(height, int(cy) + r + 1)
    for y in range(y0, y1):
        dy = y - cy
        row = pixels[y]
        for x in range(x0, x1):
            dx = x - cx
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > r:
                continue
            t = dist / r
            # core disk + soft falloff
            if dist <= POINT_RADIUS:
                add = 1.0
            else:
                add = (1.0 - t) ** 2
            r0, g0, b0 = row[x]
            v = min(255, int(r0 + 230 * add))
            row[x] = (v, v, min(255, int(b0 + 220 * add)))


def render_ppm(points, path: Path, width=WIDTH, height=HEIGHT):
    bg = (12, 12, 14)
    pixels = [[bg for _ in range(width)] for _ in range(height)]
    for x, y in points:
        _add_glow(pixels, x, y, width, height)

    with path.open("wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        for row in pixels:
            f.write(bytes(c for rgb in row for c in rgb))


def main():
    points = make_grid()
    assert len(points) == COLS * ROWS
    print(f"{ROWS} x {COLS} grid")
    print(f"{len(points)} points")
    print("interactive attractor lives in grid.html")


if __name__ == "__main__":
    main()
