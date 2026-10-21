import test from "node:test";
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";
import {dirname,resolve} from "node:path";
import {calculateMultilayerState,multilayerSchema,syntheticMultilayerInput} from "./field-state.mjs";

const here=dirname(fileURLToPath(import.meta.url));
const appRoot=resolve(here,"..");

test("schema lists 26 required inputs",()=>{
  const s=multilayerSchema();
  assert.equal(s.required_count,26);
  assert.equal(Object.values(s.observations).flat().length,26);
});

test("synthetic mid-range scenario returns all six indices = 50",async()=>{
 const v=await calculateMultilayerState(syntheticMultilayerInput());
 assert.equal(Object.keys(v.state_vector).length,6);
 for(const n of Object.values(v.state_vector))assert.ok(Math.abs(n-50)<1e-10);
 assert.equal(v.classification,"MIXED_TRANSITIONAL");
 assert.match(v.provenance.input_sha256,/^[a-f0-9]{64}$/);
 assert.match(v.observations.packet_loss.observation_id,/^[a-f0-9]{24}$/);
});

test("derived IR human load agrees with HLI",async()=>{
 const a=syntheticMultilayerInput();
 for(const x of Object.values(a.observations))x.value=0;
 a.observations.sleep_debt.value=1;
 const r=await calculateMultilayerState(a);
 assert.ok(Math.abs(r.state_vector.HLI-30)<1e-10);
 assert.ok(Math.abs(r.state_vector.IR-7.5)<1e-10);
 assert.equal(r.decomposition.IR.normalized_inputs.human_load,.3);
});

test("symbolic annotations excluded from calculation",async()=>{
 const a=syntheticMultilayerInput();
 const x=await calculateMultilayerState(a);
 a.symbolic_notes.push({evidence_class:"symbolic",text:"Another interpretation"});
 const y=await calculateMultilayerState(a);
 assert.deepEqual(x.state_vector,y.state_vector);
});

test("missing, extra, unsupported and out-of-bounds fields rejected",async()=>{
 for(const alteration of [
  a=>{delete a.observations.packet_loss},
  a=>{a.observations.ghost={value:0,evidence_class:"symbolic"}},
  a=>{a.observations.packet_loss.evidence_class="symbolic"},
  a=>{a.observations.packet_loss.value=2},
  a=>{a.observations.packet_loss.evidence_class=["measured"]},
 ]){
  const a=syntheticMultilayerInput();
  alteration(a);
  await assert.rejects(()=>calculateMultilayerState(a));
 }
});

test("non-normalized raw input clamps and preserves source",async()=>{
 const a=syntheticMultilayerInput();
 a.observations.wind_intensity={raw:5,minimum:0,maximum:10,evidence_class:"measured",unit:"m/s",source:"synthetic wind"};
 const r=await calculateMultilayerState(a);
 assert.equal(r.observations.wind_intensity.value,.5);
 assert.equal(r.observations.wind_intensity.raw_input.raw,5);
});

test("replay digests deterministic",async()=>{
 const a=syntheticMultilayerInput();
 const [r1,r2]=await Promise.all([calculateMultilayerState(a),calculateMultilayerState(structuredClone(a))]);
 assert.deepEqual(r1,r2);
});

test("Python reference parity for synthetic and perturbed scenario",async()=>{
 const scenarios=[syntheticMultilayerInput(),syntheticMultilayerInput()];
 scenarios[1].observations.sleep_debt.value=0.9;
 scenarios[1].observations.packet_loss.value=0.1;
 scenarios[1].observations.source_quality.value=0.8;
 const py="import json,sys; from field_calculator import calculate; a=json.load(sys.stdin); print(json.dumps(calculate(a)['state_vector']))";
 for(const scenario of scenarios){
  const python=spawnSync("python",["-c",py],{cwd:appRoot,encoding:"utf8",input:JSON.stringify(scenario)});
  assert.equal(python.status,0,python.stderr);
  const reference=JSON.parse(python.stdout);
  const result=(await calculateMultilayerState(scenario)).state_vector;
  for(const k of Object.keys(reference))assert.ok(Math.abs(reference[k]-result[k])<1e-9,k);
 }
});
