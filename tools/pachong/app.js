(() => {
  'use strict';
  const $=s=>document.querySelector(s),content=$('#content'),status=$('#status');
  const tags=['热门','最新','经典','豆瓣高分','冷门佳片','华语','欧美','韩国','日本','动作','喜剧','爱情','科幻','悬疑','恐怖','动画','豆瓣top250'];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let generation=0,controller,hls,film,lineIndex=0,episodeIndex=0,lastSaved=0;
  const historyKey='chemex-pachong-history-v1';
  function posterURL(url){try{const u=new URL(url);return /^img[1-9]\.doubanio\.com$/.test(u.hostname)?'./poster?url='+encodeURIComponent(url):url;}catch{return '';}}
  function history(){try{return JSON.parse(localStorage.getItem(historyKey)||'[]').filter(x=>x&&/^\d+$/.test(x.id)).slice(0,60);}catch{return [];}}
  function persist(){const v=$('#video');if(!v||!film)return;const items=history().filter(x=>x.id!==film.id);items.unshift({id:film.id,title:film.title,poster:film.poster,line:lineIndex,episode:episodeIndex,time:Number.isFinite(v.currentTime)?v.currentTime:0,updated:Date.now()});try{localStorage.setItem(historyKey,JSON.stringify(items.slice(0,60)));}catch{}}
  function destroy(){persist();if(hls){hls.destroy();hls=null;}const v=$('#video');if(v){v.pause();v.removeAttribute('src');v.load();}film=null;}
  async function get(route,params={}){const response=await fetch('./api/'+route+'?'+new URLSearchParams(params),{signal:controller.signal});const data=await response.json();if(!response.ok)throw Error(data.error||'请求失败，请稍后重试');return data;}
  function poster(item){return `<div class="poster"><span class="placeholder">影</span>${item.poster?`<img src="${esc(posterURL(item.poster))}" referrerpolicy="no-referrer" alt="${esc(item.title)}" loading="lazy">`:''}</div>`;}
  function cards(items){return `<div class="grid">${items.map(x=>`<a class="card" href="#play/${esc(x.id)}">${poster(x)}<h3>${esc(x.title)}</h3>${x.summary?`<p>${esc(x.summary)}</p>`:''}</a>`).join('')}</div>`;}
  function results(data){return (data.items.length?cards(data.items):'<div class="empty">没有找到匹配影片，换个片名或关键词试试。</div>')+`<div class="pager">${data.pages.map(x=>`<button data-path="${esc(x.path)}">${esc(x.label)}</button>`).join('')}</div>`;}
  function heading(title,sub=''){return `<div class="section-title"><h2>${esc(title)}</h2><small>${esc(sub)}</small></div>`;}
  function setPlayerStatus(message){const el=$('#player-status');if(el)el.textContent=message;}
  function drawEpisodes(){const line=film.lines[lineIndex];$('#line-select').value=String(lineIndex);$('#episodes').innerHTML=line.episodes.map((x,i)=>`<button data-episode="${i}" class="${i===episodeIndex?'active':''}">${esc(x.name)}</button>`).join('');}
  function playEpisode(line,episode,resume=0,autoplay=false){
    const video=$('#video');if(!video||!film?.lines[line]?.episodes[episode])return;
    if(hls){hls.destroy();hls=null;}video.pause();video.removeAttribute('src');video.load();lineIndex=line;episodeIndex=episode;drawEpisodes();
    const url=film.lines[line].episodes[episode].url;setPlayerStatus('正在连接 '+film.lines[line].name+' · '+film.lines[line].episodes[episode].name+'…');
    let resumed=false;video.onloadedmetadata=()=>{if(!resumed){resumed=true;if(resume>0&&resume<video.duration-3)video.currentTime=resume;}setPlayerStatus('已就绪 · '+film.lines[lineIndex].name+' · '+film.lines[lineIndex].episodes[episodeIndex].name);if(autoplay)video.play().catch(()=>setPlayerStatus('已就绪，请点击播放器中的播放按钮。'));};
    video.onerror=()=>setPlayerStatus('此线路暂不可播放，请在右侧切换其他线路。');
    video.onplaying=()=>setPlayerStatus('正在播放 · '+film.lines[lineIndex].name+' · '+film.lines[lineIndex].episodes[episodeIndex].name);
    video.ontimeupdate=()=>{if(Date.now()-lastSaved>5000){lastSaved=Date.now();persist();}};
    video.onpause=persist;video.onended=()=>{persist();if(episodeIndex+1<film.lines[lineIndex].episodes.length)playEpisode(lineIndex,episodeIndex+1,0,true);};
    if(/\.mp4(?:\?|$)/i.test(url)){video.src=url;}
    else if(window.Hls?.isSupported()){hls=new Hls({maxBufferLength:30,maxMaxBufferLength:60});hls.on(Hls.Events.ERROR,(_,data)=>{if(data.fatal){setPlayerStatus('此线路加载失败（'+data.type+'），请切换其他线路。');hls?.destroy();hls=null;}});hls.loadSource(url);hls.attachMedia(video);}
    else if(video.canPlayType('application/vnd.apple.mpegurl')){video.src=url;}
    else setPlayerStatus('此浏览器不支持 HLS 播放，请使用新版 Chrome、Edge 或 Safari。');
    persist();
  }
  function watch(data){
    film=data;document.title=data.title+' · 觅影';
    content.innerHTML=`<div class="watch-head"><h2>${esc(data.title)}</h2><button class="secondary" id="back-results">← 返回</button></div><div class="watch-layout"><div><div class="player-box"><video id="video" controls playsinline preload="metadata" aria-label="影片播放器"></video></div><div id="player-status" class="player-status" role="status"></div><div class="controls"><label for="speed">播放速度</label><select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select><button class="secondary" id="retry-play">重试本集</button><button class="secondary" id="next-episode">下一集 →</button></div><p class="shortcut-hint">空格：播放／暂停 · ← / →：快退／快进 10 秒</p><div class="film-info">${data.poster?`<img src="${esc(posterURL(data.poster))}" alt="${esc(data.title)}" referrerpolicy="no-referrer">`:''}<div>${data.info.map(x=>`<p>${esc(x)}</p>`).join('')}</div></div></div><aside class="line-panel"><h3>线路与选集</h3><label class="sr" for="line-select">选择播放线路</label><select id="line-select">${data.lines.map((x,i)=>`<option value="${i}">${esc(x.name)} · ${x.episodes.length} 集</option>`).join('')}</select><p class="hint">加载失败或版本不合适？切换另一条线路试试。</p><div class="episodes" id="episodes"></div></aside></div><p class="notice">播放线路来自原站，实际可用性、画质与内容取决于来源。视频可能含有来源方嵌入的广告，请勿相信其中的联系方式或支付信息。</p>`;
    if(data.lines.length){const saved=history().find(x=>x.id===data.id);const l=saved&&data.lines[saved.line]?saved.line:0;const e=saved&&data.lines[l].episodes[saved.episode]?saved.episode:0;playEpisode(l,e,saved?.time||0);}
    else{setPlayerStatus(data.notice);$('#line-select').disabled=true;$('#retry-play').disabled=true;$('#next-episode').disabled=true;}
  }
  async function render(){
    const token=++generation;controller?.abort();controller=new AbortController();destroy();status.textContent='正在获取最新数据…';content.innerHTML='';document.title='觅影 · ChemEx';
    const route=location.hash.slice(1)||'home';document.querySelectorAll('.top nav a').forEach(a=>a.classList.toggle('active',a.hash.slice(1)===route));
    try{
      if(route==='home') {const data=await get('home');if(token!==generation)return;content.innerHTML=data.sections.map((s,i)=>`<div class="section-title"><h2>${esc(s.title)}</h2><small>${i?'SERIES':'FILMS'}</small><a href="#catalog/${i?'tv':'movie'}">浏览更多 ↗</a></div>${cards(s.items)}`).join('');}
      else if(route.startsWith('catalog/')){const [,kind,rawTag]=route.split('/'),tag=decodeURIComponent(rawTag||'热门');const data=await get('catalog',{kind,tag});if(token!==generation)return;content.innerHTML=heading(kind==='tv'?'剧集':'电影','EXPLORE')+`<div class="chips">${tags.map(x=>`<button data-category="${kind}/${encodeURIComponent(x)}" class="${x===tag?'active':''}">${esc(x)}</button>`).join('')}</div>`+results(data);}
      else if(route.startsWith('search/')){const q=decodeURIComponent(route.slice(7));$('#query').value=q;const data=await get('search',{q});if(token!==generation)return;content.innerHTML=heading('搜索：'+q)+results(data);}
      else if(route==='rank'){const data=await get('list',{path:'/billboard.html'});if(token!==generation)return;content.innerHTML=heading('热门榜单','IN THE SPOTLIGHT')+results(data);}
      else if(route.startsWith('page/')){const data=await get('list',{path:decodeURIComponent(route.slice(5))});if(token!==generation)return;content.innerHTML=heading('继续发现')+results(data);}
      else if(route.startsWith('play/')){const data=await get('detail',{id:route.slice(5)});if(token!==generation)return;watch(data);}
      else if(route==='history'){const items=history();content.innerHTML=heading('最近观看','PICK UP WHERE YOU LEFT OFF')+(items.length?cards(items.map(x=>({...x,summary:`上次观看至 ${Math.floor(x.time/60)}:${String(Math.floor(x.time%60)).padStart(2,'0')}`}))):'<div class="empty">还没有播放记录，先找一部想看的影片吧。</div>');}
      else throw Error('页面不存在');
      status.textContent='';
    }catch(error){if(error.name==='AbortError'||token!==generation)return;status.textContent='';content.innerHTML=`<div class="error"><span>${esc(error.message)}</span><button id="reload" class="secondary">重新加载</button></div>`;}
  }
  $('#search-form').addEventListener('submit',e=>{e.preventDefault();const q=$('#query').value.trim();if(q){const hash='#search/'+encodeURIComponent(q);if(location.hash===hash)render();else location.hash=hash;}});
  content.addEventListener('error',e=>{if(e.target.tagName==='IMG')e.target.hidden=true;},true);
  content.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.category)location.hash='catalog/'+b.dataset.category;else if(b.dataset.path)location.hash='page/'+encodeURIComponent(b.dataset.path);else if(b.dataset.episode!==undefined)playEpisode(lineIndex,Number(b.dataset.episode),0,true);else if(b.id==='back-results')window.history.back();else if(b.id==='reload')render();else if(b.id==='retry-play')playEpisode(lineIndex,episodeIndex,0,true);else if(b.id==='next-episode'){if(episodeIndex+1<film.lines[lineIndex].episodes.length)playEpisode(lineIndex,episodeIndex+1,0,true);else setPlayerStatus('已经是本线路最后一集。');}});
  content.addEventListener('change',e=>{if(e.target.id==='line-select')playEpisode(Number(e.target.value),0,0,false);if(e.target.id==='speed')$('#video').playbackRate=Number(e.target.value);});
  document.addEventListener('keydown',event=>ChemExPlayerShortcuts.handle(event,$('#video'),{
    onError:()=>setPlayerStatus('无法开始播放，请点击播放器或切换线路。'),
    onPause:()=>{persist();setPlayerStatus('已暂停 · 空格继续播放');},
    onSeek:()=>persist()
  }),true);
  window.addEventListener('hashchange',()=>{render();window.scrollTo(0,0);});window.addEventListener('pagehide',persist);render();
})();
