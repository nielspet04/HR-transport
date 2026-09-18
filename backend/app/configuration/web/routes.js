let state,editing=null,matching=null;
let activeView='routes';
let distancePlan=null,distanceRunId=null;
let tariffKind='standard';
let automaticPoll=null;
const openWorkerGroups=new Set();
let distanceWorkerSearch='';

function renderShiftHistory(){
  let section=$('shiftHistory');if(!section){section=el('section');section.id='shiftHistory';$('shiftView').append(section);}section.replaceChildren();
  const close=el('button','Export sluiten');close.className='secondary';close.disabled=!matching;close.addEventListener('click',()=>{matching=null;renderMatching();renderRouteIssues();message('Export gesloten. Alle historische gegevens blijven bewaard.');});section.append(close);
  const details=el('details');details.append(el('summary','Historiek · eerdere maand expliciet openen'),el('p','Eerdere maanden blijven bewaard, maar worden niet automatisch geopend. Kies een maand en klik op Openen.'));
  const runs=new Map();for(const run of state.matching_runs||[])if(!runs.has(run.month))runs.set(run.month,run);
  const select=el('select');selector(select,[...runs.values()].map(r=>({id:r.id,name:r.month})));select.setAttribute('aria-label','Historische maand');const open=el('button','Maand openen');open.addEventListener('click',async()=>{if(!select.value){message('Kies eerst een historische maand.',true);return;}open.disabled=true;try{const response=await fetch(`/api/matching/run?id=${encodeURIComponent(select.value)}`);if(!response.ok)throw Error('Historische maand laden mislukt.');matching=await response.json();renderMatching();renderRouteIssues();message(`Historische maand ${matching.month} geopend.`);}catch(error){message(error.message,true);}finally{open.disabled=false;}});details.append(select,open);section.append(details);
}

