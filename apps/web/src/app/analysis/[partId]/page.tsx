"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { PartViewer } from "@/components/viewer/part-viewer";
import { FillTimeViewer, FlowSimControls } from "@/components/viewer/fill-time-viewer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MATERIAL_DB: Record<string, { name: string; family: string; bp: number; visc: number; shrink: number; melt: number; mold: number; density: number }> = {
  ABS: { name: "ABS (Generic)", family: "ABS", bp: 35, visc: 1.0, shrink: 0.5, melt: 230, mold: 60, density: 1.05 },
  PP: { name: "Polypropylene", family: "PP", bp: 25, visc: 0.8, shrink: 1.5, melt: 230, mold: 40, density: 0.91 },
  PA: { name: "Nylon (PA6)", family: "PA", bp: 45, visc: 1.2, shrink: 1.2, melt: 260, mold: 80, density: 1.14 },
  PC: { name: "Polycarbonate", family: "PC", bp: 55, visc: 1.4, shrink: 0.6, melt: 300, mold: 90, density: 1.20 },
  POM: { name: "Acetal (POM)", family: "POM", bp: 35, visc: 0.9, shrink: 2.0, melt: 210, mold: 90, density: 1.41 },
  PS: { name: "Polystyrene", family: "PS", bp: 25, visc: 0.7, shrink: 0.4, melt: 220, mold: 40, density: 1.05 },
  PE: { name: "HDPE", family: "PE", bp: 25, visc: 0.7, shrink: 2.5, melt: 230, mold: 40, density: 0.95 },
  PBT: { name: "PBT", family: "PBT", bp: 40, visc: 1.1, shrink: 1.5, melt: 260, mold: 70, density: 1.31 },
  "ABS/PC": { name: "ABS/PC Blend", family: "ABS/PC", bp: 40, visc: 1.1, shrink: 0.5, melt: 260, mold: 80, density: 1.10 },
};

function calcP(pa: number, fl: number, w: number, vol: number, fam: string) {
  const m = MATERIAL_DB[fam] || MATERIAL_DB.ABS;
  const fr = w > 0 ? fl / w : 100;
  const cp = (m.bp + Math.max(0, (fr - 100) / 10)) * m.visc;
  const ip = cp * 2;
  const cf = (pa / 100) * cp / 10 * 1.1;
  const volCm3 = vol / 1000;
  const swPart = volCm3 * m.density;
  const swTotal = swPart * 1.15; // 15% runner overhead
  const fillRate = w < 1.5 ? 150 : w < 3 ? 100 : 60;
  const fillTime = Math.max(0.3, volCm3 / fillRate);
  const packTime = w * 1.5;
  const coolTime = w * w * 1.2;
  const cycleTime = fillTime + packTime + coolTime + 3;
  const mc = cf > 500 ? "500+ ton" : cf > 200 ? "250-500 ton" : cf > 80 ? "100-250 ton" : cf > 30 ? "50-100 ton" : "25-50 ton";
  return { cp, ip, cf, swPart, swTotal, mc, fr, packP: ip * 0.6, fillTime, packTime, coolTime, cycleTime, density: m.density };
}

interface PartInfo {
  id: string; name: string; filename: string; status: string;
  file_size_bytes: number | null; error_message: string | null;
  mesh_url: string | null; facemap_url: string | null;
  topology_url: string | null; molding_plan_url: string | null;
  ceramic_feasibility_url: string | null;
  fill_time_url: string | null; fill_time_meta_url: string | null;
}

