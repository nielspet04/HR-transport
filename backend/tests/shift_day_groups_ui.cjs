const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('backend/app/configuration/web/routes.js','utf8');
const start=source.indexOf('function shiftDisplayGroups('),end=source.indexOf('\nfunction compactCalculationTrace(',start);
const ctx={};vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
const a={id:1,day:'2026-08-05',location:'Vilvoorde',multi_location:true,source_shifts:[{start:'08:00'}]},b={id:2,day:a.day,location:'Willebroek',multi_location:true,source_shifts:[{start:'14:00'}]},c={id:3,day:'2026-08-06',location:'Airport',multi_location:false,source_shifts:[{start:'06:00'}]};
const groups=ctx.shiftDisplayGroups([b,c,a],new Map([[1,{sequence:1}],[2,{sequence:2}]]));
assert.equal(groups.length,2);const day=groups.find(g=>g[0]==='Meerdere werklocaties · 2026-08-05');
assert.equal(day[1].length,2);assert.equal(day[1][0].id,1);assert.equal(day[1][1].id,2);
console.log('Multiple locations grouped by day, chronologically ordered, ordinary shifts retained.');