function renderRouteIssues(){
  let section=$('routeIssues');if(!section){section=el('section');section.id='routeIssues';$('shiftView').prepend(section);}section.replaceChildren(el('h2','Ontbrekende gegevens · per werknemer en oorzaak'));
  section.hidden=!matching;if(!matching)return;
  if(matching.route_issue_warning){section.append(el('p',matching.route_issue_warning));return;}
  const issues=matching.route_issues||[];
  const groups=new Map();for(const issue of issues){const key=JSON.stringify([issue.worker,issue.reason]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(issue);}
  section.append(el('p',`${issues.length} geblokkeerde beweging/vervoer-vermeldingen voor ${matching.month}. Alleen de geselecteerde maand wordt getoond. Eén instelling kan veel meldingen oplossen. Afstanden worden nooit uit de oude kilometerbron overgenomen.`));
  const search=el('input'),list=el('div');search.placeholder='Zoek werknemer of oorzaak';search.setAttribute('aria-label','Zoek ontbrekende gegevens');section.append(search,list);
  function draw(){list.replaceChildren();for(const rows of [...groups.values()].sort((a,b)=>a[0].worker.localeCompare(b[0].worker,'nl'))){const first=rows[0];if(!`${first.worker} ${first.reason}`.toLocaleLowerCase('nl').includes(search.value.toLocaleLowerCase('nl')))continue;
    const details=el('details');details.append(el('summary',`${first.worker} · ${rows.length} meldingen · ${first.reason}`));const dates=rows.map(r=>r.day).sort();details.append(el('p',`${dates[0]} t/m ${dates.at(-1)} · ${[...new Set(rows.map(r=>r.location))].join(', ')}`));
    if(first.reason==='Geen vervoerswijze geldig op de prestatiedatum.'){
      const w=state.workers.find(w=>w.name===first.worker),routes=state.routes.filter(r=>r.worker_id===w?.id),form=el('form');form.className='grid';const select=el('select');select.required=true;selector(select,routes.map(r=>({id:r.id,name:`${r.location} · ${r.mode} · vanaf ${state.versions.filter(v=>v.route_id===r.id).map(v=>v.valid_from).sort()[0]||'onbekend'}`})));select.setAttribute('aria-label','Vervoersinstelling');const date=el('input');date.type='date';date.required=true;date.value=dates[0];date.setAttribute('aria-label','Werkelijke eerdere ingangsdatum');const reason=el('input');reason.required=true;reason.maxLength=250;reason.placeholder='Reden / bevestiging vervoer';reason.setAttribute('aria-label','Reden eerdere vervoersinstelling');const label=el('label'),check=el('input');check.type='checkbox';check.required=true;label.append(check,document.createTextNode(' Deze vervoerswijze gold werkelijk vanaf deze datum. Latere versies blijven gelden.'));form.append(select,date,reason,label,el('button','Eerdere periode vastleggen'));form.addEventListener('submit',async event=>{event.preventDefault();try{await save('route_historical',{route_id:Number(select.value),valid_from:date.value,reason:reason.value,confirm:check.checked});message('Eerdere periode opgeslagen. De automatische verwerking vernieuwt de shiften en vraagt ontbrekende routes op.');}catch(error){message(error.message,true);}});details.append(form);
    }
    if(first.reason.includes('coördinaten')){const button=el('button','Adres controleren');button.addEventListener('click',()=>showView('addresses'));details.append(button);}
    if(first.reason.includes('niet gekoppeld'))details.append(el('p','Bevestig hieronder bij Naam- en locatiekoppelingen de ontbrekende koppeling. Selecteer een betrokken maand voor de bronagent of bronklant.'));
    if(first.reason.includes('Mob budget'))details.append(el('p','Mob budget heeft nog geen berekeningsregel. Bevestig eerst het werkelijke vervoer en de vergoedingsregel; niet automatisch behandelen als privéauto.'));
    if(first.reason.startsWith('Meerdere locaties'))details.append(el('p','Los eerst ontbrekende koppelingen op. Controleer daarna de bronuren: overlappende shiften hebben geen zekere reisvolgorde.'));
    const days=el('details');days.append(el('summary','Betrokken dagen en locaties'));for(const r of [...new Map(rows.map(r=>[`${r.day} ${r.location}`,r])).values()].sort((a,b)=>a.day.localeCompare(b.day)))days.append(el('p',`${r.day} · ${r.location}`));details.append(days);list.append(details);
  }}search.addEventListener('input',draw);draw();
}

function workerDistanceGroups(rows,headers,prefix,action,search=''){
  const container=el('div'),groups=new Map();
  for(const row of rows){const key=String(row.worker_id);if(!groups.has(key))groups.set(key,{name:row.name,rows:[]});groups.get(key).rows.push(row);}
  const query=search.trim().toLocaleLowerCase('nl');
  for(const [id,group] of [...groups].sort((a,b)=>a[1].name.localeCompare(b[1].name,'nl'))){
    if(query&&!`${group.name} ${group.rows.map(r=>r.values.join(' ')).join(' ')}`.toLocaleLowerCase('nl').includes(query))continue;
    const details=el('details'),summary=el('summary'),key=`${prefix}:${id}`;details.className='worker-distance-group';details.open=openWorkerGroups.has(key);
    const sites=new Set(group.rows.map(r=>r.values[0]));summary.append(el('span',group.name),el('span',`${sites.size} locatie${sites.size===1?'':'s'} · ${group.rows.length} afstand${group.rows.length===1?'':'en'}`));details.append(summary);
    details.addEventListener('toggle',()=>{if(details.open)openWorkerGroups.add(key);else openWorkerGroups.delete(key);});
    const scroll=el('div');scroll.className='scroll';const table=el('table'),thead=el('thead'),head=el('tr');for(const label of [...headers,'Actie'])head.append(el('th',label));thead.append(head);const body=el('tbody');
    for(const row of group.rows.sort((a,b)=>a.values[0].localeCompare(b.values[0],'nl')||a.values[1].localeCompare(b.values[1],'nl'))){const tr=el('tr');for(const value of row.values)tr.append(el('td',value));const cell=el('td');action(cell,row);tr.append(cell);body.append(tr);}table.append(thead,body);scroll.append(table);details.append(scroll);container.append(details);
  }
  if(!container.children.length)container.append(el('p','Geen werknemers gevonden.'));
  return container;
}
const distanceBatch={running:false,stop:false,text:''};
const bulkGeocoding={running:false,stop:false,completed:0,total:0,text:''};
const $=id=>document.getElementById(id);
const today=new Date();const currentDay=`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
function el(tag,text){const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;}
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
function worker(id){return state.workers.find(w=>w.id===id)?.name||'Onbekend';}
function train(route){return (route.mode||'').trim().toLowerCase()==='trein';}
function kmText(route,value,missing='?'){return train(route)?'n.v.t.':`${value??missing} km`;}
function distanceInput(){const form=$('routeForm'),input=form.elements.kms;const excluded=train({mode:form.elements.mode.value});input.required=!excluded;input.readOnly=excluded;if(excluded)input.value='n.v.t.';else if(input.value==='n.v.t.')input.value='';}
function latest(route,day='9999-12-31'){return state.versions.filter(v=>v.route_id===route&&v.valid_from<=day).sort((a,b)=>b.valid_from.localeCompare(a.valid_from))[0];}
async function refresh(newUpload=false){const month=matching?.month,source=matching?.source_sha256;const response=await fetch('/api/state');if(!response.ok)throw Error('Laden mislukt.');state=await response.json();if(state.view!=='routes')throw Error('Herstart het dashboard om het nieuwe routebeheer te openen.');if(newUpload){matching=state.matching;}else if(matching){const selected=state.matching_runs?.find(r=>r.month===month&&r.source_sha256===source);if(selected){const result=await fetch(`/api/matching/run?id=${selected.id}`);if(!result.ok)throw Error('Maand laden mislukt.');matching=await result.json();}else matching=null;}render();}
async function save(action,data){if(bulkGeocoding.running&&!['address_geocode_bulk_item','location_geocode'].includes(action))throw Error('Stop eerst de bulkgeocodering voordat je gegevens wijzigt.');if(distanceBatch.running&&action!=='route_distance_request')throw Error('Stop eerst de routeaanvragen voordat je gegevens wijzigt.');const response=await fetch(`/api/action/${action}`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({revision:state.revision,data})});const result=await response.json();if(!response.ok)throw Error(result.error||'Opslaan mislukt.');await refresh(action==='planet_upload');message('Opgeslagen.');}
function selector(node,items){const selected=node.value;node.replaceChildren();const blank=el('option','— Kies —');blank.value='';node.append(blank);for(const w of items){const option=el('option',w.name);option.value=w.id;node.append(option);}node.value=selected;}
function datalist(id,values){$(id).replaceChildren(...[...new Set(values)].sort((a,b)=>a.localeCompare(b,'nl')).map(value=>{const option=el('option');option.value=value;return option;}));}
function render(){
  const review=state.routes.filter(r=>!train(r)&&latest(r.id)?.kms==null).length;
  $('summary').textContent=`${state.workers.length} werknemers · ${state.routes.length} routes · ${review} afstand(en) na te kijken`;
  datalist('names',state.workers.map(w=>w.name));datalist('locations',state.routes.map(r=>r.location));datalist('modes',[...state.routes.map(r=>r.mode),'Privé auto','Fiets','Trein','Dienstwagen','Auto','Mob budget']);
  selector($('renameWorker'),state.workers);selector($('movingWorker'),state.workers);renderRows();renderMove();renderMatching();renderTariffs();renderLocationAddresses();renderAddresses();renderDistanceRoutes();renderAutomaticRoutes();renderTransferOverview();renderRouteIssues();showView(activeView);
}
function renderRows(){
  const day=$('asof').value,search=$('search').value.toLocaleLowerCase('nl');const rows=[];
  for(const r of state.routes){
    const active=latest(r.id,day),versions=$('history').checked?state.versions.filter(v=>v.route_id===r.id):[active||latest(r.id)];
    for(const v of versions){if(!v)continue;rows.push({route:r,values:[worker(r.worker_id),r.location,r.mode,train(r)?'n.v.t.':v.kms??v.raw_distance??'Ontbreekt',v.valid_from,v.kms==null&&!train(r)?'Nakijken':active?.id===v.id?'Opgeslagen':v.valid_from>day?'Toekomstig':'Historie']});}
  }
  rows.sort((a,b)=>a.values[0].localeCompare(b.values[0],'nl')||a.values[1].localeCompare(b.values[1],'nl')||a.values[2].localeCompare(b.values[2],'nl'));
  const groups=workerDistanceGroups(rows.map(r=>({...r,worker_id:r.route.worker_id,name:r.values[0],values:r.values.slice(1)})),['Locatie','Vervoer','Km','Vanaf','Status'],'manual',(cell,row)=>{const button=el('button','Aanpassen');button.className='secondary';button.addEventListener('click',()=>openEditor(row.route));cell.append(button);},search);
  const tr=el('tr'),cell=el('td');cell.colSpan=7;cell.append(groups);tr.append(cell);$('rows').replaceChildren(tr);
}
function openEditor(route=null){
  editing=route?.id??null;const form=$('routeForm');form.reset();$('editor').hidden=false;$('editorTitle').textContent=route?'Afstand aanpassen':'Werknemer / route toevoegen';
  for(const key of ['name','location','mode']){form.elements[key].readOnly=!!route;form.elements[key].value=route?(key==='name'?worker(route.worker_id):route[key]):'';}
  form.elements.kms.value=route?(latest(route.id)?.kms??''):'';form.elements.valid_from.value=currentDay;
  distanceInput();
  $('editor').scrollIntoView({behavior:'smooth',block:'start'});form.elements[route?'kms':'name'].focus();
}
function renderMove(){
  const routes=state.routes.filter(r=>r.worker_id===Number($('movingWorker').value));
  $('moveRows').replaceChildren(...routes.map(r=>{const label=el('label',`${r.location} · ${r.mode} (oud: ${kmText(r,latest(r.id)?.kms,'onzeker')})`);const input=el('input');input.required=!train(r);input.readOnly=train(r);if(train(r))input.value='n.v.t.';input.inputMode='decimal';input.dataset.route=r.id;label.append(input);return label;}));
  if(!routes.length)$('moveRows').append(el('p','Kies een werknemer.'));
}
function renderLocationAddresses(){
  let section=$('locationAddressProfiles');if(!section){section=el('section');section.id='locationAddressProfiles';$('locationsView').append(section);}
  section.replaceChildren(el('h2','Locaties · klantadressen'),el('p','Bestaande fysieke locaties, geen nieuwe klantenlijst. Klanten in dezelfde groep delen één adres. Adressen wijzigen nog geen afstanden of vergoedingen.'));
  if(!state.physical_locations){section.append(el('p','Herstart de server om locatieadressen toe te voegen.'));return;}
  const day=$('asof').value||currentDay,versions=state.location_addresses||[],form=el('form');form.className='grid';const choose=el('select');choose.required=true;const locationLabel=el('label','Fysieke locatie');locationLabel.append(choose);selector(choose,state.physical_locations.map(l=>({id:l.key,name:l.name})));form.append(locationLabel);const inputs={};
  for(const [field,label] of [['street','Straat'],['number','Huisnummer'],['unit','Bus'],['postal_code','Postcode'],['city','Gemeente'],['country','Landcode'],['valid_from','Geldig vanaf'],['reason','Reden']]){const wrapper=el('label',label),input=el('input');input.type=field==='valid_from'?'date':'text';input.required=field!=='unit';input.maxLength=field==='country'?2:250;inputs[field]=input;wrapper.append(input);form.append(wrapper);}
  const customerHint=el('p');customerHint.className='small';inputs.country.value='BE';inputs.valid_from.value='2026-01-01';inputs.reason.value='HR bevestigt locatieadres';
  function populate(){const loc=state.physical_locations.find(l=>l.key===choose.value),active=versions.filter(v=>v.location_key===choose.value).at(-1);for(const field of ['street','number','unit','postal_code','city','country'])inputs[field].value=active?.address[field]||(field==='country'?'BE':'');inputs.valid_from.value=active?.valid_from||'2026-01-01';inputs.reason.value=active?'Correctie locatieadres':'HR bevestigt locatieadres';customerHint.textContent=loc?.customers.length?`Gedeeld door: ${loc.customers.join(', ')}`:'Deze locatie wordt gebruikt door de bestaande werknemersroutes.';}
  choose.addEventListener('change',populate);const button=el('button','Locatieadres opslaan');form.append(button);form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;try{await save('location_address_save',{location:state.physical_locations.find(l=>l.key===choose.value)?.name,valid_from:inputs.valid_from.value,reason:inputs.reason.value,address:Object.fromEntries(['street','number','unit','postal_code','city','country'].map(k=>[k,inputs[k].value]))});message('Locatieadres opgeslagen. De oorspronkelijke klantkoppelingen en afstanden zijn behouden.');}catch(error){message(error.message,true);}finally{button.disabled=false;}});section.append(form,customerHint,el('p','Bij een adreswijziging kies je de werkelijke nieuwe ingangsdatum. Correcties op dezelfde datum bewaren ook de vorige versie.'));
  const search=el('input');search.placeholder='Zoek locatie of gekoppelde klant';search.setAttribute('aria-label','Zoek locatieadres');section.append(search);const scroll=el('div');scroll.className='scroll';const table=el('table'),thead=el('thead'),head=el('tr');for(const label of ['Locatie / klanten','Adres','Geldig vanaf',''])head.append(el('th',label));thead.append(head);const body=el('tbody');table.append(thead,body);scroll.append(table);section.append(scroll);
  head.insertBefore(el('th','Mapbox-coördinaten'),head.lastChild);
  renderLocationGeocoding(section);
  function draw(){body.replaceChildren();for(const loc of state.physical_locations){if(!`${loc.name} ${loc.customers.join(' ')}`.toLocaleLowerCase('nl').includes(search.value.toLocaleLowerCase('nl')))continue;const own=versions.filter(v=>v.location_key===loc.key),active=own.filter(v=>v.valid_from<=day).at(-1);for(const v of $('history').checked&&own.length?own:[active]){const tr=el('tr'),name=el('td',loc.name);if(loc.customers.length)name.append(el('p',loc.customers.join(', ')));const a=v?.address;tr.append(name,el('td',a?`${a.street} ${a.number}${a.unit?' bus '+a.unit:''}, ${a.postal_code} ${a.city} · ${a.country}`:'Adres ontbreekt'),el('td',v?.valid_from||'—'));const result=v?.geocode?.result,geo=el('td',geocodeLabel(v?.geocode_status||'NOT_REQUESTED'));if(result?.latitude!=null){geo.append(el('p',`${result.latitude}, ${result.longitude}`),el('p',result.label||''),el('p',`Nauwkeurigheid: ${result.accuracy||'?'} · match: ${result.confidence||'?'}`));}else if(result?.message)geo.append(el('p',result.message));tr.append(geo);const cell=el('td'),edit=el('button',own.length?'Adres aanpassen':'Adres toevoegen');edit.className='secondary';edit.addEventListener('click',()=>{choose.value=loc.key;populate();form.scrollIntoView({behavior:'smooth',block:'center'});inputs.street.focus();});cell.append(edit);tr.append(cell);body.append(tr);}}}
  search.addEventListener('input',draw);draw();compactAddressPanel(section,'Locatieadres toevoegen of aanpassen');
}
function renderDistanceRoutes(){
  let section=$('automaticRouteDistances');if(!section){section=el('section');section.id='automaticRouteDistances';$('routeView').prepend(section);}section.replaceChildren(el('h2','Vaste routeafstanden · Mapbox'),el('p','Alleen routes uit de geselecteerde export. Auto en fiets apart; thuis → werklocatie, enkele afstand. Zonder verkeersgegevens: kortste van de aangeboden routes. Opgeslagen kilometers worden nooit stil vernieuwd.'));
  const select=el('select'),runs=new Map();for(const r of state.matching_runs||[])if(!runs.has(r.month))runs.set(r.month,r);selector(select,[...runs.values()].map(r=>({id:r.id,name:`Exportverwerking via maand ${r.month}`})));select.value=String(distanceRunId||state.matching?.run_id||'');const load=el('button','Benodigde routes bekijken');load.disabled=distanceBatch.running||!select.value;select.addEventListener('change',()=>{load.disabled=distanceBatch.running||!select.value;});load.addEventListener('click',async()=>{load.disabled=true;try{const response=await fetch(`/api/routing/plan?run_id=${encodeURIComponent(select.value)}`),result=await response.json();if(!response.ok)throw Error(result.error||'Routeplan laden mislukt.');distanceRunId=Number(select.value);distancePlan=result;renderDistanceRoutes();}catch(error){message(error.message,true);}finally{load.disabled=false;}});section.append(select,load);
  if(!distancePlan)return;
  const exportButton=el('button','Excel exporteren · alle afstanden en shiften');exportButton.disabled=distanceBatch.running||bulkGeocoding.running;
  exportButton.addEventListener('click',async()=>{exportButton.disabled=true;try{const response=await fetch(`/api/routing/export?run_id=${distanceRunId}&csrf=${encodeURIComponent(state.csrf)}`);if(!response.ok){const error=await response.json();throw Error(error.error||'Export mislukt.');}const url=URL.createObjectURL(await response.blob()),link=el('a');link.href=url;link.download='werknemersafstanden-controle.xlsx';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Excel gedownload. Alle afstanden zijn naar boven afgerond; ontbrekende gegevens blijven zichtbaar.');}catch(error){message(error.message,true);}finally{exportButton.disabled=false;}});section.append(exportButton,el('p','Excel: alle opgeslagen Mapbox-afstanden en alle behouden shiften van deze export, over alle maanden. Afstanden in gehele enkele kilometers, altijd naar boven afgerond.'));
  const cache=new Map((state.route_distances||[]).map(r=>[r.cache_key,r]));for(const r of distancePlan.routes)r.cached=cache.get(r.cache_key)||r.cached;const missing=distancePlan.routes.filter(r=>!r.cached);
  section.append(el('p',`Maanden: ${distancePlan.months.join(', ')} · ${distancePlan.routes.length} unieke routes · ${missing.length} nieuwe aanvragen · ${distancePlan.blocked.length} beweging/vervoer-combinaties geblokkeerd · ${distancePlan.excluded} trein/dienstwagen-combinaties uitgesloten.`));
  const label=el('label'),consent=el('input');consent.type='checkbox';label.append(consent,document.createTextNode(' Ik bevestig verkregen toestemming voor routeaanvragen en blijvende opslag van afstanden.'));const start=el('button',`Ontbrekende afstanden opvragen (${missing.length})`),stop=el('button','Stop na huidige route'),progress=el('p',distanceBatch.text);progress.id='routeDistanceProgress';progress.setAttribute('aria-live','polite');start.disabled=distanceBatch.running||bulkGeocoding.running||!state.mapbox_configured||!missing.length;stop.disabled=!distanceBatch.running;stop.className='secondary';stop.addEventListener('click',()=>{distanceBatch.stop=true;stop.disabled=true;progress.textContent='Stop gevraagd; huidige aanvraag wordt nog opgeslagen.';});
  start.addEventListener('click',async()=>{if(distanceBatch.running||bulkGeocoding.running)return;if(!consent.checked){message('Bevestig eerst toestemming en permanente opslag.',true);return;}const queue=missing.map(r=>r.cache_key);Object.assign(distanceBatch,{running:true,stop:false,text:'Routeaanvragen gestart.'});renderDistanceRoutes();let completed=0;try{for(const key of queue){if(distanceBatch.stop)break;distanceBatch.text=`Route ${completed+1} van ${queue.length}…`;if($('routeDistanceProgress'))$('routeDistanceProgress').textContent=distanceBatch.text;await save('route_distance_request',{run_id:distanceRunId,cache_key:key,consent:true});completed++;const current=state.route_distances.find(r=>r.cache_key===key);if(current?.status!=='READY'){distanceBatch.stop=true;break;}await new Promise(resolve=>setTimeout(resolve,250));}distanceBatch.text=`${distanceBatch.stop?'Gestopt':'Klaar'}: ${completed} van ${queue.length} verwerkt. Bekijk de afstandstabel.`;message(distanceBatch.text);}catch(error){distanceBatch.text=`Routeaanvragen gestopt: ${error.message} Eerdere resultaten blijven bewaard; vernieuw eerst bij een onzekere netwerkuitkomst.`;message(distanceBatch.text,true);}finally{distanceBatch.running=false;renderDistanceRoutes();}});section.append(label,start,stop,progress);
  const workerRows=[];
  for(const route of distancePlan.routes){const seen=new Set();for(const c of route.contexts){const key=JSON.stringify([c.worker_id,c.location,c.mode,c.home_valid_from,c.location_valid_from]);if(seen.has(key))continue;seen.add(key);workerRows.push({worker_id:c.worker_id,name:c.worker,route,context:c,values:[c.location,c.mode,`${c.home_valid_from} / ${c.location_valid_from}`,route.cached?.kms??'—',route.cached?.message?`${route.cached.status}: ${route.cached.message}`:route.cached?.status||'NOG OPVRAGEN']});}}
  for(const row of workerRows){if(row.context.origin_location)row.values[0]=`${row.context.origin_location} → ${row.context.location} · tussenlocatie`;const correction=row.route.cached?.overrides?.find(c=>c.worker_id===row.worker_id)||row.route.cached?.transfer_override;if(correction){row.values[3]=String(correction.kms);row.values[4]=`HR-correctie: ${correction.reason} · Mapbox: ${row.route.cached.kms} km`;}}
  const search=el('input');search.type='search';search.placeholder='Zoek werknemer, locatie of vervoer';search.setAttribute('aria-label','Zoek werknemersafstanden');search.value=distanceWorkerSearch;
  const list=el('div');list.id='workerDistanceList';
  function updateList(){list.replaceChildren(workerDistanceGroups(workerRows,['Locatie','Vervoer','Adresversies vanaf','Enkele km','Status'],'mapbox',(cell,row)=>{if(row.route.cached?.status==='READY'){const button=el('button','Route bekijken');button.disabled=distanceBatch.running||bulkGeocoding.running;button.addEventListener('click',()=>openRoutePreview(row.route.cached.id,`${row.name} → ${row.context.location} · ${row.context.mode}`));cell.append(button);appendRouteCorrection(cell,row);}},distanceWorkerSearch));}
  search.addEventListener('input',()=>{distanceWorkerSearch=search.value;updateList();});updateList();section.append(el('h3','Werknemers · klik om alle locatieafstanden te zien'),search,list,el('p','Geen herhaling bij READY, ERROR of PENDING. Een onderbroken aanvraag blijft geblokkeerd voor handmatige opvolging. Nieuwe adrescombinaties krijgen een nieuwe route; oude afstanden blijven behouden. Dit vervangt nog niet de handmatige afstand in de vergoeding-engine.'));
  if(distancePlan.blocked.length){const details=el('details');details.append(el('summary',`Ontbrekende gegevens (${distancePlan.blocked.length})`));const groups=new Set();for(const b of distancePlan.blocked){const text=`${b.worker} · ${b.location} · ${b.reason}`;if(!groups.has(text)){groups.add(text);details.append(el('p',text));}}section.append(details);}
}
function appendRouteCorrection(cell,row){
  const saved=row.route.cached,active=saved.overrides?.find(c=>c.worker_id===row.worker_id),details=el('details');details.append(el('summary',active?'Correctie aanpassen':'Afstand corrigeren'));
  details.append(el('p',`Alleen ${row.name} · ${row.values[0]} · ${row.context.mode}. Mapbox blijft bewaard: ${saved.kms} km. De kaart toont de Mapbox-route, niet een handmatig gewijzigde route.`));
  const form=el('form'),km=el('input'),reason=el('input'),submit=el('button','Correctie opslaan');km.type='number';km.min='0';km.max='100000';km.step='1';km.required=true;km.value=active?.kms??saved.kms;km.setAttribute('aria-label','Gecorrigeerde enkele kilometers');reason.required=true;reason.maxLength=500;reason.placeholder='Reden voor correctie';reason.setAttribute('aria-label','Reden voor afstandscorrectie');submit.disabled=distanceBatch.running||bulkGeocoding.running;form.append(km,reason,submit);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;try{await save('route_distance_override',{route_id:saved.id,worker_id:row.worker_id,kms:km.value,reason:reason.value});}catch(error){message(error.message,true);submit.disabled=false;}});details.append(form);
  if(active){const reset=el('button','Mapbox-afstand herstellen');reset.type='button';reset.disabled=distanceBatch.running||bulkGeocoding.running;reset.addEventListener('click',async()=>{if(!reason.value.trim()){reason.reportValidity();return;}reset.disabled=true;try{await save('route_distance_override',{route_id:saved.id,worker_id:row.worker_id,reset:true,reason:reason.value});}catch(error){message(error.message,true);reset.disabled=false;}});details.append(reset);}
  const history=(saved.correction_history||[]).filter(c=>c.worker_id===row.worker_id);if(history.length){const log=el('details');log.append(el('summary','Correctiehistorie'));for(const c of [...history].reverse())log.append(el('p',`${c.changed_at}: ${c.kms==null?'Mapbox hersteld':c.kms+' km'} · ${c.reason}`));details.append(log);}cell.append(details);
}
async function openRoutePreview(id,title){
  try{
    let panel=$('routePreview');if(!panel){panel=el('section');panel.id='routePreview';$('routeView').prepend(panel);}panel.replaceChildren(el('h2',title),el('p','Routelijn laden…'));panel.scrollIntoView({behavior:'smooth'});
    const url=`/api/routing/preview?id=${id}&csrf=${encodeURIComponent(state.csrf)}`;
    const response=await fetch(url),item=await response.json();if(!response.ok)throw Error(item.error||'Route laden mislukt.');panel.replaceChildren(el('h2',title));
    const close=el('button','Sluiten');close.addEventListener('click',()=>panel.remove());panel.append(close);
    if(item.status==='MISSING'){
      panel.append(el('p','Deze bestaande afstand heeft nog geen routelijn. Eén aanvullende Directions-aanvraag haalt de huidige route op; je oude kilometers blijven behouden.'));
      const request=el('button','Routelijn éénmalig opvragen');request.disabled=!state.mapbox_configured;
      request.addEventListener('click',async()=>{request.disabled=true;try{await save('route_visualization_request',{route_id:id,consent:true});await openRoutePreview(id,title);}catch(error){message(error.message,true);request.disabled=false;}});panel.append(request);return;
    }
    if(item.status!=='READY'){panel.append(el('p',`${item.status}: ${item.message||'Aanvraag nog niet afgerond. Geen automatische herhaling.'}`));return;}
    panel.append(el('p',`Opgeslagen afstand: ${item.original_kms} km · Controlekaart: ${item.kms} km.`));
    if(Number(item.original_kms)!==Number(item.kms))panel.append(el('p','Let op: deze nieuw opgevraagde route verschilt van de oorspronkelijke afstand. De oorspronkelijke kilometers zijn niet gewijzigd.'));
    panel.append(el('p','Groen = vertrekpunt, rood = bestemming. De routelijn blijft opgeslagen. Elke kaartweergave vraagt een Mapbox-kaartafbeelding op (geen nieuwe Directions-aanvraag).'));
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 900 600');svg.setAttribute('class','route-map');svg.setAttribute('role','img');svg.setAttribute('aria-label',title);
    const image=document.createElementNS(ns,'image');image.setAttribute('href',`/api/routing/map-background?id=${id}&csrf=${encodeURIComponent(state.csrf)}`);image.setAttribute('width','900');image.setAttribute('height','600');image.addEventListener('error',()=>message('Kaartachtergrond kon niet laden; de opgeslagen routelijn blijft zichtbaar.',true));svg.append(image);
    const line=document.createElementNS(ns,'polyline');line.setAttribute('points',item.points.map(p=>p.join(',')).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#2254d5');line.setAttribute('stroke-width','4');svg.append(line);
    for(const [point,color] of [[item.points[0],'#138636'],[item.points.at(-1),'#ce2424']]){const marker=document.createElementNS(ns,'circle');marker.setAttribute('cx',point[0]);marker.setAttribute('cy',point[1]);marker.setAttribute('r','7');marker.setAttribute('fill',color);marker.setAttribute('stroke','white');marker.setAttribute('stroke-width','2');svg.append(marker);}panel.append(svg);
  }catch(error){message(error.message,true);}
}
function renderAddresses(){
  let section=$('addressProfiles');
  if(!section){section=el('section');section.id='addressProfiles';$('addressesView').append(section);}
  section.replaceChildren(el('h2','Woonadressen'),el('p','Opgeslagen woonadressen en coördinaten per werknemer. Adreswijzigingen bewaren de eerdere versies.'));
  const form=el('form'),choose=el('select');choose.required=true;choose.name='worker_id';selector(choose,state.workers);form.append(el('label','Werknemer'),choose);
  const inputs={};
  for(const [key,label] of [['valid_from','Geldig vanaf'],['street','Straat'],['number','Huisnummer'],['unit','Bus'],['postal_code','Postcode'],['city','Gemeente'],['country','Landcode (BE, NL, …)'],['reason','Reden']]){
    const wrapper=el('label',label),input=el('input');input.name=key;input.required=key!=='unit';input.type=key==='valid_from'?'date':'text';if(key==='country')input.maxLength=2;inputs[key]=input;wrapper.append(input);form.append(wrapper);
  }
  inputs.valid_from.value='2026-01-01';
  choose.addEventListener('change',()=>{const active=(state.addresses||[]).filter(a=>a.worker_id===Number(choose.value)).at(-1);for(const field of ['street','number','unit','postal_code','city','country'])inputs[field].value=active?.address[field]||'';inputs.valid_from.value=active?.valid_from||'2026-01-01';inputs.reason.value='';});
  const button=el('button','Adres opslaan');form.append(button);form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;try{await save('address_save',{worker_id:Number(choose.value),valid_from:inputs.valid_from.value,reason:inputs.reason.value,address:Object.fromEntries(['street','number','unit','postal_code','city','country'].map(k=>[k,inputs[k].value]))});}catch(error){message(error.message,true);}finally{button.disabled=false;}});section.append(form);
  section.append(el('h3','Mapbox · één adres testen'),el('p',state.mapbox_configured?'Lokale token ingesteld. De token wordt niet naar de browser verstuurd.':'Token ontbreekt. Voer zelf .venv/bin/python scripts/setup_mapbox.py uit in de projectterminal.'));
  const geoSelect=el('select'),geoPanel=el('div'),latestAddresses=new Map();for(const a of state.addresses||[])if(a.valid_from<=currentDay)latestAddresses.set(a.worker_id,a);selector(geoSelect,[...latestAddresses.values()].map(a=>({id:a.id,name:`${worker(a.worker_id)} · ${a.valid_from} · ${geocodeLabel(a.geocode_status)}`})));section.append(geoSelect,geoPanel);
  renderBulkGeocoding(section);
  geoSelect.addEventListener('change',()=>{
    geoPanel.replaceChildren();const a=(state.addresses||[]).find(a=>a.id===Number(geoSelect.value));if(!a)return;
    geoPanel.append(el('p',`${a.address.street} ${a.address.number}, ${a.address.postal_code} ${a.address.city} · ${a.address.country||'Land ontbreekt'}`));
    if(!a.geocode){const label=el('label'),consent=el('input');consent.type='checkbox';label.append(consent,document.createTextNode(' Ik mag dit adres naar Mapbox sturen en bevestig permanente, mogelijk betaalde geocodering (accountvoorwaarden en privacy gecontroleerd).'));const request=el('button','Coördinaten voor dit adres opvragen');request.disabled=!state.mapbox_configured||a.address.country!=='BE';request.addEventListener('click',async()=>{if(!consent.checked){message('Bevestig eerst verzending en permanente geocodering.',true);return;}request.disabled=true;message('Eén adres wordt opgevraagd…');try{await save('address_geocode',{address_id:a.id,consent:true});message('Aanvraag opgeslagen. Selecteer het adres opnieuw om het resultaat te bekijken.');}catch(error){message(error.message,true);}finally{request.disabled=false;}});geoPanel.append(label,request);return;}
    const g=a.geocode,r=g.result;geoPanel.append(el('p',`${geocodeLabel(g.status)} · ${r.message||''}`));if(r.label)geoPanel.append(el('p',`Gevonden adres: ${r.label}`));if(r.latitude!=null)geoPanel.append(el('p',`Breedtegraad ${r.latitude} · lengtegraad ${r.longitude} · nauwkeurigheid ${r.accuracy||'onbekend'} · match ${r.confidence||'onbekend'}`));
    if(g.status==='REVIEW'){
      const form=el('form'),reason=el('input'),check=el('input'),label=el('label');reason.required=true;reason.maxLength=250;reason.placeholder='Reden van bevestiging of afwijzing';reason.setAttribute('aria-label','Reden adrescontrole');check.type='checkbox';label.append(check,document.createTextNode(' Ik heb het gevonden adres én de coördinaten gecontroleerd. Bij een onzekere match neem ik deze expliciet over.'));
      const accept=el('button','Adres bevestigen'),reject=el('button','Adres afwijzen');reject.type='button';form.append(reason,label,accept,reject);form.addEventListener('submit',async event=>{event.preventDefault();if(!check.checked){message('Controleer en bevestig eerst het adres en de coördinaten.',true);return;}try{await save('geocode_review',{address_id:a.id,accept:true,reason:reason.value,confirm_uncertain:!r.eligible});}catch(error){message(error.message,true);}});reject.addEventListener('click',async()=>{if(!form.reportValidity())return;try{await save('geocode_review',{address_id:a.id,accept:false,reason:reason.value});}catch(error){message(error.message,true);}});geoPanel.append(form);
    }
    if(['ERROR','NO_MATCH','REJECTED'].includes(g.status))geoPanel.append(el('p','Geen automatische herhaling. Controleer eerst adres/token/account. Een gewijzigd adres krijgt een nieuwe aanvraag; voor dezelfde aanvraag is herhalen in deze eerste versie bewust niet beschikbaar.'));
  });
  const table=el('table'),head=el('tr');for(const text of ['Werknemer','Adres','Geldig vanaf','Coördinaten'])head.append(el('th',text));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
  for(const w of state.workers){const versions=(state.addresses||[]).filter(a=>a.worker_id===w.id),active=versions.filter(a=>a.valid_from<=($('asof').value||currentDay)).at(-1);for(const v of $('history').checked&&versions.length?versions:[active]){const tr=el('tr'),a=v?.address;for(const value of [w.name,a?`${a.street} ${a.number}${a.unit?' bus '+a.unit:''}, ${a.postal_code} ${a.city} · ${a.country||'land ontbreekt'}`:'Adres ontbreekt',v?.valid_from||'—',geocodeLabel(v?.geocode_status||'NOT_REQUESTED')])tr.append(el('td',value));body.append(tr);}}table.append(body);section.append(table);
  const pending=(state.address_candidates||[]).filter(c=>c.status==='REVIEW');section.append(el('h3',`Adresbronregels ter controle (${pending.length})`));
  for(const c of pending){const block=el('div'),a=c.address;block.append(el('p',`Bronrij ${c.source_row}: ${c.name} — ${a.street} ${a.number}, ${a.postal_code} ${a.city}`));const select=el('select');selector(select,state.workers);select.value=String(c.worker_id||'');const reason=el('input');reason.placeholder='Reden van koppeling of negeren';reason.setAttribute('aria-label','Reden');block.append(select,reason);for(const [action,label] of [['address_link','Koppelen'],['address_ignore','Negeren']]){const b=el('button',label);b.type='button';b.className='secondary';b.addEventListener('click',async()=>{b.disabled=true;try{await save(action,{candidate_id:c.id,worker_id:Number(select.value),reason:reason.value});}catch(error){message(error.message,true);}finally{b.disabled=false;}});block.append(b);}section.append(block);}compactAddressPanel(section,'Woonadres toevoegen of aanpassen');
}
function compactAddressPanel(section,title){
  const form=section.querySelector(':scope > form');if(!form)return;
  const editor=el('details');editor.dataset.addressEditor='true';editor.className='addressTools';editor.append(el('summary',title));form.before(editor);editor.append(form);
  const table=section.querySelector(':scope > table, :scope > .scroll');if(table)editor.before(table);
  const children=[...section.children],geoIndex=children.findIndex(n=>n.tagName==='H3'&&n.textContent.startsWith('Mapbox'));
  if(geoIndex>=0){const nodes=children.slice(geoIndex);const stopIndex=nodes.findIndex(n=>n===table||n.tagName==='TABLE'||n.classList.contains('scroll')||(n.tagName==='H3'&&n.textContent.startsWith('Adresbronregels')));const tools=el('details');tools.className='addressTools';tools.open=bulkGeocoding.running;tools.append(el('summary','Mapbox-aanvragen en resultaten'));children[geoIndex].before(tools);for(const n of stopIndex<0?nodes:nodes.slice(0,stopIndex))tools.append(n);}
  section.onclick=event=>{if(event.target.closest('button')&&/Adres aanpassen|Adres toevoegen|Bronadres aanpassen/.test(event.target.textContent))editor.open=true;};
  for(const button of section.querySelectorAll('button'))if(/Adres aanpassen|Adres toevoegen|Bronadres aanpassen/.test(button.textContent))button.addEventListener('click',()=>{editor.open=true;form.scrollIntoView({behavior:'smooth',block:'center'});});
}
function renderLocationGeocoding(section){
  const plan=state.location_geocoding_plan;if(!plan)return;section.append(el('h3','Mapbox · locatiecoördinaten opvragen'),el('p',`${plan.requests} nieuwe unieke adresaanvragen · ${plan.missing_addresses} locaties zonder huidig adres overgeslagen · ${plan.unsupported_country} locaties buiten België overgeslagen. Opgeslagen resultaten worden hergebruikt.`));
  const label=el('label'),consent=el('input');consent.type='checkbox';label.append(consent,document.createTextNode(' Ik bevestig verzending van de ingevulde locatieadressen naar Mapbox en permanente, mogelijk betaalde geocodering.'));const start=el('button',`Locatiecoördinaten opvragen (${plan.requests})`),stop=el('button','Stop na huidige locatie'),progress=el('p',bulkGeocoding.text);progress.id='locationGeocodingProgress';progress.setAttribute('aria-live','polite');start.disabled=bulkGeocoding.running||!state.mapbox_configured||!plan.requests;stop.disabled=!bulkGeocoding.running;stop.className='secondary';stop.addEventListener('click',()=>{bulkGeocoding.stop=true;stop.disabled=true;progress.textContent='Stop gevraagd; de lopende aanvraag wordt nog opgeslagen.';});
  start.addEventListener('click',async()=>{if(bulkGeocoding.running)return;if(!consent.checked){message('Bevestig eerst permanente geocodering van de locatieadressen.',true);return;}const ids=[...plan.address_ids];Object.assign(bulkGeocoding,{running:true,stop:false,completed:0,total:ids.length,text:'Locatiegeocodering gestart.'});renderLocationAddresses();renderAddresses();try{for(const id of ids){if(bulkGeocoding.stop)break;bulkGeocoding.text=`Locatieaanvraag ${bulkGeocoding.completed+1} van ${ids.length}…`;if($('locationGeocodingProgress'))$('locationGeocodingProgress').textContent=bulkGeocoding.text;await save('location_geocode',{address_id:id,consent:true});bulkGeocoding.completed++;if(state.location_addresses.find(a=>a.id===id)?.geocode_status==='ERROR'){bulkGeocoding.stop=true;break;}}bulkGeocoding.text=`${bulkGeocoding.stop?'Gestopt':'Klaar'}: ${bulkGeocoding.completed} van ${ids.length} verwerkt. Bekijk gevonden adres en coördinaten in de locatietabel.`;message(bulkGeocoding.text);}catch(error){bulkGeocoding.text=`Locatiegeocodering gestopt: ${error.message} Eerdere resultaten blijven opgeslagen.`;message(bulkGeocoding.text,true);}finally{bulkGeocoding.running=false;renderLocationAddresses();renderAddresses();}});
  section.append(label,start,stop,progress,el('p','Laat de pagina open. Elke aanvraag wordt apart opgeslagen. Geen automatische retries of bevestiging; dit berekent nog geen routekilometers. Bij een grote site moet het punt ook bij de juiste toegang passen.'));
}
function geocodeLabel(status){return {NOT_REQUESTED:'Nog niet aangevraagd',REVIEW:'Resultaat nakijken',CONFIRMED:'Coördinaten bevestigd',REJECTED:'Resultaat afgewezen',NO_MATCH:'Geen adres gevonden',ERROR:'Aanvraag mislukt'}[status]||status;}
function renderBulkGeocoding(section){
  const plan=state.geocoding_bulk_plan;
  section.append(el('h3','Alle ontbrekende coördinaten opvragen'));
  if(!plan){section.append(el('p','Herstart de server om bulkgeocodering te gebruiken.'));return;}
  section.append(el('p',`${plan.requests} nieuwe unieke adresaanvragen · ${plan.existing_profiles} profielen met bestaand resultaat overgeslagen · ${plan.blocked_profiles} profielen zonder BE overgeslagen. Alleen huidige adressen, geen historische of toekomstige versies. Permanente geocodering kan kosten veroorzaken volgens je Mapbox-account.`));
  const label=el('label'),consent=el('input');consent.type='checkbox';label.append(consent,document.createTextNode(' Ik bevestig verzending van deze adressen naar Mapbox, privacybevoegdheid en permanente, mogelijk betaalde geocodering.'));const start=el('button',`Alles opvragen (${plan.requests} aanvragen)`),stop=el('button','Stop na huidig adres'),progress=el('p',bulkGeocoding.text);progress.id='bulkGeocodingProgress';progress.setAttribute('aria-live','polite');start.disabled=bulkGeocoding.running||!state.mapbox_configured||!plan.requests;stop.disabled=!bulkGeocoding.running;stop.className='secondary';
  stop.addEventListener('click',()=>{bulkGeocoding.stop=true;bulkGeocoding.text='Stop gevraagd; de lopende aanvraag wordt nog opgeslagen.';progress.textContent=bulkGeocoding.text;stop.disabled=true;});
  start.addEventListener('click',async()=>{
    if(bulkGeocoding.running)return;if(!consent.checked){message('Bevestig eerst de bulkverzending en permanente geocodering.',true);return;}
    const queue=[...plan.address_ids];Object.assign(bulkGeocoding,{running:true,stop:false,completed:0,total:queue.length,text:'Bulkverwerking gestart.'});renderAddresses();
    try{
      for(const addressId of queue){
        if(bulkGeocoding.stop)break;
        bulkGeocoding.text=`Aanvraag ${bulkGeocoding.completed+1} van ${bulkGeocoding.total} wordt verwerkt…`;if($('bulkGeocodingProgress'))$('bulkGeocodingProgress').textContent=bulkGeocoding.text;
        await save('address_geocode_bulk_item',{address_id:addressId,consent:true});bulkGeocoding.completed++;
        const status=state.addresses.find(a=>a.id===addressId)?.geocode_status;
        if(status==='ERROR'){bulkGeocoding.stop=true;bulkGeocoding.text=`Gestopt bij een API-fout na ${bulkGeocoding.completed} van ${bulkGeocoding.total}. Controleer het resultaat voordat je doorgaat.`;break;}
      }
      if(!bulkGeocoding.text.startsWith('Gestopt bij'))bulkGeocoding.text=`${bulkGeocoding.stop?'Gestopt':'Klaar'}: ${bulkGeocoding.completed} van ${bulkGeocoding.total} verwerkt. Opgeslagen resultaten blijven bewaard; controleer de adresmatches.`;
      message(bulkGeocoding.text);
    }catch(error){bulkGeocoding.text=`Bulk gestopt: ${error.message} Eerdere resultaten blijven opgeslagen. Bij onzekere netwerkuitkomst eerst vernieuwen, niet blind herhalen.`;message(bulkGeocoding.text,true);}
    finally{bulkGeocoding.running=false;renderAddresses();}
  });section.append(label,start,stop,progress,el('p','Laat deze pagina open tijdens de verwerking. Stoppen of afsluiten bewaart eerdere resultaten. Later opnieuw starten verwerkt alleen adressen zonder opgeslagen aanvraag, nooit automatische retries of automatische bevestiging.'));
}
function bind(id,action,data,onSaved=()=>{}){$(id).addEventListener('submit',async event=>{event.preventDefault();const button=$(id).querySelector('button');button.disabled=true;try{await save(typeof action==='function'?action():action,data());onSaved();}catch(error){message(error.message,true);}finally{button.disabled=false;}});}
bind('routeForm',()=>editing?'route_update':'route_add',()=>({...Object.fromEntries(new FormData($('routeForm'))),...(editing?{route_id:editing}:{})}),()=>{$('editor').hidden=true;editing=null;});
bind('rename','worker_rename',()=>({...Object.fromEntries(new FormData($('rename'))),worker_id:Number($('renameWorker').value)}));
bind('move','worker_move',()=>({...Object.fromEntries(new FormData($('move'))),worker_id:Number($('movingWorker').value),updates:[...$('moveRows').querySelectorAll('input')].map(input=>({route_id:Number(input.dataset.route),kms:input.value}))}));
$('add').addEventListener('click',()=>openEditor());$('cancel').addEventListener('click',()=>{$('editor').hidden=true;editing=null;});$('refresh').addEventListener('click',()=>refresh().catch(e=>message(e.message,true)));$('movingWorker').addEventListener('change',renderMove);
for(const id of ['search','asof','history'])$(id).addEventListener(id==='search'?'input':'change',()=>{if(state){renderRows();if(id!=='search'){renderAddresses();renderLocationAddresses();showView(activeView);}}});$('asof').value=currentDay;refresh().catch(e=>message(e.message,true));

function selectItems(id,items,value=''){const select=$(id);select.replaceChildren();for(const [v,text] of items){const option=el('option',text);option.value=v;select.append(option);}select.value=String(value);}
function renderMatching(){
  const selectedAgent=$('matchingAgent').value;
  if(!Array.isArray(state.matching_runs)){$('matchingSummary').textContent='De server draait nog oude code. Stop met Ctrl+C, start scripts/manage_transport.py opnieuw en herlaad deze pagina.';$('agentShifts').replaceChildren();return;}
  renderShiftHistory();
  const runs=new Map();for(const run of state.matching_runs||[])if(matching&&run.source_sha256===matching.source_sha256&&!runs.has(run.month))runs.set(run.month,run);
  selectItems('matchingMonth',[...runs.values()].map(r=>[r.id,r.month]),matching?.run_id||'');
  $('matchingRefresh').disabled=!matching;
  for(const id of ['employeeMatch','locationMatch'])for(const control of $(id).querySelectorAll('input,select,button'))control.disabled=!matching;
  if(!matching){$('matchingSummary').textContent='Geen export geopend. Upload een Pl@net-export of vraag hieronder bewust een eerdere maand op.';$('agentShifts').replaceChildren();$('matchingWarning').hidden=true;$('calculationSummary').textContent='';$('calculationWarning').textContent='';for(const id of ['matchingAgent','sourceAgent','sourceCustomer'])$(id).replaceChildren();$('employeeSuggestions').textContent='';return;}
  const summary=matching.summary;$('matchingSummary').textContent=`${matching.month} · ${summary.agents} agenten · ${summary.movements} behouden bewegingen · ${summary.source_shifts} onderliggende shiften · ${Object.entries(summary.statuses).map(([s,n])=>`${s}: ${n}`).join(' · ')}`;
  $('calculationSummary').textContent=matching.calculation?`Fase 5 · ${Object.entries(matching.calculation.statuses).map(([s,n])=>`${calculationLabel(s)}: ${n}`).join(' · ')}`:'Vernieuw dit oudere overzicht om fase 5 te berekenen.';
  $('calculationWarning').textContent=matching.calculation?.warning||'Nog geen berekening.';
  $('matchingWarning').hidden=!matching.stale;$('matchingWarning').textContent='Instellingen zijn gewijzigd sinds deze verwerking. Klik op Vernieuwen om het volledige bronbestand opnieuw te verwerken.';
  selectItems('matchingAgent',[['','Alle agenten'],...matching.agents.map(a=>[a.planet_id,`${a.planet_id} — ${a.worker_name||a.source_names.join(' / ')}`])],matching.agents.some(a=>a.planet_id===selectedAgent)?selectedAgent:'');
  selectItems('sourceAgent',[['','— Kies —'],...matching.agents.map(a=>[a.planet_id,`${a.planet_id} — ${a.source_names.join(' / ')} (${a.status})`])],'');
  selectItems('targetWorker',[['','— Kies —'],...state.workers.map(w=>[w.id,w.name])],'');
  selectItems('sourceCustomer',[['','— Kies —'],...matching.locations.map(l=>[l.customer,`${l.customer} (${l.status})`])],'');
  selectItems('targetLocation',[['','— Kies —'],...[...new Set(state.routes.map(r=>r.location))].sort().map(l=>[l,l])],'');
  $('employeeSuggestions').textContent='';renderAgentShifts();
}
function renderAgentShifts(){
  $('agentShifts').replaceChildren();if(!matching)return;
  const selected=$('matchingAgent').value;
  for(const agent of [...matching.agents].sort((a,b)=>(a.worker_name||a.source_names[0]).localeCompare(b.worker_name||b.source_names[0],'nl'))){
    if(selected&&selected!==agent.planet_id)continue;
    const calculations=new Map((matching.calculation?.rows||[]).map(r=>[r.movement_id,r]));
    const filter=$('calculationFilter').value;
    const shifts=matching.movements.filter(m=>m.planet_id===agent.planet_id&&(filter==='all'||filter==='MULTI_LOCATION'&&m.multi_location||calculations.get(m.id)?.status===filter));if(!shifts.length)continue;const details=el('details');details.className='agentGroup';details.open=!!selected;
    details.append(el('summary',`${agent.planet_id} — ${agent.worker_name||agent.source_names.join(' / ')} · ${shifts.length} getoonde bewegingen · koppeling: ${shifts.filter(m=>m.status!=='MATCHED').length} na te kijken · berekening: ${shifts.filter(m=>calculations.get(m.id)?.status==='BLOCKED').length} na te kijken · ${shifts.filter(m=>calculations.get(m.id)?.status==='LATER_PHASE').length} nog niet in deze fase`));
    const selectedDays=new Set(shifts.filter(m=>m.multi_location).map(m=>m.day));
    const completeShifts=matching.movements.filter(m=>m.planet_id===agent.planet_id&&(shifts.includes(m)||m.multi_location&&selectedDays.has(m.day)));
    for(const [location,movements] of shiftDisplayGroups(completeShifts,calculations)){
      details.append(el('h3',`${location} · ${movements.length} bewegingen`));const wrap=el('div');wrap.className='scroll';const table=el('table');
      const head=el('thead'),hr=el('tr');for(const label of ['Datum','Bronklant(en)','Diensturen (alle bronshiften)','Routes beschikbaar','Koppeling','Auto · controlebedrag','Berekeningscontrole'])hr.append(el('th',label));head.append(hr);table.append(head);const body=el('tbody');
      for(const m of movements){
        const c=calculations.get(m.id);
        if(m.multi_location&&c?.origin_location){const transfer=el('tr');transfer.className='transfer-row';const cell=el('td');cell.colSpan=7;const km=c.travel_kms??c.distance;cell.append(el('strong',`Verplaatsing: ${c.origin_location} → ${m.location||m.source_location}`),el('span',` · ${c.selected_mode||m.routes[0]?.mode||'Vervoer niet ingesteld'} · ${km!=null?km+' km (enkele afstand)':'afstand nog op te vragen'}${c.distance_source?' · '+c.distance_source:''} · standaardtarief`));transfer.append(cell);body.append(transfer);}
        const tr=el('tr');const customers=el('td');if(m.multi_location)customers.append(el('strong',m.location||m.source_location));customers.append(el('div',[...new Set(m.source_shifts.map(s=>s.customer))].join(', ')));tr.append(el('td',m.day),customers);
        const times=el('td');for(const s of m.source_shifts)times.append(el('div',`${s.start}–${s.end}${s.end_day_offset===1?' (+1 dag)':''} · bronrij ${s.row}`));tr.append(times);
        tr.append(el('td',m.routes.length?m.routes.map(r=>`${r.mode}: ${kmText(r,r.kms)}`).join(' / '):'Geen geldige route op datum'),el('td',m.status));
        const amount=el('td',c?.amount!=null?`€ ${c.amount}`:c?.status==='EXCLUDED_TRAIN'?'n.v.t.':'—');amount.className=c?.status==='CALCULATED'?'calculated':'pending';tr.append(amount);
        tr.append(compactCalculationTrace(c));body.append(tr);
      }
      table.append(body);wrap.append(table);details.append(wrap);
    }
    $('agentShifts').append(details);
  }
}
bind('employeeMatch','matching_employee',()=>({...Object.fromEntries(new FormData($('employeeMatch'))),worker_id:Number($('targetWorker').value),run_id:matching?.run_id}));
bind('locationMatch','matching_location',()=>({...Object.fromEntries(new FormData($('locationMatch'))),run_id:matching?.run_id}));
$('sourceAgent').addEventListener('change',()=>{const agent=matching?.agents.find(a=>a.planet_id===$('sourceAgent').value);$('employeeSuggestions').textContent=agent?`Bronnaam: ${agent.source_names.join(' / ')}. Suggesties (zelf bevestigen): ${agent.suggestions.map(s=>s.name).join(', ')||'geen'}`:'';});
$('matchingAgent').addEventListener('change',renderAgentShifts);
$('matchingMonth').addEventListener('change',async()=>{try{const response=await fetch(`/api/matching/run?id=${encodeURIComponent($('matchingMonth').value)}`);if(!response.ok)throw Error('Maand laden mislukt.');matching=await response.json();renderMatching();renderRouteIssues();}catch(error){message(error.message,true);}});
$('matchingRefresh').addEventListener('click',async()=>{const button=$('matchingRefresh');button.disabled=true;button.textContent='Bezig…';message('Het volledige bronbestand wordt opnieuw verwerkt…');try{await save('matching_refresh',{run_id:matching?.run_id});message('Volledig bronbestand opnieuw verwerkt. Kies een maand om de resultaten te bekijken.');}catch(error){message(error.message,true);}finally{button.disabled=!matching;button.textContent='Vernieuwen';}});
function tab(shifts,settings=false){showView(settings?'settings':shifts?'shifts':'routes');}
function initializeNavigation(){
  for(const [view,title] of [['addresses','Woonadressen'],['locations','Werklocaties'],['settings','Instellingen']]){const button=el('button',title);button.id=`tab${view[0].toUpperCase()+view.slice(1)}`;button.className='secondary';button.addEventListener('click',()=>showView(view));document.querySelector('nav').append(button);if(view!=='settings'){const container=el('div');container.id=`${view}View`;container.hidden=true;$('routeView').before(container);const controls=el('div');controls.className='toolbar viewControls';for(const [id,labelText] of [['asof','Situatie op datum'],['history','Historiek tonen']]){const label=el('label',labelText),input=el('input');input.type=id==='asof'?'date':'checkbox';input.dataset.sharedControl=id;input.value=$(id).value;input.checked=$(id).checked;input.addEventListener('change',()=>{$(id).value=input.value;$(id).checked=input.checked;$(id).dispatchEvent(new Event('change'));});label.append(input);controls.append(label);}container.append(controls);}}
  $('shiftView').prepend($('monthlyImport'));
  $('tabRoutes').textContent='Werknemersroutes';document.querySelector('nav').setAttribute('aria-label','Dashboardonderdelen');
  try{const saved=sessionStorage.getItem('hr-active-view');if(['routes','addresses','locations','shifts','settings'].includes(saved))activeView=saved;}catch{}
  showView(activeView);
}
function showView(view){
  activeView=view;const panels={routes:'routeView',addresses:'addressesView',locations:'locationsView',shifts:'shiftView',settings:'tariffSettings'};
  for(const [key,id] of Object.entries(panels)){$(id).hidden=key!==view;const button=$(key==='routes'?'tabRoutes':key==='shifts'?'tabShifts':`tab${key[0].toUpperCase()+key.slice(1)}`);button.className=key===view?'':'secondary';button.setAttribute('aria-current',key===view?'page':'false');}
  $('monthlyImport').hidden=view!=='shifts';
  for(const input of document.querySelectorAll('[data-shared-control]')){const original=$(input.dataset.sharedControl);input.value=original.value;input.checked=original.checked;}
  const labels={routes:['Werknemers en vervoersroutes','Afstanden per werknemer, locatie en vervoerswijze.'],addresses:['Woonadressen','Opgeslagen agentadressen en coördinaten.'],locations:['Werklocaties','Fysieke locaties, gekoppelde klanten en locatieadressen.'],shifts:['Maandshiften en berekeningen','Upload een export, kies een maand en bekijk de resultaten.'],settings:['Instellingen en tarieven','Gedateerde tarieven met bewaarde eerdere versies.']};
  document.querySelector('header .eyebrow').textContent='HR · Vervoerskosten';document.querySelector('header h1').textContent=labels[view][0];document.querySelector('header p').textContent=labels[view][1];
  try{sessionStorage.setItem('hr-active-view',view);}catch{}
}
$('tabRoutes').addEventListener('click',()=>tab(false));$('tabShifts').addEventListener('click',()=>tab(true));
$('routeForm').elements.mode.addEventListener('input',distanceInput);

function renderAutomaticRoutes(){
  let section=$('automaticRouteSettings');if(!section){section=el('section');section.id='automaticRouteSettings';$('tariffSettings').prepend(section);}
  const auto=state.automatic_routes||{},label=el('label'),input=el('input');input.type='checkbox';input.checked=!!auto.enabled;label.append(input,document.createTextNode(' Automatisch coördinaten en ontbrekende routes opvragen en blijvend bewaren.'));
  input.addEventListener('change',async()=>{input.disabled=true;try{await save('automatic_settings',{enabled:input.checked,consent:input.checked});}catch(error){message(error.message,true);input.disabled=false;}});
  const status=`Automatische afstanden: ${auto.enabled?'aan':'uit'} · ${auto.status||'IDLE'} · ${auto.report?.geocoded||0} adressen · ${auto.report?.routes||0} nieuwe routes${auto.report?.attention_results?' · '+auto.report.attention_results+' resultaten ter controle':''}${auto.report?.message?' · '+auto.report.message:''}`;
  const button=el('button','Ontbrekende routes nu automatisch verwerken');button.disabled=!auto.enabled||['RUNNING','QUEUED'].includes(auto.status);button.addEventListener('click',async()=>{button.disabled=true;try{await save('automatic_process',{});}catch(error){message(error.message,true);button.disabled=false;}});
  section.replaceChildren(el('h2','Automatische adres- en routeverwerking'),label,el('p',status),el('p','Na uploaden of toevoegen/wijzigen van adressen en routes. Alleen zekere adresmatches worden automatisch bevestigd; geen heraanvragen bij ERROR/PENDING. Een nieuw adres en vervoerswijze blijven vereist.'),button);
  let progress=$('automaticRouteStatus');if(!progress){progress=el('p');progress.id='automaticRouteStatus';progress.setAttribute('aria-live','polite');$('routeView').prepend(progress);}progress.textContent=status;
  if(automaticPoll)clearTimeout(automaticPoll);
  if(['RUNNING','QUEUED'].includes(auto.status))automaticPoll=setTimeout(async()=>{try{if(document.activeElement?.closest('form')){renderAutomaticRoutes();return;}await refresh();}catch(error){message(error.message,true);}},2500);
}
function renderTransferOverview(){
  let section=$('locationTransferOverview');if(!section){section=el('section');section.id='locationTransferOverview';$('locationsView').append(section);}section.replaceChildren(el('h2','Afstanden tussen werklocaties'),el('p','Gerichte trajecten, auto en fiets apart. Een correctie hier geldt voor dit traject bij alle werknemers; persoonlijke correcties blijven voorgaan. Oude Mapbox-afstanden en historie blijven bewaard.'));
  const table=el('table'),head=el('thead'),hr=el('tr');for(const text of ['Van','Naar','Vervoer','Enkele km','Status','Controle / correctie'])hr.append(el('th',text));head.append(hr);const body=el('tbody');
  for(const item of state.location_transfers||[]){const c=item.contexts[0],saved=item.cached,shared=saved?.transfer_override,tr=el('tr');for(const value of [c.origin_location,c.location,c.mode,shared?.kms??saved?.kms??'—',shared?'HR-correctie':saved?.status||'AUTOMATISCH OP TE VRAGEN'])tr.append(el('td',value));const cell=el('td');
    if(saved?.status==='READY'){
      const view=el('button','Route bekijken');view.addEventListener('click',()=>{showView('routes');openRoutePreview(saved.id,`${c.origin_location} → ${c.location} · ${c.mode}`);});cell.append(view);
      const details=el('details');details.append(el('summary','Afstand corrigeren'),el('p',`Mapbox: ${saved.kms} km${shared?' · HR: '+shared.reason:''}`));const form=el('form'),km=el('input'),reason=el('input');km.type='number';km.min='0';km.max='100000';km.step='1';km.required=true;km.value=shared?.kms??saved.kms;km.setAttribute('aria-label','Gecorrigeerde tussenlocatieafstand');reason.required=true;reason.maxLength=500;reason.placeholder='Reden';reason.setAttribute('aria-label','Reden tussenlocatiecorrectie');form.append(km,reason,el('button','Correctie opslaan'));form.addEventListener('submit',async event=>{event.preventDefault();try{await save('location_transfer_override',{route_id:saved.id,kms:km.value,reason:reason.value});}catch(error){message(error.message,true);}});details.append(form);
      if(shared){const reset=el('button','Mapbox herstellen');reset.type='button';reset.addEventListener('click',async()=>{if(!reason.value.trim()){reason.reportValidity();return;}try{await save('location_transfer_override',{route_id:saved.id,reset:true,reason:reason.value});}catch(error){message(error.message,true);}});details.append(reset);}
      for(const old of [...(saved.transfer_correction_history||[])].reverse())details.append(el('p',`${old.changed_at} · ${old.kms==null?'Mapbox hersteld':old.kms+' km'} · ${old.reason}`));cell.append(details);
    }else if(saved?.message)cell.append(el('p',saved.message));tr.append(cell);body.append(tr);
  }
  table.append(head,body);const scroll=el('div');scroll.className='scroll';scroll.append(table);section.append(scroll);if(!body.children.length)section.append(el('p','Nog geen tussenlocatieroutes nodig of de shiftverwerking moet vernieuwd worden.'));
}
function shiftDisplayGroups(shifts,calculations){
  const groups=new Map();for(const m of shifts){const label=m.multi_location?`Meerdere werklocaties · ${m.day}`:m.location||m.source_location;if(!groups.has(label))groups.set(label,[]);groups.get(label).push(m);}
  for(const movements of groups.values())movements.sort((a,b)=>a.day.localeCompare(b.day)||(calculations.get(a.id)?.sequence??999)-(calculations.get(b.id)?.sequence??999)||(a.source_shifts?.map(s=>s.start).sort()[0]||'').localeCompare(b.source_shifts?.map(s=>s.start).sort()[0]||''));
  return [...groups].sort((a,b)=>a[0].localeCompare(b[0],'nl'));
}
function compactCalculationTrace(c){
  const cell=el('td');cell.className='calculation-trace';
  if(!c){cell.append(el('div','Vernieuwen nodig'));return cell;}
  if(c.amount==null){cell.append(el('div',calculationLabel(c.status)));if(c.reason)cell.append(el('div',c.reason));return cell;}
  cell.append(el('div',`${c.tariff_kind==='EXTRA48'?'Auto 48h':c.tariff_kind==='SPECIAL'?'Auto vroeg/laat':c.selected_mode||'Auto'} · ${c.distance} km${c.tariff_kind==='EXTRA48'?' enkel / '+c.reimbursed_kms+' km totaal':''} · ${c.distance_source||'Handmatig'}`));
  if(c.multi_location)cell.append(el('div',c.origin_location?`${c.origin_location} → werklocatie · standaardtarief`:'Eerste rit van de dag · thuis → werklocatie'));
  const details=el('details');details.append(el('summary','Details'));
  details.append(el('div',c.reason),el('div',`Afstand vanaf ${c.distance_valid_from}${c.mapbox_route_id?' · route #'+c.mapbox_route_id:''}`));
  if(c.override_reason)details.append(el('div',`HR: ${c.override_reason}`));
  details.append(el('div',`${c.rule} · tarief #${c.tariff_id} vanaf ${c.tariff_valid_from}`),el('div',c.tariff_source));cell.append(details);return cell;
}
function calculationLabel(status){return {CALCULATED:'Auto berekend',BLOCKED:'Nakijken',LATER_PHASE:'Nog niet in deze fase',EXCLUDED_TRAIN:'Trein · uitgesloten'}[status]||status;}
function selectedTariffs(){return (tariffKind==='extra48'?state.extra_shift_tariffs:tariffKind==='special'?state.special_car_tariffs:state.car_tariffs)||[];}
function renderTariffs(){const versions=selectedTariffs();$('tariffForm').hidden=tariffKind==='extra48';$('extraShiftTariffForm').hidden=tariffKind!=='extra48';selectItems('tariffVersion',versions.slice().reverse().map(t=>[t.id,`${t.valid_from} · versie ${t.id} · ${t.reason}`]),versions.at(-1)?.id||'');renderTariffForm();}
function renderTariffForm(){const tariff=selectedTariffs().find(t=>t.id===Number($('tariffVersion').value));if(!tariff)return;$('tariffSource').textContent=`Bron: ${tariff.source} · geldig vanaf ${tariff.valid_from} · opgeslagen ${tariff.changed_at}`;if(tariffKind==='extra48'){const form=$('extraShiftTariffForm');form.elements.valid_from.value=currentDay;form.elements.rate_per_km.value=tariff.rate_per_km;return;}const form=$('tariffForm');form.elements.valid_from.value=currentDay;form.elements.extra_per_km.value=tariff.data.extra_per_km;$('tariffRows').replaceChildren(...tariff.data.bands.map(b=>{const tr=el('tr');tr.append(el('td',`${b.from_km}–${b.to_km} km`));const cell=el('td'),input=el('input');input.required=true;input.inputMode='decimal';input.value=b.amount;input.dataset.from=b.from_km;input.dataset.to=b.to_km;input.setAttribute('aria-label',`Bedrag ${b.from_km} tot ${b.to_km} km`);cell.append(input);tr.append(cell);return tr;}));}
$('tariffForm').addEventListener('submit',async event=>{event.preventDefault();try{await save(tariffKind==='special'?'special_car_tariff':'car_tariff',{...Object.fromEntries(new FormData($('tariffForm'))),bands:[...$('tariffRows').querySelectorAll('input')].map(i=>({from_km:Number(i.dataset.from),to_km:Number(i.dataset.to),amount:i.value}))});}catch(error){message(error.message,true);}});
const tariffTypeLabel=el('label','Tariefsoort'),tariffType=el('select');tariffType.id='tariffType';for(const [value,label] of [['standard','Standaard · 120%-tabel'],['special','Vroeg/laat · 150%-tabel'],['extra48','48h-extra-shift · km-tarief heen en terug']]){const option=el('option',label);option.value=value;tariffType.append(option);}tariffTypeLabel.append(tariffType);$('tariffVersion').parentNode.before(tariffTypeLabel);tariffType.addEventListener('change',()=>{tariffKind=tariffType.value;renderTariffs();});$('tariffSettings').querySelector('h2').textContent='Instellingen · autotarief-tabellen';
const extraShiftForm=el('form');extraShiftForm.id='extraShiftTariffForm';extraShiftForm.hidden=true;extraShiftForm.className='grid';for(const [name,title,type] of [['valid_from','Geldig vanaf','date'],['rate_per_km','48h-tarief (€ per km, max. 4 decimalen)','text'],['reason','Reden van wijziging','text']]){const label=el('label',title),input=el('input');input.name=name;input.type=type;input.required=true;if(name==='rate_per_km')input.inputMode='decimal';if(name==='reason')input.value='HR bevestigt nieuw 48h-tarief';label.append(input);extraShiftForm.append(label);}extraShiftForm.append(el('p','Enkele km (naar boven afgerond) × 2 × dit tarief. Geen standaard- of vroeg/laat-vergoeding erbij.'),el('button','48h-tarief opslaan'));$('tariffForm').after(extraShiftForm);extraShiftForm.addEventListener('submit',async event=>{event.preventDefault();try{await save('extra_shift_tariff',Object.fromEntries(new FormData(extraShiftForm)));}catch(error){message(error.message,true);}});
$('tariffVersion').addEventListener('change',renderTariffForm);
initializeNavigation();
$('tabShifts').textContent='Maandshiften';
const calculationSummary=el('p');calculationSummary.id='calculationSummary';const calculationWarning=el('p');calculationWarning.id='calculationWarning';calculationWarning.className='warning';
const filterLabel=el('label','Berekeningscontrole'),filterSelect=el('select');filterSelect.id='calculationFilter';filterLabel.append(filterSelect);$('matchingSummary').after(calculationSummary,calculationWarning,filterLabel);selectItems('calculationFilter',[['all','Alle bewegingen'],['MULTI_LOCATION','Meerdere werklocaties · aparte controle'],['BLOCKED','Nakijken'],['CALCULATED','Auto berekend'],['LATER_PHASE','Nog niet in deze fase'],['EXCLUDED_TRAIN','Trein · uitgesloten']],'all');filterSelect.addEventListener('change',renderAgentShifts);
$('planetUpload').addEventListener('submit',async event=>{event.preventDefault();const file=$('planetFile').files[0],button=$('planetUpload').querySelector('button');if(!file)return;if(file.size>5_000_000){message('Bestand groter dan 5 MB.',true);return;}button.disabled=true;message('Export wordt geïmporteerd, gekoppeld en gecontroleerd…');try{const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(Error('Bestand lezen mislukt.'));reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);});await save('planet_upload',{filename:file.name,content});tab(true);message('Export verwerkt. Controleer de geselecteerde maand en filter op Nakijken of Nog niet in deze fase.');}catch(error){message(error.message,true);}finally{button.disabled=false;}});
