// SOVRINT Field Calculator v1.0 — Cloudflare JavaScript parity implementation.
// Proposed dimensionless scores only; no physical/clinical causal claims.
const EAS={pressure_change:.15,wind_intensity:.10,precipitation_severity:.10,temperature_stress:.10,humidity_stress:.10,air_quality_severity:.15,geomagnetic_activity:.15,solar_alert_severity:.15};
const TSS={packet_loss:.20,latency_deviation:.20,rf_noise_elevation:.20,outage_severity:.15,gnss_degradation:.10,equipment_anomaly_rate:.15};
const HLI={sleep_debt:.30,cognitive_load:.25,emotional_load:.20,physical_stress:.15,attentional_fragmentation:.10};
const OC={source_quality:.40,data_recency:.25,layer_coverage:.20,source_agreement:.15};
const IR={evidence_gap:.35,human_load:.25,anomaly_density:.20,source_disagreement:.20};
const FCS={environmental_stability:.30,technical_stability:.25,human_readiness:.20,observability_confidence:.25};
const GROUPS={EAS,TSS,HLI,OC,IR:Object.fromEntries(Object.entries(IR).filter(([k])=>k!=="human_load"))};
const INPUT_GROUPS=Object.fromEntries(Object.entries(GROUPS).flatMap(([group,w])=>Object.keys(w).map(k=>[k,group])));
const EVIDENCE={EAS:["measured"],TSS:["measured"],HLI:["measured","self_reported"],OC:["measured","interpretive"],IR:["measured","interpretive"]};
const VERSION="1.0.0";
function text(x,k){if(typeof x!=="string"||!x.trim())throw Error(k+" must be a non-empty string");return x;}
function num(x,k){if(typeof x!=="number"||!Number.isFinite(x))throw Error(k+" must be a finite number");return x;}
function frac(x,k){x=num(x,k);if(x<0||x>1)throw Error(k+" must be in [0,1]");return x;}
function utc(x,k){text(x,k);if(!x.endsWith("Z")||!Number.isFinite(Date.parse(x)))throw Error(k+" must be a valid ISO-8601 UTC timestamp ending in Z");return x;}
function norm(v,k){
 const hasValue=Object.hasOwn(v,"value"),hasRaw=["raw","minimum","maximum"].some(q=>Object.hasOwn(v,q));
 if(hasValue===hasRaw)throw Error(k+" requires value OR raw/minimum/maximum");
 if(hasValue)return frac(v.value,k+".value");
 for(const j of ["raw","minimum","maximum"])if(!Object.hasOwn(v,j))throw Error(k+" requires raw,minimum,maximum");
 const raw=num(v.raw,k+".raw"),mi=num(v.minimum,k+".minimum"),ma=num(v.maximum,k+".maximum");
 if(ma<=mi)throw Error(k+" maximum must exceed minimum");
 return Math.max(0,Math.min(1,(raw-mi)/(ma-mi)));
}
function weighted(v,w){const tw=Object.values(w).reduce((a,b)=>a+b,0);return Object.entries(w).reduce((a,[k,p])=>a+p*v[k],0)/tw;}
function canonical(obj){if(Array.isArray(obj))return "["+obj.map(canonical).join(",")+"]";if(obj&&typeof obj==="object")return "{"+Object.keys(obj).sort().map(k=>JSON.stringify(k)+":"+canonical(obj[k])).join(",")+"}";return JSON.stringify(obj);}
async function digest(x){const bytes=new TextEncoder().encode(typeof x==="string"?x:canonical(x));const out=await crypto.subtle.digest("SHA-256",bytes);return Array.from(new Uint8Array(out),n=>n.toString(16).padStart(2,"0")).join("");}
function band(v){const n=Math.min(100,Math.floor(v));if(n<20)return "CRITICAL_INSTABILITY";if(n<40)return "HIGH_DISTURBANCE";if(n<60)return "MIXED_TRANSITIONAL";if(n<80)return "STABLE_WITH_ACTIVE_VARIABLES";return "HIGH_COHERENCE";}
export function syntheticMultilayerInput(){
const observations={};
for(const [k,g] of Object.entries(INPUT_GROUPS))observations[k]={value:.5,unit:"normalized_fraction",evidence_class:g==="HLI"?"self_reported":(g==="OC"||g==="IR"?"interpretive":"measured"),confidence:.5};
return {context:{created_at:"2026-10-21T12:00:00Z",location:"synthetic-no-real-location",source:"synthetic_fixture_not_an_observed_measurement",source_class:"synthetic"},observations,symbolic_notes:[{evidence_class:"symbolic",text:"Synthetic illustration only; excluded from scoring."}]};
}
export function multilayerSchema(){
return {tool:"calculate_multilayer_state",model:"SOVRINT six-index field-state vector",version:VERSION,required_context:["created_at","location","source","source_class"],observations:Object.fromEntries(Object.entries(GROUPS).map(([g,w])=>[g,Object.keys(w)])),required_count:Object.keys(INPUT_GROUPS).length,input_format:"Each observation requires evidence_class and either value between 0 and 1 or raw/minimum/maximum with maximum>minimum. Optional unit, source, source_class, source_url, confidence, created_at, retrieved_at and user_notes.",evidence_classes:EVIDENCE,weights:{EAS,TSS,HLI,OC,IR,FCS},derived:"IR.human_load is HLI/100; FCS uses environmental_stability=1-EAS/100, technical_stability=TSS/100, human_readiness=1-HLI/100 and observability_confidence=OC/100.",caution:"Illustrative indices, not verified physical fields, medical diagnostics or causal evidence. Never submit sensitive personal information to this unauthenticated public demonstrator.",synthetic_example:syntheticMultilayerInput()};
}
export const multilayerToolSchema={type:"object",additionalProperties:false,required:["context","observations"],properties:{context:{type:"object",additionalProperties:false,required:["created_at","location","source","source_class"],properties:{created_at:{type:"string"},location:{type:"string"},source:{type:"string"},source_class:{type:"string"}}},observations:{type:"object",additionalProperties:false,required:Object.keys(INPUT_GROUPS),properties:Object.fromEntries(Object.keys(INPUT_GROUPS).map(k=>[k,{type:"object",description:"evidence_class and normalized value 0–1, or raw/minimum/maximum; see multilayer_schema",required:["evidence_class"],properties:{evidence_class:{type:"string",enum:EVIDENCE[INPUT_GROUPS[k]]},value:{type:"number",minimum:0,maximum:1},raw:{type:"number"},minimum:{type:"number"},maximum:{type:"number"},unit:{type:"string"},source:{type:"string"},source_class:{type:"string"},source_url:{type:"string"},confidence:{type:"number",minimum:0,maximum:1},created_at:{type:"string"},retrieved_at:{type:"string"},user_notes:{type:"string"}}}] ))},symbolic_notes:{type:"array",items:{type:"object",required:["evidence_class","text"],properties:{evidence_class:{type:"string",enum:["symbolic"]},text:{type:"string"}}}}}};
export async function calculateMultilayerState(payload){
if(!payload||typeof payload!=="object"||Array.isArray(payload))throw Error("input must be a JSON object");
if(Object.keys(payload).some(k=>!["context","observations","symbolic_notes"].includes(k)))throw Error("unknown input fields");
const context=payload.context,provided=payload.observations;
if(!context||typeof context!=="object"||!provided||typeof provided!=="object"||Array.isArray(provided))throw Error("context and observations must be objects");
const created=utc(context.created_at,"context.created_at"),location=text(context.location,"context.location"),defaultSource=text(context.source,"context.source"),defaultClass=text(context.source_class,"context.source_class");
const keys=Object.keys(INPUT_GROUPS),missing=keys.filter(k=>!Object.hasOwn(provided,k)),extra=Object.keys(provided).filter(k=>!Object.hasOwn(INPUT_GROUPS,k));
if(missing.length||extra.length)throw Error("observation keys mismatch; missing="+missing.join(",")+"; unknown="+extra.join(","));
const vals={},rows={};
for(const k of keys){
const v=provided[k],g=INPUT_GROUPS[k];
if(!v||typeof v!=="object"||Array.isArray(v))throw Error(k+" must be an object");
if(typeof v.evidence_class!=="string"||!EVIDENCE[g].includes(v.evidence_class))throw Error(k+" invalid evidence_class; symbolic observations cannot score");
const value=norm(v,k),source=text(v.source??defaultSource,k+".source"),sourceClass=text(v.source_class??defaultClass,k+".source_class");
if(v.confidence!==undefined&&v.confidence!==null)frac(v.confidence,k+".confidence");
if(v.user_notes!==undefined&&typeof v.user_notes!=="string")throw Error(k+".user_notes must be text");
if(v.source_url!==undefined&&typeof v.source_url!=="string")throw Error(k+".source_url must be text");
if(v.unit!==undefined)text(v.unit,k+".unit");
const ts=utc(v.created_at??created,k+".created_at"),retrieved=utc(v.retrieved_at??created,k+".retrieved_at");
vals[k]=value;rows[k]={observation_id:(await digest({field:k,input:v,context})).slice(0,24),created_at:ts,retrieved_at:retrieved,location,layer:g,value,unit:v.unit??"normalized_fraction",source,source_class:sourceClass,source_url:v.source_url??null,confidence:v.confidence??null,evidence_class:v.evidence_class,user_notes:v.user_notes??"",calculation_version:VERSION};
if(Object.hasOwn(v,"raw"))rows[k].raw_input={raw:v.raw,minimum:v.minimum,maximum:v.maximum};
}
const notes=payload.symbolic_notes??[];
if(!Array.isArray(notes)||notes.some(x=>!x||typeof x!=="object"||x.evidence_class!=="symbolic"||typeof x.text!=="string"||!x.text.trim()))throw Error("symbolic_notes must contain only labeled non-empty symbolic annotations");
const eas=100*weighted(vals,EAS),tss=100*(1-weighted(vals,TSS)),hli=100*weighted(vals,HLI),oc=100*weighted(vals,OC);
const irInputs={...vals,human_load:hli/100};const ir=100*weighted(irInputs,IR);
const fInputs={environmental_stability:1-eas/100,technical_stability:tss/100,human_readiness:1-hli/100,observability_confidence:oc/100};
const fcs=100*weighted(fInputs,FCS),state={EAS:eas,TSS:tss,HLI:hli,OC:oc,IR:ir,FCS:fcs};
if(Object.values(state).some(v=>!Number.isFinite(v)||v<-.0000001||v>100.0000001))throw Error("result outside permitted [0,100] bounds");
const core={artifact_id:"SOVRINT-FIELD-CALC-001",implementation:"cloudflare-javascript-parity",model_status:"illustrative_indices_not_empirically_validated",calculation_version:VERSION,state_vector:state,classification:band(fcs),decomposition:{EAS:{weights:EAS,normalized_inputs:Object.fromEntries(Object.keys(EAS).map(k=>[k,vals[k]]))},TSS:{weights:TSS,normalized_disturbances:Object.fromEntries(Object.keys(TSS).map(k=>[k,vals[k]]))},HLI:{weights:HLI,normalized_inputs:Object.fromEntries(Object.keys(HLI).map(k=>[k,vals[k]]))},OC:{weights:OC,normalized_inputs:Object.fromEntries(Object.keys(OC).map(k=>[k,vals[k]]))},IR:{weights:IR,normalized_inputs:Object.fromEntries(Object.keys(IR).map(k=>[k,irInputs[k]])),human_load_source:"derived:HLI/100"},FCS:{weights:FCS,normalized_inputs:fInputs}},observations:rows,symbolic_notes_excluded_from_scoring:notes};
return {...core,provenance:{hash_algorithm:"SHA-256",input_sha256:await digest(payload),core_result_sha256:await digest(core),hash_scope:"Cloudflare JavaScript canonical JSON; separate from Python source and exact byte serialization.",notice:"Content hashes support deterministic replay, not source authentication, sensor accuracy or scientific validity."}};
}
