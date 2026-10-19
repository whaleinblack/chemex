const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const context=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../tools/pachong/player-shortcuts.js'),'utf8'),context);
const {handle}=context.ChemExPlayerShortcuts;
function event(key,extra={}){return {key,target:{closest:()=>null},preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};}
function video(extra={}){return {readyState:4,currentTime:30,duration:100,paused:true,play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;},...extra};}
test('space toggles playback once and consumes native defaults',()=>{const v=video(),e=event(' ');assert.equal(handle(e,v),true);assert.equal(v.paused,false);assert.equal(e.prevented,true);handle(event(' ',{repeat:true}),v);assert.equal(v.paused,false);handle(event(' '),v);assert.equal(v.paused,true);});
test('arrows seek 10 seconds and clamp at both media boundaries',()=>{const v=video();handle(event('ArrowRight'),v);assert.equal(v.currentTime,40);handle(event('ArrowLeft'),v);assert.equal(v.currentTime,30);v.currentTime=95;handle(event('ArrowRight'),v);assert.equal(v.currentTime,100);v.currentTime=3;handle(event('ArrowLeft'),v);assert.equal(v.currentTime,0);});
test('typing, focused controls, modifiers, loading and other pages are untouched',()=>{for(const extra of [{target:{closest:()=>({})}},{ctrlKey:true},{metaKey:true},{altKey:true},{shiftKey:true},{defaultPrevented:true}]){const v=video(),e=event(' ',extra);assert.equal(handle(e,v),false);assert.equal(v.paused,true);assert.equal(e.prevented,undefined);}assert.equal(handle(event(' '),null),false);assert.equal(handle(event(' '),video({readyState:0})),false);assert.equal(handle(event('x'),video()),false);});
test('rejected play promise reports failure without an unhandled rejection',async()=>{let failed=false;handle(event(' '),video({play:()=>Promise.reject(Error('blocked'))}),{onError:()=>failed=true});await Promise.resolve();assert.equal(failed,true);});
