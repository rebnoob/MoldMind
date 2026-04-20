"use client";

import { useRef, useEffect, useState, useMemo, Suspense } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface FillMeta {
  max_time: number;
  voxel_grid: [number, number, number];
  pitch_mm: number;
  gate_world: { x: number; y: number; z: number };
  active_voxels: number;
  vertex_count: number;
}

interface FillTimeViewerProps {
  meshUrl: string;
  fillTimeUrl: string;
  meta: FillMeta;
  partId?: string;
}

// Defaults for the melt-temperature mapping.
// T_inj = injection / melt temperature at the gate
// T_wall = mold wall / coolest reachable temperature
const DEFAULT_T_INJ = 250;  // °C (ABS-ish thermoplastic)
const DEFAULT_T_WALL = 30;  // °C

const VERT_SHADER = `
  attribute float fillTime;
  varying float vFillTime;
  varying vec3 vNormal;
  void main() {
    vFillTime = fillTime;
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// Temperature field: T = T_wall + (T_inj - T_wall) * exp(-fillTime / decayLen)
// (Arrhenius-like spatial decay, same form as hele_shaw_step.py)
// We don't need T_inj/T_wall in the shader — we colorize by the fraction u ∈ [0, 1].
// u = (T - T_wall) / (T_inj - T_wall) = exp(-fillTime / decayLen)
// Colormap: u=1 (hot, at gate) → red ; u=0 (cool, far) → blue. Matches Moldex3D.
const FRAG_SHADER = `
  precision highp float;
  uniform float uCurrentTime;
  uniform float uMaxTime;
  uniform float uDecayLen;       // mm — characteristic cooling length
  uniform float uRemapMin;       // min u actually observed (for full-range colormap)
  uniform bool  uRemap;          // stretch u ∈ [uRemapMin, 1] → [0, 1] before color lookup
  uniform float uOpacityUnfilled;
  varying float vFillTime;
  varying vec3 vNormal;

  vec3 jet(float t) {
    float r = clamp(1.5 - abs(4.0 * t - 3.0), 0.0, 1.0);
    float g = clamp(1.5 - abs(4.0 * t - 2.0), 0.0, 1.0);
    float b = clamp(1.5 - abs(4.0 * t - 1.0), 0.0, 1.0);
    return vec3(r, g, b);
  }

  void main() {
    float u = exp(-vFillTime / max(uDecayLen, 1e-6));      // temperature fraction
    if (uRemap) {
      u = clamp((u - uRemapMin) / max(1.0 - uRemapMin, 1e-6), 0.0, 1.0);
    }
    bool reached = vFillTime <= uCurrentTime;
    vec3 color;
    float alpha;
    if (reached) {
      // jet(1) → red (hot), jet(0) → blue (cool)
      color = jet(u);
      alpha = 1.0;
    } else {
      color = vec3(0.25, 0.27, 0.32);
      alpha = uOpacityUnfilled;
      if (alpha < 0.01) discard;
    }
    vec3 light = normalize(vec3(0.5, 0.8, 1.0));
    float lambert = clamp(dot(vNormal, light), 0.25, 1.0);
    gl_FragColor = vec4(color * lambert, alpha);
  }
