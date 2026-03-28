"use client";

import { Suspense, useRef, useEffect, useState, useMemo, useCallback } from "react";
import { Canvas, useThree, useLoader, useFrame, ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

// --- Types ---

interface FaceMapEntry {
  face_index: number;
  vert_start: number;
  vert_end: number;
  centroid: [number, number, number];
  normal: [number, number, number];
}

interface TopologyEdge {
  id: number;
  curve_type: string;
  polyline: number[][];
  face_ids: number[];
  vertex_ids: number[];
  length_mm: number;
  convexity: string;
  curve_params?: any;
}

interface TopologyFace {
  id: number;
  surface_type: string;
  area_mm2: number;
  feature_type?: string;
  mold_side?: string;
  edge_ids?: number[];
  adjacent_face_ids?: number[];
}

interface TopologyVertex {
  id: number;
  point: number[];
  edge_ids: number[];
}

interface TopologyData {
  faces: TopologyFace[];
  edges: TopologyEdge[];
  vertices: TopologyVertex[];
}

interface SelectedEntity {
  type: "face" | "edge" | "vertex";
  id: number;
}

interface PartViewerProps {
  meshUrl: string | null;
  facemapUrl: string | null;
  topologyUrl: string | null;
}

// --- Colors ---

const DEFAULT_COLOR = new THREE.Color(0.78, 0.80, 0.83);
const HOVER_FACE_COLOR = 0x3399ff;
const SELECT_FACE_COLOR = 0x00cc66;
const HOVER_EDGE_COLOR = 0x3399ff;
const SELECT_EDGE_COLOR = 0x00cc66;
const SELECT_VERTEX_COLOR = 0x00cc66;
const HOVER_VERTEX_COLOR = 0x3399ff;
const DEFAULT_EDGE_COLOR = 0x555555;

// --- Helpers ---

function findFaceByVertex(vertIdx: number, faceMap: FaceMapEntry[]): number {
  for (const fm of faceMap) {
    if (vertIdx >= fm.vert_start && vertIdx < fm.vert_end) return fm.face_index;
  }
  return -1;
}

function buildFaceOverlay(
  srcGeo: THREE.BufferGeometry,
  faceMap: FaceMapEntry[],
  faceIds: number[],
  color: number,
  opacity: number,
): THREE.Mesh | null {
  const posAttr = srcGeo.getAttribute("position");
  const normAttr = srcGeo.getAttribute("normal");
  const idxAttr = srcGeo.getIndex();
  if (!posAttr || !idxAttr) return null;

  const faceSet = new Set(faceIds);
  const faceRanges = faceMap.filter(fm => faceSet.has(fm.face_index));
  if (faceRanges.length === 0) return null;

  const isInRange = (v: number) => {
    for (const fm of faceRanges) {
      if (v >= fm.vert_start && v < fm.vert_end) return true;
    }
    return false;
  };

  const indices: number[] = [];
  const triCount = idxAttr.count / 3;
  for (let t = 0; t < triCount; t++) {
    const a = idxAttr.getX(t * 3);
    if (isInRange(a)) {
      indices.push(a, idxAttr.getX(t * 3 + 1), idxAttr.getX(t * 3 + 2));
    }
  }
  if (indices.length === 0) return null;

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", posAttr);
  if (normAttr) geo.setAttribute("normal", normAttr);
  geo.setIndex(indices);

  return new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
    color, transparent: true, opacity,
    side: THREE.DoubleSide, depthTest: true,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
  }));
}

