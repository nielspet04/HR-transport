const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('backend/app/configuration/web/routes.js','utf8');
const start=source.indexOf('async function refresh('),end=source.indexOf('\nasync function save(',start);
const latest={run_id:30,month:'2026-09',source_sha256:'new'},old={run_id:10,month:'2026-08',source_sha256:'old'};
const state={view:'routes',matching:latest,matching_runs:[{id:21,month:'2026-08',source_sha256:'new'},{id:11,month:'2026-08',source_sha256:'old'}]};
const calls=[],ctx={matching:null,render(){},fetch:async url=>{calls.push(url);return {ok:true,json:async()=>url==='/api/state'?state:{...old,run_id:11}};}};
vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
(async()=>{
  await ctx.refresh();assert.equal(ctx.matching,null);assert.deepEqual(calls,['/api/state']);
  ctx.matching=old;await ctx.refresh();assert.equal(ctx.matching.run_id,11);assert.equal(calls.at(-1),'/api/matching/run?id=11');
  await ctx.refresh(true);assert.equal(ctx.matching,latest);
  ctx.matching=null;await ctx.refresh();assert.equal(ctx.matching,null);
  console.log('Empty initial/closed state, explicit historical source retained, upload opens new processing.');
})().catch(error=>{console.error(error);process.exitCode=1;});