`;

function GatePin({ pos }: { pos: [number, number, number] }) {
  return (
    <mesh position={pos}>
      <sphereGeometry args={[1.2, 16, 16]} />
      <meshBasicMaterial color="#ffffff" />
    </mesh>
  );
}

function FillMesh({
  meshUrl, fillTimes, maxTime, currentTime, opacityUnfilled, gateWorld,
  decayLen, remap,
}: {
  meshUrl: string;
  fillTimes: Float32Array;
  maxTime: number;
  currentTime: number;
  opacityUnfilled: number;
  gateWorld: { x: number; y: number; z: number };
  decayLen: number;
  remap: boolean;
}) {
  const gltf = useLoader(GLTFLoader, meshUrl);
  const groupRef = useRef<THREE.Group>(null);
  const matRef = useRef<THREE.ShaderMaterial | null>(null);
  const [centerOffset, setCenterOffset] = useState<THREE.Vector3 | null>(null);
  const { camera } = useThree();
  const [fitted, setFitted] = useState(false);

  // Build the shader material once
  const material = useMemo(() => {
    const mat = new THREE.ShaderMaterial({
      vertexShader: VERT_SHADER,
      fragmentShader: FRAG_SHADER,
      uniforms: {
        uCurrentTime: { value: 0 },
        uMaxTime: { value: maxTime },
        uDecayLen: { value: decayLen },
        uRemapMin: { value: Math.exp(-maxTime / Math.max(decayLen, 1e-6)) },
        uRemap: { value: remap },
        uOpacityUnfilled: { value: opacityUnfilled },
      },
      side: THREE.DoubleSide,
      transparent: true,
    });
    matRef.current = mat;
    return mat;
  }, [maxTime]);

  // Wire the mesh + attach fillTime attribute
  useEffect(() => {
    if (!groupRef.current) return;
    const scene = gltf.scene.clone(true);
    scene.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const geo = child.geometry as THREE.BufferGeometry;
        // Ensure per-vertex fillTime attribute matches the mesh vertex count.
        // Mesh is non-indexed (flat): vertex_count === 3 * triangle_count.
        const posCount = (geo.getAttribute("position") as THREE.BufferAttribute).count;
        let ft = fillTimes;
        if (ft.length !== posCount) {
          // Fallback: clamp or tile
          const buf = new Float32Array(posCount);
          for (let i = 0; i < posCount; i++) buf[i] = ft[Math.min(i, ft.length - 1)];
          ft = buf;
        }
        geo.setAttribute("fillTime", new THREE.BufferAttribute(ft, 1));
        child.material = material;
      }
    });
    while (groupRef.current.children.length > 0) groupRef.current.remove(groupRef.current.children[0]);
    groupRef.current.add(scene);

    if (!fitted) {
      const box = new THREE.Box3().setFromObject(groupRef.current);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      groupRef.current.position.sub(center);
      setCenterOffset(center.clone());
      const maxDim = Math.max(size.x, size.y, size.z);
      if (camera instanceof THREE.PerspectiveCamera) {
        camera.position.set(maxDim * 1.8, maxDim * 1.2, maxDim * 1.8);
        camera.lookAt(0, 0, 0);
        camera.updateProjectionMatrix();
      }
      setFitted(true);
    }
  }, [gltf, material, fillTimes, camera, fitted]);

  // Update uniforms as user scrubs timeline
  useEffect(() => {
    if (matRef.current) {
      matRef.current.uniforms.uCurrentTime.value = currentTime;
      matRef.current.uniforms.uMaxTime.value = maxTime;
      matRef.current.uniforms.uDecayLen.value = decayLen;
      matRef.current.uniforms.uRemapMin.value = Math.exp(-maxTime / Math.max(decayLen, 1e-6));
      matRef.current.uniforms.uRemap.value = remap;
      matRef.current.uniforms.uOpacityUnfilled.value = opacityUnfilled;
    }
  }, [currentTime, maxTime, decayLen, remap, opacityUnfilled]);

  const gatePos: [number, number, number] | null = centerOffset
    ? [gateWorld.x - centerOffset.x, gateWorld.y - centerOffset.y, gateWorld.z - centerOffset.z]
    : null;

  return (
    <group ref={groupRef}>
      {gatePos && <GatePin pos={gatePos} />}
    </group>
  );
}

function ColorLegend({ tInj, tWall, decayFrac, remap }: { tInj: number; tWall: number; decayFrac: number; remap: boolean }) {
  // With remap off, the bottom of the palette corresponds to the coolest T actually reached,
  // which is T_wall + (T_inj - T_wall) * exp(-1/decayFrac), not pure T_wall.
  const tBottom = remap ? tWall : tWall + (tInj - tWall) * Math.exp(-1 / Math.max(decayFrac, 1e-6));
  // Gradient is inverted to match the shader: top = hot (red = gate), bottom = cool (blue = flow end).
  const stops: string[] = [];
  for (let i = 0; i <= 8; i++) {
    const t = i / 8;
    const u = 1 - t;  // invert so t=0 (top) → red, t=1 (bottom) → blue
    const r = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * u - 3)));
    const g = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * u - 2)));
    const b = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * u - 1)));
    stops.push(`rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}) ${t * 100}%`);
  }
  const gradient = `linear-gradient(to bottom, ${stops.join(", ")})`;
  return (
    <div className="absolute top-4 right-4 text-white text-[10px] font-mono flex items-center gap-1.5 bg-black/40 backdrop-blur-sm rounded p-2">
      <div className="flex flex-col justify-between h-40">
        <span>{tInj.toFixed(0)} °C</span>
        <span className="text-gray-300">temperature</span>
        <span>{tBottom.toFixed(0)} °C</span>
      </div>
      <div style={{ width: 12, height: 160, background: gradient, borderRadius: 2 }} />
    </div>
  );
}

type SolverMode = "auto" | "simple" | "openfoam";

interface OpenFoamStatus {
  available: boolean;
  reason?: string;
  message?: string;
  next_steps?: string[];
  container?: string;
}

interface SolverAlternative {
  solver: string;
  name: string;
  available: boolean;
  runtime_estimate: string;
  tradeoff: string;
}

interface SolverRecommendation {
  recommended: "hele_shaw_2d" | "fmm_3d" | "stokes_3d" | "vof_3d";
  name: string;
  available: boolean;
  confidence: string;
  runtime_estimate: string;
  reasoning: string[];
  ignores: string[];
  physics: string[];
  derived: {
    aspect_ratio_h_over_L: number;
    reynolds_number: number;
    stokes_regime: boolean;
    median_thickness_mm: number;
    flow_length_mm: number;
    thickness_range_mm: [number, number];
    thickness_uniformity: number;
    undercut_count: number;
  };
  alternatives: SolverAlternative[];
}

// Maps the selector's choice onto the concrete UI mode we render.
function recToUiMode(rec: SolverRecommendation["recommended"]): SolverMode {
  // hele_shaw_2d / fmm_3d → we have these wired (Simple shows the 3D viewer,
  // 2D GIF is in the side panel). stokes_3d / vof_3d → OpenFOAM setup card.
  if (rec === "hele_shaw_2d" || rec === "fmm_3d") return "simple";
  return "openfoam";
}

export function FillTimeViewer({ meshUrl, fillTimeUrl, meta, partId }: FillTimeViewerProps) {
  // Note: this component is now purely the 3D viewer. Mode selection
  // (Auto/Simple/OpenFOAM) + recommendation panel live in <FlowSimControls>
  // and are rendered in the right-side panel of the analysis page.
  void partId;
  const [fillTimes, setFillTimes] = useState<Float32Array | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [loopSeconds, setLoopSeconds] = useState(6);
  const [opacityUnfilled, setOpacityUnfilled] = useState(0.08);
  const [tInj, setTInj] = useState(DEFAULT_T_INJ);
  const [tWall, setTWall] = useState(DEFAULT_T_WALL);
  // Arrhenius spatial decay: T = T_wall + (T_inj - T_wall) * exp(-fillTime / decayLen)
  // Default decayLen = 65% of max fill distance, matches hele_shaw_step.py
  const [decayFrac, setDecayFrac] = useState(0.65);
  const [remapPalette, setRemapPalette] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number>(0);

  // Fetch fillTime binary on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(fillTimeUrl);
        if (!r.ok) throw new Error(`fetch ${fillTimeUrl} → ${r.status}`);
        const buf = await r.arrayBuffer();
        if (!cancelled) setFillTimes(new Float32Array(buf));
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message || e));
      }
    })();
    return () => { cancelled = true; };
  }, [fillTimeUrl]);

  // Animate currentTime on a loop when playing
  useEffect(() => {
    if (!playing) { if (rafRef.current) cancelAnimationFrame(rafRef.current); return; }
    startRef.current = performance.now() - (currentTime / meta.max_time) * loopSeconds * 1000;
    const tick = () => {
      const elapsed = (performance.now() - startRef.current) / 1000;
      const phase = (elapsed % (loopSeconds + 1.0)) / loopSeconds;
      if (phase <= 1.0) setCurrentTime(phase * meta.max_time);
      else setCurrentTime(meta.max_time);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, loopSeconds, meta.max_time]);

  if (err) return <div className="flex items-center justify-center h-full text-sm text-red-600">Fill-time load failed: {err}</div>;
  if (!fillTimes) return <div className="flex items-center justify-center h-full"><div className="animate-spin h-8 w-8 border-2 border-brand-600 border-t-transparent rounded-full"/></div>;

  return (
    <div className="relative w-full h-full bg-gradient-to-b from-[#0b0e16] to-[#161b24]">
      <Canvas camera={{ position: [200, 150, 200], fov: 40, near: 1, far: 5000 }} dpr={[1, 2]}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[100, 200, 100]} intensity={1.0} />
        <Grid cellColor="#2a3040" sectionColor="#3a4050" infiniteGrid cellSize={10} sectionSize={50} fadeDistance={500} fadeStrength={1} />
        <Suspense fallback={null}>
          <FillMesh
            meshUrl={meshUrl}
            fillTimes={fillTimes}
            maxTime={meta.max_time}
            currentTime={currentTime}
            opacityUnfilled={opacityUnfilled}
            gateWorld={meta.gate_world}
            decayLen={meta.max_time * decayFrac}
            remap={remapPalette}
          />
        </Suspense>
        <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
      </Canvas>
      <ColorLegend tInj={tInj} tWall={tWall} decayFrac={decayFrac} remap={remapPalette} />

      {/* Timeline controls */}
      <div className="absolute bottom-0 left-0 right-0 bg-black/60 backdrop-blur-md p-3 text-white">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPlaying(p => !p)}
            className="text-xs font-medium px-2 py-1 rounded bg-white/10 hover:bg-white/20 transition"
          >
            {playing ? "❚❚ Pause" : "▶ Play"}
          </button>
          <input
            type="range"
            min={0}
            max={meta.max_time}
            step={meta.max_time / 500}
            value={currentTime}
            onChange={e => { setPlaying(false); setCurrentTime(parseFloat(e.target.value)); }}
            className="flex-1 accent-brand-500"
          />
          <span className="text-[11px] font-mono tabular-nums w-36 text-right">
            T<sub>front</sub> = {(tWall + (tInj - tWall) * Math.exp(-currentTime / Math.max(meta.max_time * decayFrac, 1e-6))).toFixed(0)} °C
            <span className="text-gray-400 ml-1">({currentTime.toFixed(0)}/{meta.max_time.toFixed(0)}mm)</span>
          </span>
        </div>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-gray-300 flex-wrap">
          <label className="flex items-center gap-1.5">
            T<sub>inj</sub>
            <input type="number" value={tInj} onChange={e => setTInj(parseFloat(e.target.value)||0)} className="w-14 bg-white/10 rounded px-1 py-0.5 font-mono"/>
            °C
          </label>
          <label className="flex items-center gap-1.5">
            T<sub>wall</sub>
            <input type="number" value={tWall} onChange={e => setTWall(parseFloat(e.target.value)||0)} className="w-14 bg-white/10 rounded px-1 py-0.5 font-mono"/>
            °C
          </label>
          <label className="flex items-center gap-1.5" title="Characteristic cooling length / max fill distance. T = T_wall + (T_inj − T_wall)·exp(−r / decayLen)">
            Decay
            <input type="range" min={0.1} max={2.0} step={0.05} value={decayFrac} onChange={e => setDecayFrac(parseFloat(e.target.value))} className="w-16 accent-brand-500"/>
            <span className="font-mono w-10">{decayFrac.toFixed(2)}×</span>
          </label>
          <label className="flex items-center gap-1.5" title="Stretch the visible temperature range to use the full blue→red palette">
            <input type="checkbox" checked={remapPalette} onChange={e => setRemapPalette(e.target.checked)} className="accent-brand-500"/>
            Full palette
          </label>
          <label className="flex items-center gap-1.5">
            Loop
            <input type="range" min={2} max={20} value={loopSeconds} onChange={e => setLoopSeconds(parseInt(e.target.value))} className="w-16 accent-brand-500"/>
            <span className="font-mono w-6">{loopSeconds}s</span>
          </label>
          <label className="flex items-center gap-1.5">
            Ghost
            <input type="range" min={0} max={0.3} step={0.01} value={opacityUnfilled} onChange={e => setOpacityUnfilled(parseFloat(e.target.value))} className="w-16 accent-brand-500"/>
            <span className="font-mono w-8">{(opacityUnfilled * 100).toFixed(0)}%</span>
          </label>
          <span className="ml-auto text-gray-400">
            Grid {meta.voxel_grid.join("×")} · pitch {meta.pitch_mm.toFixed(1)}mm · gate ({meta.gate_world.x.toFixed(1)}, {meta.gate_world.y.toFixed(1)}, {meta.gate_world.z.toFixed(1)})
          </span>
        </div>
      </div>
    </div>
  );
}

// --- Right-panel controls ----------------------------------------------------
// Rendered inside the Flow Sim tab's side panel on the analysis page. Replaces
// the mode toggle + Auto/OpenFOAM cards that used to overlay the 3D view.

interface FlowSimControlsProps {
  partId: string;
}

export function FlowSimControls({ partId }: FlowSimControlsProps) {
  const [mode, setMode] = useState<SolverMode>("simple");
  const [ofStatus, setOfStatus] = useState<OpenFoamStatus | null>(null);
  const [rec, setRec] = useState<SolverRecommendation | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recErr, setRecErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const r = await fetch(`${API_URL}/api/analysis/simulation/openfoam/status`);
        if (!r.ok) return;
        const d = await r.json();
        if (!cancelled) setOfStatus(d);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (mode !== "auto" || rec || recLoading || !partId) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) return;
    setRecLoading(true);
    setRecErr(null);
    (async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const r = await fetch(
          `${API_URL}/api/analysis/simulation/select-solver/${partId}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        setRec(await r.json());
      } catch (e: any) {
        setRecErr(String(e?.message || e));
      } finally {
        setRecLoading(false);
      }
    })();
  }, [mode, partId, rec, recLoading]);

  const btn = (m: SolverMode, label: string, sub: string, badge?: React.ReactNode) => (
    <button
      onClick={() => setMode(m)}
      className={`flex-1 px-2 py-1.5 text-[11px] font-medium rounded transition ${mode === m ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
    >
      <div>{label}</div>
      <div className="text-[9px] opacity-70 font-normal">{sub}</div>
      {badge}
    </button>
  );

  return (
    <div className="p-4">
      <div className="mb-3">
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Solver mode</span>
      </div>
      <div className="flex gap-1.5 mb-4">
        {btn("auto", "Auto", "Recommend")}
        {btn("simple", "Simple", "Hele-Shaw")}
        {btn(
          "openfoam",
          "OpenFOAM",
          "VOF · interFoam",
          ofStatus && (
            <span className={`mt-1 inline-block text-[8px] px-1 rounded ${ofStatus.available ? "bg-green-200 text-green-800" : "bg-amber-200 text-amber-800"}`}>
              {ofStatus.available ? "ready" : "setup"}
            </span>
          ),
        )}
      </div>

      {mode === "simple" && (
        <div className="p-3 rounded bg-gray-50 border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-1">Simple Model · Thickness-weighted FMM 3D</h3>
          <p className="text-[11px] text-gray-600 leading-relaxed">
            The 3D viewer shows melt-front arrival time as a voxel fast-marching solution with
            speed ∝ h²/η(T). Local wall thickness comes from the 3D distance transform; viscosity
            is Arrhenius, coupled to a preliminary temperature estimate (two-pass).
          </p>
          <p className="text-[10px] text-gray-500 mt-2 italic">Runs in ~2s on upload. Already computed and on screen.</p>
        </div>
      )}

      {mode === "auto" && (
        <div>
          {recLoading && (
            <div className="flex items-center gap-2 p-3 rounded bg-gray-50 border border-gray-200">
              <div className="animate-spin h-4 w-4 border-2 border-brand-600 border-t-transparent rounded-full"/>
              <span className="text-xs text-gray-600">Analysing geometry…</span>
            </div>
          )}
          {recErr && (
            <div className="p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
              Selector failed: {recErr}
            </div>
          )}
          {rec && !recLoading && (
            <>
              <div className="p-3 rounded border bg-gradient-to-br from-brand-50 to-white border-brand-300 mb-3">
                <div className="flex items-start justify-between mb-1">
                  <div>
                    <div className="text-[9px] font-bold uppercase tracking-wider text-brand-600">Recommended</div>
                    <div className="text-sm font-semibold text-gray-900 mt-0.5">{rec.name}</div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-block text-[9px] px-1.5 py-0.5 rounded ${rec.confidence === "high" ? "bg-green-100 text-green-700" : rec.confidence === "high_accuracy" ? "bg-purple-100 text-purple-700" : "bg-amber-100 text-amber-700"}`}>
                      {rec.confidence}
                    </div>
                    <div className="text-[10px] text-gray-500 mt-0.5">~{rec.runtime_estimate}</div>
                  </div>
                </div>
                <ul className="text-[11px] space-y-1 mt-2 text-gray-700">
                  {rec.reasoning.map((r, i) => <li key={i} className="flex gap-1"><span className="text-brand-500">•</span><span>{r}</span></li>)}
                </ul>
                <button
                  onClick={() => setMode(recToUiMode(rec.recommended))}
                  disabled={!rec.available}
                  className={`mt-3 w-full px-2 py-1.5 rounded text-xs font-medium transition ${rec.available ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-gray-200 text-gray-400 cursor-not-allowed"}`}
                >
                  {rec.available ? `Use ${rec.name}` : "Not yet implemented"}
                </button>
              </div>

              <div className="border-b border-gray-100 pb-3 mb-3">
                <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">Geometry</h4>
                <dl className="text-[11px] space-y-0.5">
                  <div className="flex justify-between"><dt className="text-gray-500">median h</dt><dd className="font-mono">{rec.derived.median_thickness_mm.toFixed(2)} mm</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">range h</dt><dd className="font-mono">{rec.derived.thickness_range_mm[0].toFixed(1)}–{rec.derived.thickness_range_mm[1].toFixed(1)} mm</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">flow length L</dt><dd className="font-mono">{rec.derived.flow_length_mm.toFixed(0)} mm</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">aspect h/L</dt><dd className="font-mono font-semibold text-brand-700">{rec.derived.aspect_ratio_h_over_L.toFixed(3)}</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">undercuts</dt><dd className="font-mono">{rec.derived.undercut_count}</dd></div>
                </dl>
              </div>

              <div className="border-b border-gray-100 pb-3 mb-3">
                <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">Flow regime</h4>
                <dl className="text-[11px] space-y-0.5">
                  <div className="flex justify-between"><dt className="text-gray-500">Re</dt><dd className="font-mono">{rec.derived.reynolds_number.toExponential(1)}</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">Stokes</dt><dd className="font-mono">{rec.derived.stokes_regime ? "yes (Re≪1)" : "no"}</dd></div>
                  <div className="flex justify-between"><dt className="text-gray-500">h uniformity</dt><dd className="font-mono">{(rec.derived.thickness_uniformity * 100).toFixed(0)}%</dd></div>
                </dl>
                <p className="text-[9px] text-gray-400 mt-1 italic">Polymer reference: ρ≈1000 kg/m³, v≈0.1 m/s, η≈1000 Pa·s</p>
              </div>

              <div className="border-b border-gray-100 pb-3 mb-3">
                <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">What this ignores</h4>
                <ul className="text-[10px] text-gray-600 space-y-0.5">
                  {rec.ignores.map((s, i) => <li key={i}>• {s}</li>)}
                </ul>
              </div>

              <div>
                <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">Override</h4>
                <div className="space-y-1.5">
                  {rec.alternatives.map(alt => (
                    <div key={alt.solver} className="p-2 rounded bg-gray-50 border border-gray-200">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[11px] font-medium text-gray-900 truncate">{alt.name}</span>
                            <span className={`text-[8px] px-1 rounded ${alt.available ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-500"}`}>
                              {alt.available ? "available" : "not wired"}
                            </span>
                          </div>
                          <p className="text-[10px] text-gray-500 mt-0.5 leading-tight">{alt.tradeoff} · ~{alt.runtime_estimate}</p>
                        </div>
                        <button
                          disabled={!alt.available}
                          onClick={() => {
                            if (alt.solver === "hele_shaw_2d" || alt.solver === "fmm_3d") setMode("simple");
                            else setMode("openfoam");
                          }}
                          className={`ml-2 text-[10px] px-2 py-0.5 rounded ${alt.available ? "bg-white hover:bg-gray-100 border border-gray-300 text-gray-700" : "bg-gray-100 text-gray-400 cursor-not-allowed"}`}
                        >Use</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {mode === "openfoam" && (
        <div>
          <div className={`p-3 rounded border mb-3 ${ofStatus?.available ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-bold uppercase tracking-wider ${ofStatus?.available ? "text-green-700" : "text-amber-700"}`}>
                {ofStatus?.available ? "Ready" : "Not configured"}
              </span>
              {ofStatus && <span className="text-[9px] text-gray-500">({ofStatus.reason})</span>}
            </div>
            <p className="text-[11px] text-gray-700">{ofStatus?.message || "Checking OpenFOAM availability…"}</p>
            {!ofStatus?.available && ofStatus?.next_steps && (
              <details className="mt-2">
                <summary className="text-[10px] text-gray-600 cursor-pointer hover:text-gray-900">How to enable</summary>
                <ol className="list-decimal list-inside mt-1 space-y-0.5 text-[10px] font-mono bg-white/70 rounded p-2 text-gray-700 whitespace-pre-wrap">
                  {ofStatus.next_steps.map((s, i) => <li key={i}>{s}</li>)}
                </ol>
              </details>
            )}
          </div>

          <div className="border-b border-gray-100 pb-3 mb-3">
            <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">Physics</h4>
            <ul className="text-[11px] space-y-0.5 text-gray-700">
              <li>• 3D incompressible Navier-Stokes</li>
              <li>• VOF free-surface (α polymer/air)</li>
              <li>• Cross-WLF viscosity (shear + T)</li>
              <li>• Energy equation with mold cooling</li>
              <li>• No-slip walls, inlet at gate</li>
            </ul>
          </div>

          <div className="border-b border-gray-100 pb-3 mb-3">
            <h4 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1.5">Pipeline</h4>
            <ol className="text-[11px] space-y-0.5 text-gray-700 list-decimal list-inside">
              <li>STEP → STL (pythonocc)</li>
              <li>STL → polyMesh (snappyHexMesh)</li>
              <li>Case setup (0/, constant/, system/)</li>
              <li>interFoam solve (4 cores, 20–60 min)</li>
              <li>VTK → per-vertex fill time</li>
            </ol>
          </div>

          <div className="p-2.5 rounded bg-blue-50 border border-blue-200">
            <h4 className="text-[9px] font-bold uppercase tracking-wider text-blue-700 mb-1">Meanwhile</h4>
            <p className="text-[11px] text-blue-900 leading-relaxed">
              The 3D viewer already shows the <strong>Simple Model</strong> (voxel FMM + h²/η(T)).
              For gate placement / cold-spot mapping, it agrees qualitatively with VOF at 600× the speed.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
