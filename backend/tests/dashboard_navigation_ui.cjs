const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('backend/app/configuration/web/routes.js','utf8');
const start=source.indexOf('function showView('),end=source.indexOf("\n$('tabRoutes').addEventListener",start);
const nodes={};for(const id of ['routeView','addressesView','locationsView','shiftView','tariffSettings','monthlyImport','tabRoutes','tabAddresses','tabLocations','tabShifts','tabSettings'])nodes[id]={setAttribute(key,value){this[key]=value;}};
const headers={};const storage={};
const context={activeView:'routes',$:id=>nodes[id],document:{querySelectorAll(){return [];},querySelector(selector){return headers[selector]||(headers[selector]={});}},sessionStorage:{setItem(key,value){storage[key]=value;}}};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
const panels={routes:'routeView',addresses:'addressesView',locations:'locationsView',shifts:'shiftView',settings:'tariffSettings'};
for(const [view,panel] of Object.entries(panels)){
  context.showView(view);
  assert.equal(context.activeView,view);assert.equal(storage['hr-active-view'],view);
  for(const [key,id] of Object.entries(panels))assert.equal(nodes[id].hidden,key!==view);
  assert.equal(nodes.monthlyImport.hidden,view!=='shifts');
  assert.equal(Object.values(nodes).filter(n=>n['aria-current']==='page').length,1);
}
console.log('5 dashboard tabs tested: isolated visibility, upload placement, active state.');
