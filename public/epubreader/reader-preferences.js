/* Shared preference and typography rules; no storage or book content is global here. */
(() => {
  'use strict';
  const defaults=Object.freeze({font:21,line:1.9,theme:'paper',flow:'paginated',wheel:true,writing:'original'});
  function normalize(value={}) {
    const raw=value&&typeof value==='object'?value:{};
    const number=(key,min,max)=>Number.isFinite(Number(raw[key]))?Math.max(min,Math.min(max,Number(raw[key]))):defaults[key];
    return {writingExplicit:raw.writingExplicit===true,writing:raw.writing==='horizontal'?'horizontal':'original',font:number('font',14,36),line:number('line',1.3,2.5),theme:['paper','sepia','cream','dark'].includes(raw.theme)?raw.theme:defaults.theme,flow:['paginated','scrolled-doc'].includes(raw.flow)?raw.flow:defaults.flow,wheel:typeof raw.wheel==='boolean'?raw.wheel:defaults.wheel};
  }
  function forBook(value,metadata={}) {
    const preferences=normalize(value);
    const japanese=/^(?:ja|jpn)(?:[-_]|$)|^japanese$|^日本語$/i.test(String(metadata.language||'').trim());
    if(japanese && metadata.layout!=='pre-paginated' && !preferences.writingExplicit)preferences.writing='horizontal';
    return preferences;
  }
  function saveBook(record,value) {record.preferences=normalize(value);return {...record.preferences};}
  function metrics(role,font,line) {
    const scale=({h1:1.8,h2:1.5,h3:1.25,h4:1.12,h5:1.06,h6:1,small:.85,sup:.75,sub:.75,rt:.5,rp:.5})[role]||1;
    return {font:Math.round(font*scale*100)/100,line:Math.round(font*scale*(/^h[1-6]$/.test(role)?1.5:role==='rt'||role==='rp'?1:line)*100)/100};
  }
  globalThis.ReaderPreferences=Object.freeze({defaults,normalize,forBook,saveBook,metrics});
})();
