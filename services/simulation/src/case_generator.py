"""OpenFOAM interFoam (VOF) case-file generator for injection-molding fills.

Everything is produced programmatically as strings — no external template engine.
The generated case directory is a self-contained OpenFOAM case that can be run
via:

    blockMesh && snappyHexMesh -overwrite && interFoam

All values are in SI units (metres, seconds, kg, Pa). Parts come in mm from
pythonocc, so the case_params expect mm and we convert here.

Physics (v1, simplified):
  • Two-phase VOF: polymer (α=1) + air (α=0)
  • Both Newtonian (Cross-WLF comes in a later session)
  • Isothermal (no energy eqn yet)
  • Laminar (Re ≪ 1)
  • Gravity included but minor at these scales
  • No surface tension yet (can add with σ in transportProperties)

Defaults are ABS-like:
  ρ_polymer = 1000 kg/m³, η_polymer = 1000 Pa·s
  ρ_air = 1.2 kg/m³, η_air = 1.8e-5 Pa·s
  U_inlet = 0.1 m/s at the gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent


@dataclass
class CaseParams:
    """All inputs needed to generate an interFoam case. Units as noted."""
    # Geometry bbox of the STL (mm)
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]

    # Gate location in mm (world coords, must be inside the cavity)
    gate_pos_mm: tuple[float, float, float]
    gate_radius_mm: float = 3.0

    # Mesh density
    block_mesh_cells_per_axis: int = 32        # background cube cell count on longest axis
    snappy_refinement_level: tuple[int, int] = (1, 2)   # (min, max) surface refinement

    # Material
    polymer_density: float = 1000.0            # kg/m³
    polymer_viscosity: float = 1000.0          # Pa·s (Newtonian)
    air_density: float = 1.2                   # kg/m³
    air_viscosity: float = 1.8e-5              # Pa·s
    surface_tension: float = 0.03              # N/m

    # Flow
    inlet_velocity: float = 0.1                # m/s

    # Time-stepping
    end_time_s: float = 2.0                    # simulated seconds (enough to fill most shells)
    delta_t_s: float = 1e-4                    # initial timestep; adaptive from there
    write_interval_s: float = 0.02             # GUI frame cadence
    max_cfl: float = 0.5

    # Parallelism
    n_procs: int = 4

    # Padding around the bbox for the background mesh (mm). Background must
    # fully enclose the STL by at least 1-2 cell widths.
    padding_mm: float = 5.0


def _fmt_vec(v: tuple[float, float, float], scale: float = 1.0) -> str:
    return f"({v[0] * scale:.6g} {v[1] * scale:.6g} {v[2] * scale:.6g})"


def _foam_header(class_name: str, object_name: str, location: str = '"system"') -> str:
    return dedent(f"""\
        /*--------------------------------*- C++ -*----------------------------------*\\
        | MoldMind auto-generated interFoam case                                        |
        \\*---------------------------------------------------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       {class_name};
            location    {location};
            object      {object_name};
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
        """)


# ─── system/ ────────────────────────────────────────────────────────────────

def block_mesh_dict(p: CaseParams) -> str:
    # Pad the background cube so snappyHexMesh has room to carve the STL
    x0 = (p.bbox_min_mm[0] - p.padding_mm) / 1000.0
    y0 = (p.bbox_min_mm[1] - p.padding_mm) / 1000.0
    z0 = (p.bbox_min_mm[2] - p.padding_mm) / 1000.0
    x1 = (p.bbox_max_mm[0] + p.padding_mm) / 1000.0
    y1 = (p.bbox_max_mm[1] + p.padding_mm) / 1000.0
    z1 = (p.bbox_max_mm[2] + p.padding_mm) / 1000.0
    lx, ly, lz = x1 - x0, y1 - y0, z1 - z0
    lmax = max(lx, ly, lz, 1e-9)
    nx = max(4, int(round(p.block_mesh_cells_per_axis * lx / lmax)))
    ny = max(4, int(round(p.block_mesh_cells_per_axis * ly / lmax)))
    nz = max(4, int(round(p.block_mesh_cells_per_axis * lz / lmax)))
    return _foam_header("dictionary", "blockMeshDict") + dedent(f"""\
        scale   1;

        vertices
        (
            ({x0:.6g} {y0:.6g} {z0:.6g})   // 0
            ({x1:.6g} {y0:.6g} {z0:.6g})   // 1
            ({x1:.6g} {y1:.6g} {z0:.6g})   // 2
            ({x0:.6g} {y1:.6g} {z0:.6g})   // 3
            ({x0:.6g} {y0:.6g} {z1:.6g})   // 4
            ({x1:.6g} {y0:.6g} {z1:.6g})   // 5
            ({x1:.6g} {y1:.6g} {z1:.6g})   // 6
            ({x0:.6g} {y1:.6g} {z1:.6g})   // 7
        );

        blocks
        (
            hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
        );

        edges ();

        // Whole background box is a single patch; snappy will split it up.
        boundary
        (
            walls
            {{
                type wall;
                faces
                (
                    (0 4 7 3)  // xMin
                    (2 6 5 1)  // xMax
                    (1 5 4 0)  // yMin
                    (3 7 6 2)  // yMax
                    (0 3 2 1)  // zMin
                    (4 5 6 7)  // zMax
                );
            }}
        );

        mergePatchPairs ();
        """)


def snappy_hex_mesh_dict(p: CaseParams) -> str:
    # Gate is a small sphere used as a refinement region (not a patch — that's
    # set up in createPatchDict after snappy defines walls).
    gx, gy, gz = (c / 1000.0 for c in p.gate_pos_mm)
    gr = p.gate_radius_mm / 1000.0
    # Refinement centre: a point known to be inside the cavity
    cx = (p.bbox_min_mm[0] + p.bbox_max_mm[0]) / 2000.0
    cy = (p.bbox_min_mm[1] + p.bbox_max_mm[1]) / 2000.0
    cz = (p.bbox_min_mm[2] + p.bbox_max_mm[2]) / 2000.0
    lo, hi = p.snappy_refinement_level
    return _foam_header("dictionary", "snappyHexMeshDict") + dedent(f"""\
        castellatedMesh true;
        snap            true;
        addLayers       false;

        geometry
        {{
            part.stl
            {{
                type triSurfaceMesh;
                name cavity;
            }}
            gateRegion
            {{
                type searchableSphere;
                centre ({gx:.6g} {gy:.6g} {gz:.6g});
                radius {gr * 3:.6g};
            }}
        }};

        castellatedMeshControls
        {{
            maxLocalCells 1000000;
            maxGlobalCells 2000000;
            minRefinementCells 10;
            maxLoadUnbalance 0.10;
            nCellsBetweenLevels 2;

            features ();

            refinementSurfaces
            {{
                cavity
                {{
                    level ({lo} {hi});
                    patchInfo {{ type wall; }}
                }}
            }}

            resolveFeatureAngle 30;

            refinementRegions
            {{
                gateRegion
                {{
                    mode inside;
                    levels (( 1.0 {hi} ));
                }}
            }}

            // A point known to be inside the cavity (melt region)
            locationInMesh ({cx:.6g} {cy:.6g} {cz:.6g});
            allowFreeStandingZoneFaces true;
        }}

        snapControls
        {{
            nSmoothPatch 3;
            tolerance 2.0;
            nSolveIter 30;
            nRelaxIter 5;
            nFeatureSnapIter 10;
            implicitFeatureSnap false;
            explicitFeatureSnap true;
            multiRegionFeatureSnap false;
        }}

        addLayersControls
        {{
            relativeSizes true;
            layers {{}}
            expansionRatio 1.0;
            finalLayerThickness 0.3;
            minThickness 0.1;
        }}

        meshQualityControls
        {{
            maxNonOrtho 65;
            maxBoundarySkewness 20;
            maxInternalSkewness 4;
            maxConcave 80;
            minVol 1e-13;
            minTetQuality 1e-15;
            minArea -1;
            minTwist 0.02;
            minDeterminant 0.001;
            minFaceWeight 0.02;
            minVolRatio 0.01;
            minTriangleTwist -1;
            nSmoothScale 4;
            errorReduction 0.75;
        }}

        mergeTolerance 1e-6;
        """)


def control_dict(p: CaseParams) -> str:
    return _foam_header("dictionary", "controlDict") + dedent(f"""\
        application     interFoam;

        startFrom       startTime;
        startTime       0;

        stopAt          endTime;
        endTime         {p.end_time_s:.6g};

        deltaT          {p.delta_t_s:.6g};

        writeControl    adjustable;
        writeInterval   {p.write_interval_s:.6g};

        purgeWrite      0;

        writeFormat     binary;
        writePrecision  8;
        writeCompression off;

        timeFormat      general;
        timePrecision   6;

        runTimeModifiable yes;

        adjustTimeStep  yes;
        maxCo           {p.max_cfl:.4g};
        maxAlphaCo      {p.max_cfl:.4g};
        maxDeltaT       0.01;
        """)


def fv_schemes() -> str:
    return _foam_header("dictionary", "fvSchemes") + dedent("""\
        ddtSchemes      { default Euler; }

        gradSchemes
        {
            default         Gauss linear;
        }

        divSchemes
        {
            div(rhoPhi,U)     Gauss linearUpwind grad(U);
            div(phi,alpha)    Gauss vanLeer;
            div(phirb,alpha)  Gauss linear;
            div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
            default           none;
        }

        laplacianSchemes
        {
            default Gauss linear corrected;
        }

        interpolationSchemes { default linear; }
        snGradSchemes        { default corrected; }
        """)


def fv_solution() -> str:
    return _foam_header("dictionary", "fvSolution") + dedent("""\
        solvers
        {
            "alpha.polymer.*"
            {
                nAlphaCorr        2;
                nAlphaSubCycles   1;
                cAlpha            1;
                MULESCorr         yes;
                nLimiterIter      5;
                solver            smoothSolver;
                smoother          symGaussSeidel;
                tolerance         1e-8;
                relTol            0;
            }

            "pcorr.*"
            {
                solver            GAMG;
                smoother          DIC;
                tolerance         1e-5;
                relTol            0;
            }

            p_rgh
            {
                solver            GAMG;
                smoother          DIC;
                tolerance         1e-7;
                relTol            0.05;
            }

            p_rghFinal
            {
                $p_rgh;
                relTol            0;
            }

            U
            {
                solver            smoothSolver;
                smoother          symGaussSeidel;
                tolerance         1e-6;
                relTol            0;
            }
        }

        PIMPLE
        {
            momentumPredictor      no;
            nOuterCorrectors       1;
            nCorrectors            3;
            nNonOrthogonalCorrectors 0;
        }

        relaxationFactors
        {
            equations { ".*" 1; }
        }
        """)


def decompose_par_dict(p: CaseParams) -> str:
    # Simple scotch decomposition
    return _foam_header("dictionary", "decomposeParDict") + dedent(f"""\
        numberOfSubdomains {p.n_procs};
        method scotch;
        """)


# ─── constant/ ──────────────────────────────────────────────────────────────

def transport_properties(p: CaseParams) -> str:
    nu_poly = p.polymer_viscosity / p.polymer_density   # kinematic viscosity m²/s
    nu_air = p.air_viscosity / p.air_density
    return _foam_header("dictionary", "transportProperties", location='"constant"') + dedent(f"""\
        phases (polymer air);

        polymer
        {{
            transportModel  Newtonian;
            nu              {nu_poly:.6g};
            rho             {p.polymer_density:.6g};
        }}

        air
        {{
            transportModel  Newtonian;
            nu              {nu_air:.6g};
            rho             {p.air_density:.6g};
        }}

        sigma           {p.surface_tension:.6g};
        """)


def turbulence_properties() -> str:
    return _foam_header("dictionary", "turbulenceProperties", location='"constant"') + dedent("""\
        simulationType  laminar;
        """)


def g_field() -> str:
    return _foam_header("uniformDimensionedVectorField", "g", location='"constant"') + dedent("""\
        dimensions      [0 1 -2 0 0 0 0];
        value           (0 0 -9.81);
        """)


# ─── 0/ ────────────────────────────────────────────────────────────────────

def initial_alpha(p: CaseParams) -> str:
    # Entire domain starts as air; polymer is injected at the gate patch.
    # snappyHexMesh gave us a single "cavity" patch (walls). The gate patch
    # is created in a post-step via createPatchDict (session 2). For v1 we
    # just set up the file skeleton — actual BC patching comes later.
    return _foam_header("volScalarField", "alpha.polymer", location='"0"') + dedent("""\
        dimensions      [0 0 0 0 0 0 0];
        internalField   uniform 0;

        boundaryField
        {
            cavity
            {
                type            zeroGradient;   // walls: no polymer flux
            }
            gate
            {
                type            fixedValue;
                value           uniform 1;      // pure polymer at the gate
            }
            outlet
            {
                type            inletOutlet;
                inletValue      uniform 0;
                value           uniform 0;
            }
        }
        """)


def initial_u(p: CaseParams) -> str:
    # Direction: gate → cavity interior. We default to -Y (top→bottom) which
    # matches the "top_z" gate default in the simple model. Session 2 will
    # compute the correct direction from the gate normal.
    u = p.inlet_velocity
    return _foam_header("volVectorField", "U", location='"0"') + dedent(f"""\
        dimensions      [0 1 -1 0 0 0 0];
        internalField   uniform (0 0 0);

        boundaryField
        {{
            cavity
            {{
                type            noSlip;
            }}
            gate
            {{
                type            fixedValue;
                value           uniform (0 -{u:.6g} 0);
            }}
            outlet
            {{
                type            pressureInletOutletVelocity;
                value           uniform (0 0 0);
            }}
        }}
        """)


def initial_p_rgh() -> str:
    return _foam_header("volScalarField", "p_rgh", location='"0"') + dedent("""\
        dimensions      [1 -1 -2 0 0 0 0];
        internalField   uniform 0;

        boundaryField
        {
            cavity
            {
                type            fixedFluxPressure;
                value           uniform 0;
            }
            gate
            {
                type            fixedFluxPressure;
                value           uniform 0;
            }
            outlet
            {
                type            totalPressure;
                p0              uniform 0;
                value           uniform 0;
            }
        }
        """)


# ─── Orchestrator ──────────────────────────────────────────────────────────

def write_case_dir(case_dir: str | Path, p: CaseParams) -> dict[str, str]:
    """Generate all case files into case_dir. Returns a map of
    relative_path → file contents (also written to disk)."""
    case = Path(case_dir)
    (case / "system").mkdir(parents=True, exist_ok=True)
    (case / "constant" / "triSurface").mkdir(parents=True, exist_ok=True)
    (case / "0").mkdir(parents=True, exist_ok=True)

    files = {
        "system/blockMeshDict": block_mesh_dict(p),
        "system/snappyHexMeshDict": snappy_hex_mesh_dict(p),
        "system/controlDict": control_dict(p),
        "system/fvSchemes": fv_schemes(),
        "system/fvSolution": fv_solution(),
        "system/decomposeParDict": decompose_par_dict(p),
        "constant/transportProperties": transport_properties(p),
        "constant/turbulenceProperties": turbulence_properties(),
        "constant/g": g_field(),
        "0/alpha.polymer": initial_alpha(p),
        "0/U": initial_u(p),
        "0/p_rgh": initial_p_rgh(),
    }
    for rel_path, content in files.items():
        (case / rel_path).write_text(content)
    return files