function buildEntityInfo(entity: SelectedEntity, topology: TopologyData): string {
  if (entity.type === "face") {
    const f = topology.faces.find(f => f.id === entity.id);
    if (!f) return `Face ${entity.id}`;
    const ft = f.feature_type || f.surface_type;
    const ms = f.mold_side ? ` (${f.mold_side})` : "";
    const edges = f.edge_ids?.length || 0;
    const adj = f.adjacent_face_ids?.length || 0;
    return `Face ${entity.id} — ${ft}${ms} — ${f.area_mm2.toFixed(1)} mm² — ${edges} edges, ${adj} adjacent`;
  }
  if (entity.type === "edge") {
    const e = topology.edges.find(e => e.id === entity.id);
    if (!e) return `Edge ${entity.id}`;
    const r = e.curve_params?.radius ? ` r=${e.curve_params.radius} mm` : "";
    const faces = e.face_ids.map(id => `Face ${id}`).join(", ");
    return `Edge ${entity.id} — ${e.curve_type}${r} — ${e.length_mm.toFixed(1)} mm — ${e.convexity} — ${faces}`;
  }
  if (entity.type === "vertex") {
    const v = topology.vertices.find(v => v.id === entity.id);
    if (!v) return `Vertex ${entity.id}`;
    const pt = v.point.map(c => c.toFixed(2)).join(", ");
    return `Vertex ${entity.id} — (${pt}) — ${v.edge_ids.length} edges`;
  }
  return "";
}

// --- Interactive Model ---

