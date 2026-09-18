let state;
const labels={PRIVATE_CAR:'Privé auto',BIKE:'Fiets',TRAIN:'Trein',COMPANY_CAR:'Dienstwagen'};
const $=id=>document.getElementById(id);
function el(tag,text){const node=document.createElement(tag);if(text!=null)node.textContent=text;return node;}
function options(select,items,selected=''){
  select.replaceChildren();const empty=el('option','— Kies —');empty.value='';select.append(empty);
  for(const [value,label] of items){const o=el('option',label);o.value=value;select.append(o);}select.value=selected;
}
function employeeOptions(select,value){options(select,state.employees.map(e=>[e.id,`${e.name} (#${e.id})`]),value);}
function locationOptions(select,value){options(select,state.locations.map(e=>[e.id,e.name]),value);}
function modeOptions(select,value){options(select,Object.entries(labels),value);}
function name(id){return state.employees.find(e=>e.id===id)?.name||'Onbekend';}
function locationName(id){return state.locations.find(e=>e.id===id)?.name||'Onbekend';}
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function refresh(){const r=await fetch('/api/state');if(!r.ok)throw Error('Gegevens laden mislukt.');state=await r.json();render();}
async function save(action,data){
  const r=await fetch(`/api/action/${action}`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({revision:state.revision,data})});
  const result=await r.json();if(!r.ok)throw Error(result.error||'Opslaan mislukt.');
  await refresh();message('Opgeslagen. Instellingen blijven bewaard na herstart.');
}
function formData(form){const d=Object.fromEntries(new FormData(form));for(const key of ['employee_id','location_id'])if(key in d)d[key]=Number(d[key]);return d;}
function bind(form,action,extra=()=>({})){form.addEventListener('submit',async event=>{
  event.preventDefault();const button=form.querySelector('button');button.disabled=true;
  try{await save(action,{...formData(form),...extra()});}catch(error){message(error.message,true);}finally{button.disabled=false;}
});}
function field(form,text,node,name){node.name=name;node.required=true;const label=el('label',text);label.append(node);form.append(label);return node;}
function render(){
  const selections=new Map([...document.querySelectorAll('select')].map(s=>[s,s.value]));
  document.querySelectorAll('select.employees').forEach(s=>employeeOptions(s,selections.get(s)));
  document.querySelectorAll('select.locations').forEach(s=>locationOptions(s,selections.get(s)));
  document.querySelectorAll('select.modes').forEach(s=>modeOptions(s,selections.get(s)));
  options($('agents'),state.planet_agents.filter(a=>a.employee_id==null).map(a=>[a.planet_id,`${a.planet_id} — ${a.name}`]),selections.get($('agents')));
  $('summary').textContent=`${state.employees.length} werknemers · ${state.settings.length} instellingsversies · ${state.candidates.filter(c=>!c.reviewed).length} uitzonderingsregels · ${state.planet_agents.filter(a=>a.employee_id==null).length} agenten te koppelen`;
  renderSettings();renderRelocation();renderCandidates();
  $('aliases').replaceChildren(...state.aliases.map(a=>el('p',`${a.source}: ${a.name_key} → ${locationName(a.location_id)}`)));
  $('changes').replaceChildren(...state.changes.slice(-30).reverse().map(c=>el('p',`${c.happened_at} — ${c.reason}`)));
}
function renderSettings(){
  const search=$('search').value.toLowerCase();const day=$('asof').value;
  const active=new Map();for(const s of state.settings){const key=`${s.employee_id}/${s.location_id}`;if(s.valid_from<=day&&(!active.has(key)||active.get(key).valid_from<s.valid_from))active.set(key,s);}
  const rows=state.settings.filter(s=>$('history').checked||active.get(`${s.employee_id}/${s.location_id}`)?.id===s.id).map(s=>[name(s.employee_id),locationName(s.location_id),s.valid_from,s.kms,labels[s.mode],active.get(`${s.employee_id}/${s.location_id}`)?.id===s.id?'Bevestigd':s.valid_from>day?'Toekomstig':'Historie']);
  const seen=new Set();
  for(const c of state.candidates.filter(c=>!c.reviewed)){
    const key=JSON.stringify([c.name,c.location,c.kms,c.mode]);if(seen.has(key))continue;seen.add(key);
    rows.push([c.name||'Naam ontbreekt',c.location||'Locatie ontbreekt','—',c.kms??'Ontbreekt',labels[c.mode]||'Ontbreekt','Nakijken']);
  }
  rows.sort((a,b)=>a[0].localeCompare(b[0],'nl')||a[1].localeCompare(b[1],'nl'));
  $('settings').replaceChildren(...rows.filter(r=>(`${r[0]} ${r[1]}`).toLowerCase().includes(search)).map(r=>{const tr=el('tr');for(const value of r)tr.append(el('td',value));return tr;}));
}
function renderRelocation(){
  const employee=Number($('movingEmployee').value);const latest=new Map();
  for(const s of state.settings.filter(s=>s.employee_id===employee)){if(!latest.has(s.location_id)||latest.get(s.location_id).valid_from<s.valid_from)latest.set(s.location_id,s);}
  $('moveRows').replaceChildren(...[...latest.values()].map(s=>{
    const row=el('div');row.className='moveRow grid';row.dataset.location=s.location_id;
    row.append(el('strong',`${locationName(s.location_id)} · laatste ingangsdatum ${s.valid_from}`));
    const km=el('input');km.type='text';km.inputMode='decimal';km.name=`km_${s.location_id}`;km.required=true;km.placeholder=`Oud: ${s.kms} km — nieuwe afstand invullen`;
    const l=el('label','Nieuwe kilometers');l.append(km);row.append(l);
    const mode=el('select');mode.name=`mode_${s.location_id}`;mode.required=true;modeOptions(mode,s.mode);
    const ml=el('label','Vervoer na verhuizing');ml.append(mode);row.append(ml);return row;
  }));
  if(!latest.size)$('moveRows').append(el('p','Kies een werknemer met bestaande locatie-instellingen.'));
}
function renderCandidates(){
  $('candidates').replaceChildren();
  const pending=state.candidates.filter(c=>!c.reviewed);
  $('candidates').append(el('p',`${pending.length} uitzonderingsregels. Alleen deze gegevens hebben nog correctie nodig.`));
  for(const c of pending){
    const card=el('div');card.className='candidate';
    card.append(el('h3',`Bronrij ${c.source_row} — ${c.name||'Naam ontbreekt'} — ${c.location||'Locatie ontbreekt'}`));
    card.append(el('p',`Bronafstand: ${c.kms??'onbekend'} · vervoer: ${labels[c.mode]||'onbekend'}`));
    const issueList=JSON.parse(c.issues);if(issueList.length){const note=el('p',issueList.join(', '));note.className='warning';card.append(note);}
    const f=el('form');f.className='grid';
    const matches=state.employees.filter(e=>e.name.trim().toLowerCase().replace(/\s+/g,' ')===(c.name||'').trim().toLowerCase().replace(/\s+/g,' '));
    employeeOptions(field(f,'Bevestigde werknemer',el('select'),'employee_id'),matches.length===1?matches[0].id:'');
    const alias=state.aliases.find(a=>a.source==='reference'&&a.name_key===(c.location||'').trim().toLowerCase().replace(/\s+/g,' '));
    locationOptions(field(f,'Bevestigde fysieke locatie',el('select'),'location_id'),alias?.location_id||'');
    const km=field(f,'Bevestigde kilometers',el('input'),'kms');km.type='text';km.inputMode='decimal';km.value=c.kms??'';
    modeOptions(field(f,'Bevestigd vervoer',el('select'),'mode'),c.mode||'');
    const start=field(f,'Geldig vanaf',el('input'),'valid_from');start.type='date';
    const reason=field(f,'Reden',el('input'),'reason');reason.value='Eenmalige referentie bevestigd';reason.maxLength=250;
    const b=el('button','Bevestigen en opslaan');f.append(b);bind(f,'candidate',()=>({candidate_id:c.id}));
    card.append(f);
    const ignoreForm=el('form');ignoreForm.className='grid ignoreForm';
    const ignoreReason=field(ignoreForm,'Reden voor negeren',el('input'),'reason');ignoreReason.value='Overbodige bronregel';ignoreReason.maxLength=250;
    const ignoreButton=el('button','Negeren');ignoreButton.className='secondary';ignoreForm.append(ignoreButton);
    bind(ignoreForm,'ignore_candidate',()=>({candidate_id:c.id}));
    card.append(ignoreForm);$('candidates').append(card);
  }
  const ignored=state.candidates.filter(c=>c.reviewed===2);
  if(ignored.length){
    const archive=el('details');archive.append(el('summary',`Genegeerde bronregels (${ignored.length})`));
    for(const c of ignored){
      const row=el('div');row.className='candidate';
      row.append(el('p',`Bronrij ${c.source_row} — ${c.name||'Naam ontbreekt'} — ${c.location||'Locatie ontbreekt'}`));
      const change=[...state.changes].reverse().find(item=>{const details=JSON.parse(item.details);return details.action==='ignore_candidate'&&details.candidate_id===c.id;});
      if(change)row.append(el('p',`Reden: ${change.reason}`));
      const restore=el('form');restore.append(el('button','Terug naar Nakijken'));bind(restore,'restore_candidate',()=>({candidate_id:c.id}));row.append(restore);archive.append(row);
    }
    $('candidates').append(archive);
  }
}
for(const id of ['employee','location','link','setting','alias'])bind($(id),id);
bind($('relocation'),'relocation',()=>({updates:[...$('moveRows').querySelectorAll('.moveRow')].map(row=>({location_id:Number(row.dataset.location),kms:row.querySelector('input').value,mode:row.querySelector('select').value}))}));
$('refresh').addEventListener('click',()=>refresh().then(()=>message('Gegevens vernieuwd.')).catch(e=>message(e.message,true)));
$('movingEmployee').addEventListener('change',renderRelocation);
$('search').addEventListener('input',()=>state&&renderSettings());$('asof').addEventListener('change',()=>state&&renderSettings());
$('history').addEventListener('change',()=>state&&renderSettings());
const now=new Date();$('asof').value=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
refresh().catch(e=>message(e.message,true));
