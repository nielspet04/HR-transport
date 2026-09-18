const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Node{
  constructor(tag,text){this.tag=tag;this.textContent=text;this.children=[];this.handlers={};}
  append(...nodes){this.children.push(...nodes);}
  addEventListener(event,fn){this.handlers[event]=fn;}
}
const source=fs.readFileSync('backend/app/configuration/web/routes.js','utf8');
const start=source.indexOf('function workerDistanceGroups('),end=source.indexOf('\nconst distanceBatch=',start);
const context={el:(tag,text)=>new Node(tag,text),openWorkerGroups:new Set()};vm.createContext(context);vm.runInContext(source.slice(start,end),context);
const rows=[
  {worker_id:1,name:'Serge',values:['Luchthaven','Auto','18']},
  {worker_id:1,name:'Serge',values:['Luchthaven','Fiets','14']},
  {worker_id:1,name:'Serge',values:['WeWork','Auto','7']},
  {worker_id:2,name:'Anna',values:['WeWork','Auto','9']},
  {worker_id:3,name:'Serge',values:['Andere locatie','Auto','5']},
];
let actions=0;
const make=(search='')=>context.workerDistanceGroups(rows,['Locatie','Vervoer','Km'],'mapbox',()=>actions++,search);
let result=make();assert.equal(result.children.length,3);assert.equal(actions,5);
assert.equal(result.children[0].children[0].children[0].textContent,'Anna');
const serge=result.children[1];assert.equal(serge.children[0].children[1].textContent,'2 locaties · 3 afstanden');
assert.equal(serge.children[1].children[0].children[1].children.length,3);
assert.equal(serge.open,false);serge.open=true;serge.handlers.toggle();
result=make();assert.equal(result.children[1].open,true);
result=make('fiets');assert.equal(result.children.length,1);assert.equal(result.children[0].children[1].children[0].children[1].children.length,3);
result=make('niemand');assert.equal(result.children[0].textContent,'Geen werknemers gevonden.');
console.log('Worker grouping: stable IDs, one entry, all locations/modes, search, action preservation and open state tested.');
