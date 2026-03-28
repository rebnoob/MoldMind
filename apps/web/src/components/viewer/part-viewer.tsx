"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Environment } from "@react-three/drei";
import * as THREE from "three";

interface PartViewerProps {
  meshUrl: string | null;
  highlightedFaces: number[];
  pullDirection: number[];
}

function PullDirectionArrow({ direction }: { direction: number[] }) {
  const length = 30;
  const [x, y, z] = direction;

  return (
    <group>
      <arrowHelper
        args={[
          new THREE.Vector3(x, y, z).normalize(),
          new THREE.Vector3(0, 0, 0),
          length,
          0x3b82f6,
          length * 0.15,
          length * 0.08,
        ]}
      />
    </group>
  );
}

function PlaceholderMesh({ highlightedFaces }: { highlightedFaces: number[] }) {
  /**
   * Placeholder geometry for development.
   * In production, this loads the GLB mesh from the API and applies
   * per-face coloring based on DFM issues.
   */
  const meshRef = useRef<THREE.Mesh>(null);

  // Simple box as placeholder
  const geometry = useMemo(() => {
    const geo = new THREE.BoxGeometry(40, 25, 15, 4, 4, 4);
    // Add some face colors to simulate DFM highlighting
    const colors = new Float32Array(geo.attributes.position.count * 3);
    for (let i = 0; i < colors.length; i += 3) {
      colors[i] = 0.85;     // R
      colors[i + 1] = 0.87; // G
      colors[i + 2] = 0.9;  // B
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geo;
  }, []);

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        vertexColors
        roughness={0.4}
        metalness={0.1}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export function PartViewer({ meshUrl, highlightedFaces, pullDirection }: PartViewerProps) {
  return (
    <div className="w-full h-full viewer-container">
      <Canvas
        camera={{ position: [60, 40, 60], fov: 45, near: 0.1, far: 1000 }}
        gl={{ antialias: true }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[50, 50, 50]} intensity={0.8} />
        <directionalLight position={[-30, -20, 40]} intensity={0.3} />

        <PlaceholderMesh highlightedFaces={highlightedFaces} />
        <PullDirectionArrow direction={pullDirection} />

        <Grid
          args={[200, 200]}
          cellSize={5}
          cellThickness={0.5}
          cellColor="#e5e7eb"
          sectionSize={25}
          sectionThickness={1}
          sectionColor="#d1d5db"
          fadeDistance={150}
          fadeStrength={1}
          position={[0, -15, 0]}
        />

        <OrbitControls
          enableDamping
          dampingFactor={0.1}
          minDistance={20}
          maxDistance={200}
        />
      </Canvas>

      {!meshUrl && (
        <div className="absolute bottom-4 left-4 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
          Showing placeholder geometry. Upload a STEP file for real analysis.
        </div>
      )}
    </div>
  );
}