function InteractiveModel({
  url, faceMap, topology, onHoverInfo,
}: {
  url: string;
  faceMap: FaceMapEntry[];
  topology: TopologyData | null;
  onHoverInfo: (info: string | null) => void;
}) {
  const gltf = useLoader(GLTFLoader, url);
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const edgesGroupRef = useRef<THREE.Group>(new THREE.Group());
  const verticesGroupRef = useRef<THREE.Group>(new THREE.Group());
  const overlayRef = useRef<THREE.Mesh | null>(null);
  const { camera, raycaster, pointer } = useThree();
  const [fitted, setFitted] = useState(false);
  const [hoveredEntity, setHoveredEntity] = useState<SelectedEntity | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity | null>(null);
  const pointerDownPos = useRef<{ x: number; y: number } | null>(null);

  // --- Setup mesh ---
  useEffect(() => {
    if (!groupRef.current) return;
    const scene = gltf.scene.clone(true);
    scene.traverse((child) => {
      if (child instanceof THREE.Mesh && !meshRef.current) {
        meshRef.current = child;
        child.material = new THREE.MeshStandardMaterial({
          color: DEFAULT_COLOR, roughness: 0.4, metalness: 0.08, side: THREE.DoubleSide,
        });
      }
    });

    while (groupRef.current.children.length > 0)
      groupRef.current.remove(groupRef.current.children[0]);
    groupRef.current.add(scene);
    groupRef.current.add(edgesGroupRef.current);
    groupRef.current.add(verticesGroupRef.current);

    if (!fitted) {
      const box = new THREE.Box3().setFromObject(groupRef.current);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      groupRef.current.position.sub(center);
      const maxDim = Math.max(size.x, size.y, size.z);
      if (camera instanceof THREE.PerspectiveCamera) {
        camera.position.set(maxDim * 1.75, maxDim * 1.25, maxDim * 1.75);
        camera.lookAt(0, 0, 0);
        camera.updateProjectionMatrix();
      }
      setFitted(true);
    }
  }, [gltf, camera, fitted]);

  // --- Build edge lines ---
  useEffect(() => {
    const eg = edgesGroupRef.current;
    while (eg.children.length > 0) eg.remove(eg.children[0]);
    if (!topology?.edges || !fitted) return;
    for (const edge of topology.edges) {
      if (!edge.polyline || edge.polyline.length < 2) continue;
      const pts = edge.polyline.map(p => new THREE.Vector3(p[0], p[1], p[2]));
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color: DEFAULT_EDGE_COLOR, transparent: true, opacity: 0.5,
      });
      const line = new THREE.Line(geo, mat);
      (line as any).userData = { type: "edge", edgeId: edge.id, edgeData: edge };
      eg.add(line);
    }
  }, [topology, fitted]);

  // --- Build vertex spheres ---
  useEffect(() => {
    const vg = verticesGroupRef.current;
    while (vg.children.length > 0) vg.remove(vg.children[0]);
    if (!topology?.vertices || !fitted) return;
    const sphereGeo = new THREE.SphereGeometry(0.6, 8, 8);
    for (const vert of topology.vertices) {
      const mat = new THREE.MeshBasicMaterial({
        color: DEFAULT_EDGE_COLOR, transparent: true, opacity: 0,
      });
      const sphere = new THREE.Mesh(sphereGeo, mat);
      sphere.position.set(vert.point[0], vert.point[1], vert.point[2]);
      (sphere as any).userData = { type: "vertex", vertexId: vert.id };
      vg.add(sphere);
    }
  }, [topology, fitted]);

  // --- Face overlay (hover / selected) ---
  useEffect(() => {
    if (overlayRef.current) {
      overlayRef.current.geometry.dispose();
      overlayRef.current.removeFromParent();
      overlayRef.current = null;
    }
    if (!meshRef.current || faceMap.length === 0) return;

    let overlay: THREE.Mesh | null = null;
    if (selectedEntity?.type === "face") {
      overlay = buildFaceOverlay(meshRef.current.geometry, faceMap, [selectedEntity.id], SELECT_FACE_COLOR, 0.55);
    } else if (hoveredEntity?.type === "face") {
      overlay = buildFaceOverlay(meshRef.current.geometry, faceMap, [hoveredEntity.id], HOVER_FACE_COLOR, 0.4);
    }

    if (overlay && meshRef.current.parent) {
      meshRef.current.parent.add(overlay);
      overlayRef.current = overlay;
    }
    return () => {
      if (overlayRef.current) {
        overlayRef.current.geometry.dispose();
        overlayRef.current.removeFromParent();
        overlayRef.current = null;
      }
    };
  }, [selectedEntity, hoveredEntity, faceMap]);

  // --- Edge + vertex styling ---
  useEffect(() => {
    if (!topology) return;

    // Collect active edges
    let activeEdgeIds = new Set<number>();
    let edgeColor = DEFAULT_EDGE_COLOR;

    const activeEntity = selectedEntity || hoveredEntity;
    if (activeEntity?.type === "face") {
      edgeColor = selectedEntity ? SELECT_EDGE_COLOR : HOVER_EDGE_COLOR;
      const f = topology.faces.find(f => f.id === activeEntity.id);
      if (f?.edge_ids) f.edge_ids.forEach(eid => activeEdgeIds.add(eid));
    } else if (activeEntity?.type === "edge") {
      edgeColor = selectedEntity ? SELECT_EDGE_COLOR : HOVER_EDGE_COLOR;
      activeEdgeIds.add(activeEntity.id);
    }

    for (const child of edgesGroupRef.current.children) {
      if (child instanceof THREE.Line) {
        const mat = child.material as THREE.LineBasicMaterial;
        const eid = (child as any).userData?.edgeId;
        if (activeEdgeIds.has(eid)) {
          mat.color.set(edgeColor);
          mat.opacity = 1.0;
        } else {
          mat.color.set(DEFAULT_EDGE_COLOR);
          mat.opacity = 0.5;
        }
      }
    }

    // Collect active vertices
    const activeVertIds = new Set<number>();
    if (activeEntity?.type === "vertex") activeVertIds.add(activeEntity.id);
    if (activeEntity?.type === "face") {
      const f = topology.faces.find(f => f.id === activeEntity.id);
      if (f?.edge_ids) {
        for (const eid of f.edge_ids) {
          const e = topology.edges.find(e => e.id === eid);
          if (e) e.vertex_ids.forEach(vid => activeVertIds.add(vid));
        }
      }
    }
    if (activeEntity?.type === "edge") {
      const e = topology.edges.find(e => e.id === activeEntity.id);
      if (e) e.vertex_ids.forEach(vid => activeVertIds.add(vid));
    }

    const vertColor = selectedEntity ? SELECT_VERTEX_COLOR : HOVER_VERTEX_COLOR;
    for (const child of verticesGroupRef.current.children) {
      if (child instanceof THREE.Mesh) {
        const mat = child.material as THREE.MeshBasicMaterial;
        const vid = (child as any).userData?.vertexId;
        if (activeVertIds.has(vid)) {
          mat.color.set(
            selectedEntity?.type === "vertex" && selectedEntity.id === vid
              ? SELECT_VERTEX_COLOR : vertColor
          );
          mat.opacity = 1.0;
        } else {
          mat.opacity = 0;
        }
      }
    }
  }, [selectedEntity, hoveredEntity, topology]);

  // --- Click detection ---
  const handlePointerDown = useCallback((e: ThreeEvent<PointerEvent>) => {
    pointerDownPos.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handlePointerUp = useCallback((e: ThreeEvent<PointerEvent>) => {
    if (!pointerDownPos.current) return;
    const dx = e.clientX - pointerDownPos.current.x;
    const dy = e.clientY - pointerDownPos.current.y;
    pointerDownPos.current = null;
    if (Math.sqrt(dx * dx + dy * dy) > 4) return; // orbit drag

    raycaster.setFromCamera(pointer, camera);

    // Face
    if (meshRef.current) {
      const hits = raycaster.intersectObject(meshRef.current, false);
      if (hits.length > 0) {
        const idx = meshRef.current.geometry.getIndex();
        if (idx && hits[0].faceIndex !== undefined) {
          const vertIdx = idx.getX(hits[0].faceIndex * 3);
          const faceId = findFaceByVertex(vertIdx, faceMap);
          if (faceId >= 0) {
            if (selectedEntity?.type === "face" && selectedEntity.id === faceId) {
              setSelectedEntity(null); onHoverInfo(null);
            } else {
              setSelectedEntity({ type: "face", id: faceId });
              if (topology) onHoverInfo(buildEntityInfo({ type: "face", id: faceId }, topology));
            }
            return;
          }
        }
      }
    }

    // Edge
    const edgeHits = raycaster.intersectObjects(edgesGroupRef.current.children, false);
    if (edgeHits.length > 0) {
      const ed = (edgeHits[0].object as any).userData?.edgeData as TopologyEdge;
      if (ed) {
        if (selectedEntity?.type === "edge" && selectedEntity.id === ed.id) {
          setSelectedEntity(null); onHoverInfo(null);
        } else {
          setSelectedEntity({ type: "edge", id: ed.id });
          if (topology) onHoverInfo(buildEntityInfo({ type: "edge", id: ed.id }, topology));
        }
        return;
      }
    }

    // Vertex
    const vertHits = raycaster.intersectObjects(verticesGroupRef.current.children, false);
    if (vertHits.length > 0) {
      const vid = (vertHits[0].object as any).userData?.vertexId;
      if (vid !== undefined) {
        if (selectedEntity?.type === "vertex" && selectedEntity.id === vid) {
          setSelectedEntity(null); onHoverInfo(null);
        } else {
          setSelectedEntity({ type: "vertex", id: vid });
          if (topology) onHoverInfo(buildEntityInfo({ type: "vertex", id: vid }, topology));
        }
        return;
      }
    }

    // Empty
    setSelectedEntity(null);
    onHoverInfo(null);
  }, [faceMap, topology, selectedEntity, camera, pointer, raycaster, onHoverInfo]);

  // --- Hover ---
  useFrame(() => {
    if (!meshRef.current || faceMap.length === 0) return;
    if (selectedEntity) return; // Don't hover when something is selected

    raycaster.setFromCamera(pointer, camera);

    // Face
    const hits = raycaster.intersectObject(meshRef.current, false);
    if (hits.length > 0) {
      const idx = meshRef.current.geometry.getIndex();
      if (idx && hits[0].faceIndex !== undefined) {
        const vertIdx = idx.getX(hits[0].faceIndex * 3);
        const faceId = findFaceByVertex(vertIdx, faceMap);
        if (faceId >= 0) {
          if (!hoveredEntity || hoveredEntity.type !== "face" || hoveredEntity.id !== faceId) {
            setHoveredEntity({ type: "face", id: faceId });
            if (topology) onHoverInfo(buildEntityInfo({ type: "face", id: faceId }, topology));
          }
          return;
        }
      }
    }

    // Edge fallback
    const edgeHits = raycaster.intersectObjects(edgesGroupRef.current.children, false);
    if (edgeHits.length > 0) {
      const ed = (edgeHits[0].object as any).userData?.edgeData as TopologyEdge;
      if (ed) {
        if (!hoveredEntity || hoveredEntity.type !== "edge" || hoveredEntity.id !== ed.id) {
          setHoveredEntity({ type: "edge", id: ed.id });
          if (topology) onHoverInfo(buildEntityInfo({ type: "edge", id: ed.id }, topology));
        }
        return;
      }
    }

    if (hoveredEntity) {
      setHoveredEntity(null);
      onHoverInfo(null);
    }
  });

  return (
    <group ref={groupRef} onPointerDown={handlePointerDown} onPointerUp={handlePointerUp} />
  );
}

function PlaceholderModel() {
  return (
    <mesh>
      <boxGeometry args={[20, 15, 8]} />
      <meshStandardMaterial color="#d1d5db" roughness={0.6} transparent opacity={0.3} wireframe />
    </mesh>
  );
}

// --- Main Viewer ---

export function PartViewer({ meshUrl, facemapUrl, topologyUrl }: PartViewerProps) {
  const [faceMap, setFaceMap] = useState<FaceMapEntry[]>([]);
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [hoverInfo, setHoverInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!facemapUrl) return;
    fetch(facemapUrl).then(r => r.json()).then(setFaceMap).catch(() => {});
  }, [facemapUrl]);

  useEffect(() => {
    if (!topologyUrl) return;
    fetch(topologyUrl).then(r => r.json()).then(setTopology).catch(() => {});
  }, [topologyUrl]);

  return (
    <div className="w-full h-full viewer-container relative">
      <Canvas
        camera={{ position: [60, 40, 60], fov: 45, near: 0.01, far: 2000 }}
        gl={{ antialias: true, alpha: false }}
        onCreated={({ gl }) => gl.setClearColor("#f8f9fa")}
        raycaster={{ params: { Line: { threshold: 1.5 } } }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[50, 50, 50]} intensity={0.7} />
        <directionalLight position={[-30, -20, 40]} intensity={0.3} />
        <directionalLight position={[20, -40, -20]} intensity={0.15} />

        {meshUrl ? (
          <Suspense fallback={<PlaceholderModel />}>
            <InteractiveModel
              url={meshUrl}
              faceMap={faceMap}
              topology={topology}
              onHoverInfo={setHoverInfo}
            />
          </Suspense>
        ) : (
          <PlaceholderModel />
        )}

        <Grid
          args={[200, 200]}
          cellSize={5}
          cellThickness={0.5}
          cellColor="#e5e7eb"
          sectionSize={25}
          sectionThickness={1}
          sectionColor="#d1d5db"
          fadeDistance={120}
          fadeStrength={1}
          position={[0, -30, 0]}
        />
        <OrbitControls enableDamping dampingFactor={0.1} minDistance={5} maxDistance={500} makeDefault />
      </Canvas>

      {!meshUrl && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <div className="animate-spin h-8 w-8 border-2 border-brand-600 border-t-transparent rounded-full mx-auto mb-3" />
            <p className="text-sm text-gray-500">Processing geometry...</p>
          </div>
        </div>
      )}

      {hoverInfo && (
        <div className="absolute bottom-4 left-4 px-3 py-1.5 bg-black/80 text-white text-xs rounded shadow pointer-events-none font-mono">
          {hoverInfo}
        </div>
      )}
    </div>
  );
}