// --- Shared UI ---
function B({ t, c }: { t: string; c: string }) {
  const s: Record<string,string> = { green:"bg-green-100 text-green-800 border-green-200", amber:"bg-amber-100 text-amber-800 border-amber-200", red:"bg-red-100 text-red-800 border-red-200", blue:"bg-blue-100 text-blue-800 border-blue-200", purple:"bg-purple-100 text-purple-800 border-purple-200", gray:"bg-gray-100 text-gray-700 border-gray-200" };
  return <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${s[c]||s.gray}`}>{t}</span>;
}
function CB({ l }: { l: string }) { return <B t={l} c={l==="high"?"green":l==="medium"?"amber":"red"} />; }
function Sec({ title, badge, children }: { title: string; badge?: React.ReactNode; children: React.ReactNode }) {
  return (<div className="border-b border-gray-100 pb-4 mb-4"><div className="flex items-center justify-between mb-2"><h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wide">{title}</h3>{badge}</div>{children}</div>);
}
function R({ l, v, u, b }: { l: string; v: string|number; u?: string; b?: boolean }) {
  return (<div className="flex justify-between items-baseline py-0.5"><span className="text-xs text-gray-500">{l}</span><span className={`text-xs font-mono ${b?"font-bold text-gray-900":"font-medium text-gray-800"}`}>{v}{u?` ${u}`:""}</span></div>);
}

// --- Molding Plan Panel ---
function MoldingPanel({ plan, mat, onMat }: { plan: any; mat: string; onMat: (m:string)=>void }) {
  const t = plan.tooling, m = plan.material, p = plan.pressure, mc = t.mold_components||{};
  const mi = MATERIAL_DB[mat]||MATERIAL_DB.ABS;
  const pr = useMemo(() => calcP(p.projected_area_mm2, p.flow_length_mm, p.nominal_wall_mm, t.part_volume_mm3, mat), [mat, p, t]);
  return (
    <div className="p-4">
      <div className="mb-4 p-3 bg-gray-50 rounded-lg border"><div className="flex items-center justify-between mb-1.5"><span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Molding Plan</span><CB l={plan.overall_confidence} /></div><p className="text-xs text-gray-600 leading-relaxed">{plan.summary}</p></div>
      <Sec title="Tooling" badge={<CB l={t.confidence} />}>
        <R l="Mold type" v={t.mold_type} b /><R l="Complexity" v={t.complexity_level} /><R l="Side actions" v={t.side_actions_needed} />
        <R l="Parting" v={t.parting_feasibility} /><R l="Moldable area" v={`${(t.parting_ratio*100).toFixed(0)}%`} />
        <R l="Undercuts" v={t.undercut_count} /><R l="Envelope" v={`${t.part_envelope_mm.x.toFixed(0)}×${t.part_envelope_mm.y.toFixed(0)}×${t.part_envelope_mm.z.toFixed(0)}`} u="mm" />
        <R l="Volume" v={t.part_volume_mm3.toFixed(0)} u="mm³" />
        <div className="mt-2 p-2 bg-blue-50 rounded border border-blue-100"><p className="text-[11px] font-semibold text-blue-900">Cavity: {t.cavity_recommendation.primary}{t.cavity_recommendation.multi_cavity_max>t.cavity_recommendation.primary?` (up to ${t.cavity_recommendation.multi_cavity_max})`:""}</p><p className="text-[10px] text-blue-700 mt-0.5">{t.cavity_recommendation.notes}</p></div>
      </Sec>
      <Sec title="Mold Parts" badge={<B t={`${t.total_mold_parts||"?"} parts`} c="purple" />}>
        {mc.cavity_plate!=null?(<><R l="Cavity plate" v={mc.cavity_plate}/><R l="Core plate" v={mc.core_plate}/><R l="Sliders" v={mc.sliders}/><R l="Core pins" v={mc.core_pins}/><R l="Ejector pins" v={mc.ejector_pins}/><R l="Sprue bushing" v={mc.sprue_bushing}/><R l="Runner system" v={mc.runner_system}/><R l="Cooling" v={mc.cooling_channels}/><R l="Guide pins" v={mc.guide_pins}/><R l="Return pins" v={mc.return_pins}/><R l="Mold base" v={mc.mold_base}/><div className="h-px bg-gray-200 my-1"/><R l="Total" v={t.total_mold_parts} b/></>):<p className="text-xs text-gray-400">N/A</p>}
      </Sec>
      <Sec title="Material" badge={<CB l={m.confidence} />}>
        <select value={mat} onChange={e=>onMat(e.target.value)} className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 mb-2 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500">{Object.entries(MATERIAL_DB).map(([k,v])=><option key={k} value={k}>{v.name}</option>)}</select>
        <div className="p-2 bg-green-50 rounded border border-green-100 mb-2"><p className="text-[11px] font-semibold text-green-900">{mi.name}</p><div className="grid grid-cols-3 gap-1 mt-1 text-[10px] text-green-700"><span>Shrinkage: {mi.shrink}%</span><span>Melt: {mi.melt}°C</span><span>Mold: {mi.mold}°C</span></div></div>
        <R l="Nominal wall" v={m.selection_criteria.nominal_wall_mm.toFixed(1)} u="mm"/><R l="Wall range" v={`${m.selection_criteria.min_wall_mm.toFixed(1)}–${m.selection_criteria.max_wall_mm.toFixed(1)}`} u="mm"/>
      </Sec>
      <Sec title="Pressure & Force" badge={<B t={mat} c="blue" />}>
        <R l="Projected area (X×Y)" v={p.projected_area_mm2.toFixed(0)} u="mm²" b/>
        {p.projected_area_method && <p className="text-[10px] text-gray-400 mb-1">{p.projected_area_method}</p>}
        <R l="Flow length" v={p.flow_length_mm.toFixed(0)} u="mm"/><R l="Flow ratio" v={pr.fr.toFixed(1)}/>
        <div className="h-px bg-gray-100 my-1"/>
        <R l="Cavity pressure" v={pr.cp.toFixed(1)} u="MPa" b/><R l="Injection pressure" v={pr.ip.toFixed(1)} u="MPa" b/>
        <R l="Packing pressure" v={pr.packP.toFixed(1)} u="MPa"/><R l="Clamp force" v={pr.cf.toFixed(1)} u="tons" b/>
        <div className="mt-2 p-2 bg-indigo-50 rounded border border-indigo-100"><p className="text-[11px] font-semibold text-indigo-900">Machine: {pr.mc}</p></div>
      </Sec>
      <Sec title="Volume & Cycle" badge={<B t={`${pr.density} g/cm³`} c="gray" />}>
        <R l="Part volume" v={(t.part_volume_mm3/1000).toFixed(2)} u="cm³"/>
        <R l="Shot weight (part)" v={pr.swPart.toFixed(1)} u="g"/>
        <R l="Shot weight (+ runner)" v={pr.swTotal.toFixed(1)} u="g" b/>
        <div className="h-px bg-gray-100 my-1"/>
        <R l="Fill time" v={pr.fillTime.toFixed(2)} u="s"/>
        <R l="Packing time" v={pr.packTime.toFixed(1)} u="s"/>
        <R l="Cooling time" v={pr.coolTime.toFixed(1)} u="s"/>
        <R l="Cycle time (est.)" v={pr.cycleTime.toFixed(1)} u="s" b/>
      </Sec>
    </div>
  );
}

// --- Ceramic Feasibility Panel ---
function CeramicPanel({ data }: { data: any }) {
  const ratingColors: Record<string,string> = { "GO": "green", "CAUTION": "amber", "NO-GO": "red" };
  const statusIcons: Record<string,string> = { pass: "✅", caution: "⚠️", fail: "❌", unknown: "❓" };

  // Group checks by category
  const categories = ["geometry", "tooling", "structural", "thermal", "integration", "manufacturing", "process", "business"];
  const grouped: Record<string, any[]> = {};
  for (const cat of categories) grouped[cat] = [];
  for (const ch of data.checks) {
    if (grouped[ch.category]) grouped[ch.category].push(ch);
    else grouped[ch.category] = [ch];
  }

  const catLabels: Record<string,string> = {
    geometry: "Part Geometry", tooling: "Moldability / Tooling", structural: "Structural",
    thermal: "Thermal", integration: "Insert-to-Base", manufacturing: "Manufacturing",
    process: "Process / Material", business: "Tool Life / Business"
  };

  return (
    <div className="p-4">
      {/* Rating header */}
      <div className={`mb-4 p-3 rounded-lg border ${
        data.rating === "GO" ? "bg-green-50 border-green-200" :
        data.rating === "CAUTION" ? "bg-amber-50 border-amber-200" :
        "bg-red-50 border-red-200"
      }`}>
        <div className="flex items-center justify-between mb-1.5">
          <span className={`text-lg font-bold ${
            data.rating === "GO" ? "text-green-800" :
            data.rating === "CAUTION" ? "text-amber-800" : "text-red-800"
          }`}>{data.rating}</span>
          <CB l={data.confidence} />
        </div>
        <p className="text-xs text-gray-600 leading-relaxed">{data.summary}</p>
        <div className="flex gap-3 mt-2 text-[10px]">
          <span className="text-green-700">{data.statistics.pass} pass</span>
          <span className="text-amber-700">{data.statistics.caution} caution</span>
          <span className="text-red-700">{data.statistics.fail} fail</span>
        </div>
      </div>

      {/* Checks by category */}
      {categories.map(cat => {
        const checks = grouped[cat];
        if (!checks || checks.length === 0) return null;
        const hasFail = checks.some((c: any) => c.status === "fail");
        const hasCaution = checks.some((c: any) => c.status === "caution" && (c.severity === "high" || c.severity === "critical"));
        return (
          <Sec key={cat} title={catLabels[cat] || cat} badge={
            hasFail ? <B t="FAIL" c="red" /> : hasCaution ? <B t="CAUTION" c="amber" /> : <B t="OK" c="green" />
          }>
            {checks.map((ch: any, i: number) => (
              <div key={i} className="py-1.5 border-b border-gray-50 last:border-0">
                <div className="flex items-start gap-1.5">
                  <span className="text-xs mt-0.5">{statusIcons[ch.status] || "?"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-900">{ch.name}</span>
                      <span className={`text-[9px] px-1 rounded ${
                        ch.severity === "critical" ? "bg-red-100 text-red-700" :
                        ch.severity === "high" ? "bg-amber-100 text-amber-700" :
                        ch.severity === "medium" ? "bg-yellow-100 text-yellow-700" :
                        "bg-gray-100 text-gray-500"
                      }`}>{ch.severity}</span>
                    </div>
                    <p className="text-[10px] text-gray-600 mt-0.5">{ch.finding}</p>
                    {ch.risk && <p className="text-[10px] text-gray-400 italic mt-0.5">{ch.risk}</p>}
                    {ch.recommendation && <p className="text-[10px] text-blue-600 mt-0.5">→ {ch.recommendation}</p>}
                  </div>
                </div>
              </div>
            ))}
          </Sec>
        );
      })}

      {/* Top risks */}
      {data.top_risks.length > 0 && (
        <Sec title="Top Risks">
          {data.top_risks.map((r: string, i: number) => (
            <p key={i} className="text-[10px] text-red-600 py-0.5">• {r}</p>
          ))}
        </Sec>
      )}

      {/* Improvements */}
      {data.could_improve.length > 0 && (
        <Sec title="What Could Improve the Rating">
          {data.could_improve.map((c: string, i: number) => (
            <p key={i} className="text-[10px] text-green-700 py-0.5">→ {c}</p>
          ))}
        </Sec>
      )}

      {/* Assumptions */}
      <Sec title="Assumptions">
        {data.assumptions.map((a: string, i: number) => (
          <p key={i} className="text-[10px] text-gray-500">• {a}</p>
        ))}
      </Sec>

      {/* Missing inputs */}
      <Sec title="Missing Inputs">
        {data.missing_inputs.map((m: string, i: number) => (
          <p key={i} className="text-[10px] text-amber-600">• {m}</p>
        ))}
      </Sec>
    </div>
  );
}

// --- Main Page ---
export default function AnalysisPage() {
  const params = useParams(); const router = useRouter(); const partId = params.partId as string;
  const [part, setPart] = useState<PartInfo|null>(null);
  const [plan, setPlan] = useState<any>(null);
  const [ceramic, setCeramic] = useState<any>(null);
  const [fillMeta, setFillMeta] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [mat, setMat] = useState("ABS");
  const [tab, setTab] = useState<"molding"|"ceramic"|"flow">("molding");
  const pollRef = useRef<ReturnType<typeof setInterval>|null>(null);
  const token = typeof window!=="undefined"?localStorage.getItem("token"):null;

  useEffect(() => {
    if (!token) { router.push("/login"); return; }
    const fetchPart = async () => {
      try { const r = await fetch(`${API_URL}/api/parts/${partId}`,{headers:{Authorization:`Bearer ${token}`}}); if(r.status===401){router.push("/login");return null;} if(!r.ok)return null; const d=await r.json(); setPart(d); return d; } catch{return null;}
    };
    const fetchData = async (p: any) => {
      if (p.molding_plan_url) try { const r = await fetch(`${API_URL}${p.molding_plan_url}`); if(r.ok){const d=await r.json();setPlan(d);if(d.material?.primary?.family&&MATERIAL_DB[d.material.primary.family])setMat(d.material.primary.family);} } catch{}
      if (p.ceramic_feasibility_url) try { const r = await fetch(`${API_URL}${p.ceramic_feasibility_url}`); if(r.ok){setCeramic(await r.json());} } catch{}
      if (p.fill_time_meta_url) try { const r = await fetch(`${API_URL}${p.fill_time_meta_url}`); if(r.ok){setFillMeta(await r.json());} } catch{}
    };
    const init = async () => {
      const p = await fetchPart();
      if(p?.status==="analyzed") await fetchData(p);
      setLoading(false);
      if(p&&p.status!=="analyzed"&&p.status!=="error") {
        pollRef.current = setInterval(async()=>{const pp=await fetchPart();if(pp?.status==="analyzed"){await fetchData(pp);if(pollRef.current)clearInterval(pollRef.current);}else if(pp?.status==="error"){if(pollRef.current)clearInterval(pollRef.current);}},2000);
      }
    };
    init();
    return ()=>{if(pollRef.current)clearInterval(pollRef.current);};
  }, [partId]);

  if(loading) return <div className="flex items-center justify-center h-[calc(100vh-56px)]"><div className="animate-spin h-8 w-8 border-2 border-brand-600 border-t-transparent rounded-full"/></div>;
  if(!part) return <div className="flex items-center justify-center h-[calc(100vh-56px)]"><p className="text-gray-500">Part not found</p></div>;
  const isP = part.status==="processing"||part.status==="uploaded";

  return (
    <div className="h-[calc(100vh-56px)] flex flex-col">
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4"><a href="/dashboard" className="text-xs text-gray-400 hover:text-gray-600">&larr; Dashboard</a><h2 className="text-sm font-semibold text-gray-900">{part.name}</h2><span className="text-xs text-gray-400">{part.filename}</span></div>
        <a href="/upload" className="text-xs text-brand-600 hover:text-brand-700">Upload another</a>
      </div>
      {isP&&<div className="bg-blue-50 border-b border-blue-200 px-4 py-3 flex items-center gap-3"><div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full"/><p className="text-sm font-medium text-blue-900">Analyzing geometry...</p></div>}
      {part.status==="error"&&<div className="bg-red-50 border-b border-red-200 px-4 py-3"><p className="text-sm font-medium text-red-900">Analysis failed</p>{part.error_message&&<p className="text-xs text-red-700">{part.error_message}</p>}</div>}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 relative">
          {tab==="flow" && part.mesh_url && part.fill_time_url && fillMeta ? (
            <FillTimeViewer
              meshUrl={`${API_URL}${part.mesh_url}`}
              fillTimeUrl={`${API_URL}${part.fill_time_url}`}
              meta={fillMeta}
              partId={partId}
            />
          ) : (
            <PartViewer
              meshUrl={part.mesh_url?`${API_URL}${part.mesh_url}`:null}
              facemapUrl={part.facemap_url?`${API_URL}${part.facemap_url}`:null}
              topologyUrl={part.topology_url?`${API_URL}${part.topology_url}`:null}
            />
          )}
        </div>
        <div className="w-[420px] border-l border-gray-200 flex flex-col">
          {/* Tabs */}
          <div className="flex border-b border-gray-200 shrink-0">
            <button onClick={()=>setTab("molding")} className={`flex-1 px-3 py-2 text-xs font-medium ${tab==="molding"?"text-brand-600 border-b-2 border-brand-600 bg-white":"text-gray-500 hover:text-gray-700"}`}>Molding</button>
            <button onClick={()=>setTab("flow")} className={`flex-1 px-3 py-2 text-xs font-medium ${tab==="flow"?"text-brand-600 border-b-2 border-brand-600 bg-white":"text-gray-500 hover:text-gray-700"}`}>
              Flow Sim
            </button>
            <button onClick={()=>setTab("ceramic")} className={`flex-1 px-3 py-2 text-xs font-medium ${tab==="ceramic"?"text-brand-600 border-b-2 border-brand-600 bg-white":"text-gray-500 hover:text-gray-700"}`}>
              Ceramic
              {ceramic && <span className={`ml-1.5 text-[9px] px-1 rounded ${ceramic.rating==="GO"?"bg-green-100 text-green-700":ceramic.rating==="CAUTION"?"bg-amber-100 text-amber-700":"bg-red-100 text-red-700"}`}>{ceramic.rating}</span>}
            </button>
          </div>
          {/* Panel content */}
          <div className="flex-1 overflow-y-auto">
            {tab==="molding" && (plan ? <MoldingPanel plan={plan} mat={mat} onMat={setMat}/> : isP ? <div className="p-8 text-center"><div className="animate-spin h-6 w-6 border-2 border-gray-300 border-t-brand-600 rounded-full mx-auto mb-3"/><p className="text-sm text-gray-500">Generating...</p></div> : <div className="p-8 text-center"><p className="text-sm text-gray-500">No data.</p></div>)}
            {tab==="flow" && (fillMeta ? <FlowSimControls partId={partId}/> : isP ? <div className="p-8 text-center"><div className="animate-spin h-6 w-6 border-2 border-gray-300 border-t-brand-600 rounded-full mx-auto mb-3"/><p className="text-sm text-gray-500">Computing fill time...</p></div> : <div className="p-8 text-center"><p className="text-sm text-gray-500">No simulation available.</p></div>)}
            {tab==="ceramic" && (ceramic ? <CeramicPanel data={ceramic}/> : isP ? <div className="p-8 text-center"><div className="animate-spin h-6 w-6 border-2 border-gray-300 border-t-brand-600 rounded-full mx-auto mb-3"/><p className="text-sm text-gray-500">Analyzing...</p></div> : <div className="p-8 text-center"><p className="text-sm text-gray-500">No data.</p></div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
