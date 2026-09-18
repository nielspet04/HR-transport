// Bounded UI orchestration tests, no browser/token/network/HR data.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync('backend/app/configuration/web/routes.js','utf8');
const start=source.indexOf('function renderBulkGeocoding(');
const end=source.indexOf('\nfunction bind(',start);
async function scenario({error=false,stop=false,consent=true}={}){
  const nodes=[];let stopButton;let calls=[];
  const bulk={running:false,stop:false,completed:0,total:0,text:''};
  function el(tag,text){const n={tag,text,children:[],listeners:{},checked:consent,disabled:false,append(...v){this.children.push(...v);},setAttribute(){},addEventListener(k,fn){this.listeners[k]=fn;}};nodes.push(n);return n;}
  const section=el('section');
  const state={mapbox_configured:true,geocoding_bulk_plan:{requests:2,address_ids:[10,11],existing_profiles:1,blocked_profiles:0},addresses:[{id:10},{id:11}]};
  const context={state,bulkGeocoding:bulk,el,document:{createTextNode:t=>t},$:id=>nodes.find(n=>n.id===id),message(){},renderAddresses(){},save:async(action,data)=>{
    assert.equal(action,'address_geocode_bulk_item');assert.equal(data.consent,true);calls.push(data.address_id);
    state.addresses.find(a=>a.id===data.address_id).geocode_status=error?'ERROR':'REVIEW';
    if(stop)stopButton.listeners.click();
  }};
  vm.createContext(context);vm.runInContext(source.slice(start,end),context);context.renderBulkGeocoding(section);
  stopButton=nodes.find(n=>n.text==='Stop na huidig adres');
  await nodes.find(n=>n.tag==='button'&&String(n.text).startsWith('Alles opvragen')).listeners.click();
  return {bulk,calls};
}
(async()=>{
  let r=await scenario();assert.deepEqual(r.calls,[10,11]);assert.equal(r.bulk.completed,2);assert.equal(r.bulk.running,false);
  r=await scenario({stop:true});assert.deepEqual(r.calls,[10]);assert.match(r.bulk.text,/Gestopt/);
  r=await scenario({error:true});assert.deepEqual(r.calls,[10]);assert.match(r.bulk.text,/API-fout/);
  r=await scenario({consent:false});assert.deepEqual(r.calls,[]);
  console.log('4 bulk UI scenarios passed: complete, stop, API error, missing consent.');
})().catch(error=>{console.error(error);process.exitCode=1;});
