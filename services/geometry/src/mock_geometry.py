"""Mock geometry analysis for development without pythonocc.

Generates plausible FaceInfo and ThicknessAnalysis data using a seeded
random generator so the same part_id always produces the same results
but different parts get different analysis.
"""

import hashlib
import math
import random

from .face_analysis import FaceInfo
from .wall_thickness import ThicknessResult, ThicknessAnalysis


def _seed_from_id(part_id: str) -> int:
    return int(hashlib.md5(part_id.encode()).hexdigest()[:8], 16)


def mock_analyze_faces(part_id: str, pull_direction: list[float]) -> list[FaceInfo]:
    rng = random.Random(_seed_from_id(part_id))
    face_count = rng.randint(18, 40)
    faces = []

    surface_types = ["planar"] * 10 + ["cylindrical"] * 4 + ["conical"] + ["spherical"] + ["bspline"] * 2
    pull = pull_direction

    for i in range(face_count):
        stype = rng.choice(surface_types)
        area = rng.uniform(2.0, 120.0)

        if stype == "planar":
            # Generate a random normal
            nx = rng.gauss(0, 1)
            ny = rng.gauss(0, 1)
            nz = rng.gauss(0, 1)
            mag = math.sqrt(nx*nx + ny*ny + nz*nz)
            normal = [nx/mag, ny/mag, nz/mag]

            dot = sum(a*b for a, b in zip(normal, pull))
            angle_from_pull = math.degrees(math.acos(min(abs(dot), 1.0)))
            draft_angle = 90.0 - angle_from_pull

            is_undercut = dot < -0.01 and abs(draft_angle) > 5.0
        elif stype == "cylindrical":
            normal = [rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)]
            mag = math.sqrt(sum(x*x for x in normal))
            normal = [x/mag for x in normal]
            draft_angle = rng.uniform(0, 15)
            is_undercut = rng.random() < 0.1
        else:
            normal = None
            draft_angle = None
            is_undercut = rng.random() < 0.05

        faces.append(FaceInfo(
            index=i,
            surface_type=stype,
            area=area,
            normal=normal,
            draft_angle_deg=draft_angle,
            is_undercut=is_undercut,
        ))

    # Force a few interesting issues for realism
    # Ensure at least 2-4 faces have low/zero draft
    low_draft_candidates = [f for f in faces if f.draft_angle_deg is not None and f.surface_type == "planar"]
    for f in low_draft_candidates[:rng.randint(2, 4)]:
        f.draft_angle_deg = rng.uniform(0.0, 0.3)
    for f in low_draft_candidates[4:4 + rng.randint(1, 3)]:
        f.draft_angle_deg = rng.uniform(0.3, 0.9)
    # Ensure 1-2 undercuts
    non_undercut = [f for f in faces if not f.is_undercut and f.surface_type == "planar"]
    for f in non_undercut[:rng.randint(1, 2)]:
        f.is_undercut = True

    return faces


def mock_analyze_wall_thickness(part_id: str) -> ThicknessAnalysis:
    rng = random.Random(_seed_from_id(part_id) + 1)
    sample_count = rng.randint(60, 120)
    face_count = rng.randint(18, 40)

    samples = []
    # Create a baseline thickness with some variation
    nominal = rng.uniform(1.2, 2.5)
    for i in range(sample_count):
        fidx = rng.randint(0, face_count - 1)
        # Most samples near nominal, some outliers
        if rng.random() < 0.08:
            thickness = rng.uniform(0.3, 0.7)  # Thin spot
        elif rng.random() < 0.1:
            thickness = rng.uniform(3.0, 4.5)  # Thick spot
        else:
            thickness = nominal + rng.gauss(0, nominal * 0.15)
            thickness = max(0.4, thickness)

        samples.append(ThicknessResult(
            point=[rng.uniform(-20, 20), rng.uniform(-15, 15), rng.uniform(-10, 10)],
            thickness=round(thickness, 3),
            face_index=fidx,
        ))

    return ThicknessAnalysis(samples)
