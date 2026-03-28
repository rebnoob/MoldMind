"use client";

import { useMemo } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/**
 * Procedurally generated sample parts that look like real injection molded components.
 * These replace the boring box placeholder.
 */

/** Enclosure/housing shell — like a phone case or electronics enclosure */
export function EnclosureShell({ highlightFaces }: { highlightFaces: number[] }) {
  const geometry = useMemo(() => {
    const shape = new THREE.Shape();

    // Rounded rectangle profile
    const w = 40, h = 25, r = 4;
    shape.moveTo(-w / 2 + r, -h / 2);
    shape.lineTo(w / 2 - r, -h / 2);
    shape.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    shape.lineTo(w / 2, h / 2 - r);
    shape.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
    shape.lineTo(-w / 2 + r, h / 2);
    shape.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    shape.lineTo(-w / 2, -h / 2 + r);
    shape.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);

    // Hollow out the interior
    const hole = new THREE.Path();
    const wall = 1.8;
    const wi = w - wall * 2, hi = h - wall * 2, ri = r - wall * 0.5;
    hole.moveTo(-wi / 2 + ri, -hi / 2);
    hole.lineTo(wi / 2 - ri, -hi / 2);
    hole.quadraticCurveTo(wi / 2, -hi / 2, wi / 2, -hi / 2 + ri);
    hole.lineTo(wi / 2, hi / 2 - ri);
    hole.quadraticCurveTo(wi / 2, hi / 2, wi / 2 - ri, hi / 2);
    hole.lineTo(-wi / 2 + ri, hi / 2);
    hole.quadraticCurveTo(-wi / 2, hi / 2, -wi / 2, hi / 2 - ri);
    hole.lineTo(-wi / 2, -hi / 2 + ri);
    hole.quadraticCurveTo(-wi / 2, -hi / 2, -wi / 2 + ri, -hi / 2);
    shape.holes.push(hole);

    const extrudeSettings = { depth: 12, bevelEnabled: true, bevelThickness: 0.5, bevelSize: 0.5, bevelSegments: 3 };
    const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geo.center();
    return geo;
  }, []);

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#c8cdd3" roughness={0.35} metalness={0.05} side={THREE.DoubleSide} />
    </mesh>
  );
}

/** Connector clip — snap-fit feature with living hinge */
export function ConnectorClip() {
  const group = useMemo(() => {
    const parts: THREE.BufferGeometry[] = [];

    // Base plate
    const base = new THREE.BoxGeometry(20, 8, 2);
    base.translate(0, 0, 1);
    parts.push(base);

    // Snap arms (two prongs)
    for (const side of [-1, 1]) {
      const arm = new THREE.BoxGeometry(2, 1.2, 10);
      arm.translate(side * 7, 0, 6);
      parts.push(arm);

      // Hook at end of arm
      const hook = new THREE.BoxGeometry(2, 1.2, 2);
      hook.translate(side * (7 + (side * 1)), 0, 11);
      parts.push(hook);
    }

    // Center post
    const post = new THREE.CylinderGeometry(2, 2.5, 8, 16);
    post.rotateX(Math.PI / 2);
    post.translate(0, 0, 5);
    parts.push(post);

    // Ribs
    for (const x of [-4, 0, 4]) {
      const rib = new THREE.BoxGeometry(0.8, 6, 5);
      rib.translate(x, 0, 3.5);
      parts.push(rib);
    }

    return mergeGeometries(parts);
  }, []);

  return (
    <mesh geometry={group}>
      <meshStandardMaterial color="#d4cfc8" roughness={0.4} metalness={0.05} />
    </mesh>
  );
}

/** Threaded cap — like a bottle cap with internal threads (simplified) */
export function ThreadedCap() {
  const geometry = useMemo(() => {
    const shape = new THREE.Shape();
    // Outer circle
    shape.absarc(0, 0, 12, 0, Math.PI * 2, false);
    // Inner hollow
    const hole = new THREE.Path();
    hole.absarc(0, 0, 10, 0, Math.PI * 2, true);
    shape.holes.push(hole);

    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: 10,
      bevelEnabled: true,
      bevelThickness: 0.3,
      bevelSize: 0.3,
      bevelSegments: 2,
    });

    // Add knurling ridges on outer surface (simplified as a torus ring pattern)
    const knurls: THREE.BufferGeometry[] = [geo];
    for (let i = 0; i < 24; i++) {
      const angle = (i / 24) * Math.PI * 2;
      const ridge = new THREE.BoxGeometry(0.6, 0.6, 9);
      ridge.translate(12.3 * Math.cos(angle), 12.3 * Math.sin(angle), 5);
      ridge.rotateZ(angle);
      knurls.push(ridge);
    }

    // Top disc
    const top = new THREE.CylinderGeometry(12, 12, 1.5, 32);
    top.rotateX(Math.PI / 2);
    top.translate(0, 0, 10.5);
    knurls.push(top);

    return mergeGeometries(knurls);
  }, []);

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#b8c4d0" roughness={0.3} metalness={0.08} />
    </mesh>
  );
}

/** Bracket with bosses — structural bracket with mounting holes and ribs */
export function MountingBracket() {
  const geometry = useMemo(() => {
    const parts: THREE.BufferGeometry[] = [];

    // L-shaped base
    const plate1 = new THREE.BoxGeometry(30, 20, 2.5);
    plate1.translate(0, 0, 1.25);
    parts.push(plate1);

    const plate2 = new THREE.BoxGeometry(2.5, 20, 18);
    plate2.translate(-13.75, 0, 10.25);
    parts.push(plate2);

    // Gusset / triangle rib
    const gussetShape = new THREE.Shape();
    gussetShape.moveTo(0, 0);
    gussetShape.lineTo(12, 0);
    gussetShape.lineTo(0, 15);
    gussetShape.lineTo(0, 0);
    const gusset = new THREE.ExtrudeGeometry(gussetShape, { depth: 1.5, bevelEnabled: false });
    gusset.translate(-12.5, -0.75, 2.5);
    parts.push(gusset);

    // Mounting bosses (cylinders with holes)
    for (const [x, y] of [[8, 6], [8, -6], [-4, 6], [-4, -6]] as [number, number][]) {
      const boss = new THREE.CylinderGeometry(3, 3.5, 6, 16);
      boss.rotateX(Math.PI / 2);
      boss.translate(x, y, 5.5);
      parts.push(boss);

      // Boss hole
      const hole = new THREE.CylinderGeometry(1.5, 1.5, 7, 16);
      hole.rotateX(Math.PI / 2);
      hole.translate(x, y, 5.5);
      // Note: Can't do boolean subtract easily in Three.js, so bosses are solid
    }

    // Stiffening ribs
    for (const y of [-5, 0, 5]) {
      const rib = new THREE.BoxGeometry(25, 1, 3);
      rib.translate(2, y, 4);
      parts.push(rib);
    }

    return mergeGeometries(parts);
  }, []);

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#ccd0d4" roughness={0.45} metalness={0.05} />
    </mesh>
  );
}

/** Map of sample parts by name */
export const SAMPLE_PARTS = {
  enclosure: { name: "Electronics Enclosure", Component: EnclosureShell },
  clip: { name: "Connector Clip", Component: ConnectorClip },
  cap: { name: "Threaded Cap", Component: ThreadedCap },
  bracket: { name: "Mounting Bracket", Component: MountingBracket },
} as const;

export type SamplePartKey = keyof typeof SAMPLE_PARTS;
