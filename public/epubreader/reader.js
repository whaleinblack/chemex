/* EPUB Reader for ChemEx. Dependencies are vendored; books remain in IndexedDB. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const icons = {
    back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
    contents: '<path d="M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01"/>',
    search: '<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>',
    bookmark: '<path d="M6 3h12v18l-6-4-6 4V3Z"/>',
    notes: '<path d="M4 3h16v14l-4 4H4V3Zm10 18v-6h6M8 8h8M8 12h5"/>',
    focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 3l6 6m12-6-6 6M3 21l6-6m12 6-6-6"/>',
    previous: '<path d="m15 6-6 6 6 6"/>', next: '<path d="m9 6 6 6-6 6"/>',
    moon: '<path d="M20.8 13A9 9 0 0 1 11 3.2 9 9 0 1 0 20.8 13Z"/>'
  };
  function icon(name) { return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`; }
  for (const name of ['back','bookmark','focus','previous','next']) $(`#${name}`).innerHTML = icon(name);
  for (const name of ['contents','search','notes']) $(`.reader-header [data-panel="${name}"]`).innerHTML = icon(name);
  $('#site-theme').innerHTML = icon('moon');
  const escape = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const text = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
  const defaultSettings = {font:21,line:1.9,theme:'paper',flow:'paginated',wheel:true};
  let settings;
  try { settings = {...defaultSettings,...JSON.parse(localStorage.getItem('chemex-reader-settings') || '{}')}; } catch { settings = {...defaultSettings}; }
  settings.font = Math.max(14,Math.min(36,Number(settings.font)||21));
  settings.line = Math.max(1.3,Math.min(2.5,Number(settings.line)||1.9));
  if (!['paper','sepia','dark'].includes(settings.theme)) settings.theme = 'paper';
  if (!['paginated','scrolled-doc'].includes(settings.flow)) settings.flow = 'paginated';
  document.documentElement.dataset.theme = settings.theme;
  let db, records = [], current, book, rendition, toc = [], filter = 'all', manage = false;
  let activePanel = '', savedSelection, focusMode = false, opening = false, turning = false;
  let turnAt = -Infinity, wheelAt = -Infinity, wheelSum = 0, wheelDirection = 0;
  let searchVersion = 0, saveTimer, toastTimer, generation = 0, lastFocus;
  const wiredDocuments = new WeakSet();
  const colors = ['#80654e','#527066','#6f6477','#9b7659','#596b7e','#8e625d'];

  function toast(message) { clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false; toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4000); }
  function storageWarning() { toast('浏览器存储不可用。当前仍可阅读，但刷新后可能无法保留记录。'); }
  function database() {
    return new Promise((resolve,reject) => {
      const request = indexedDB.open('chemex-epubreader',2);
      request.onupgradeneeded = () => {
        const value=request.result;
        if(!value.objectStoreNames.contains('books'))value.createObjectStore('books',{keyPath:'id'});
        const files=value.createObjectStore('files',{keyPath:'id'});
        // Move v1 book payloads once; page turns then update only small metadata records.
        const books=request.transaction.objectStore('books');
        books.openCursor().onsuccess=e=>{const cursor=e.target.result;if(!cursor)return;const record=cursor.value;if(record.data){files.put({id:record.id,data:record.data});delete record.data;cursor.update(record);}cursor.continue();};
      };
      request.onsuccess = () => {
        request.result.onversionchange=()=>{request.result.close();toast('阅读器已更新，请刷新此页面继续。');};
        resolve(request.result);
      };
      request.onblocked=()=>toast('请关闭其他旧版阅读器页面，完成本地书架升级。');
      request.onerror = () => reject(request.error);
    });
  }
  function operation(mode,run,storeName='books') {
    return new Promise((resolve,reject) => {
      if (!db) { reject(new Error('Storage unavailable')); return; }
      const tx = db.transaction(storeName,mode);
      const request = run(tx.objectStore(storeName));
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  }
  async function persist(record = current) {
    if (!record) return;
    const {data,...metadata}=record;
    try { await operation('readwrite',store => store.put(metadata)); } catch { storageWarning(); }
  }
  function saveSettings() { try { localStorage.setItem('chemex-reader-settings',JSON.stringify(settings)); } catch {} }
  const status = r => r.progress >= .99 ? 'finished' : r.cfi ? 'reading' : 'unread';
  const percent = r => Math.round((r.progress || 0) * 100);
  async function loadEpub(data) {
    const loaded = ePub();
    let timer;
    try {
      await Promise.race([
        (async()=>{await loaded.open(data.slice(0),'binary');await loaded.ready;})(),
        new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('EPUB open timeout')),20000);})
      ]);
      return loaded;
    } catch(error) { loaded.destroy(); throw error; }
    finally { clearTimeout(timer); }
  }

  function renderLibrary() {
    const query = text($('#library-query').value).toLowerCase();
    const books = records.filter(r => (filter === 'all' || status(r) === filter) && `${r.title} ${r.author}`.toLowerCase().includes(query)).sort((a,b) => b.updated-a.updated);
    $('#empty').hidden = records.length > 0;
    for (const b of $$('.filters button')) { b.classList.toggle('active',b.dataset.filter === filter); b.querySelector('span').textContent = records.filter(r => b.dataset.filter === 'all' || status(r) === b.dataset.filter).length; }
    $('#manage').textContent = manage ? '完成' : '管理';
    $('#no-matches').hidden = books.length > 0 || records.length === 0;
    $('#shelf').innerHTML = books.map(r => `<article class="book-item">${manage ? `<button class="book-delete" data-delete="${escape(r.id)}" aria-label="移除 ${escape(r.title)}">×</button>` : ''}<button class="book-open" data-book="${escape(r.id)}" aria-label="阅读 ${escape(r.title)}"><div class="book-cover" style="--cover:${colors[r.color % colors.length]}"><span class="cover-epub">EPUB · BOOK</span><span class="cover-title">${escape(r.title)}</span><span class="cover-rule"></span><span class="cover-author">${escape(r.author)}</span></div><strong class="book-name">${escape(r.title)}</strong><span class="book-meta">${escape(r.author)}</span></button><p class="book-status">${status(r)==='unread'?'未读':status(r)==='finished'?'已读完':`${percent(r)}% 已读`}</p></article>`).join('') + (records.length ? '<button class="add-book" data-upload><small>EPUB</small><b>＋</b><span>添加一本书</span></button>' : '');
    const recent = records.filter(r => r.cfi).sort((a,b) => b.updated-a.updated)[0];
    $('#continue').hidden = !recent;
    if (recent) $('#continue').innerHTML = `<div class="mini-cover">▤</div><div class="continue-info"><p class="eyebrow">CONTINUE READING</p><h2>${escape(recent.title)}</h2><progress max="100" value="${percent(recent)}" aria-label="阅读进度"></progress><p>${percent(recent)}% · ${escape(recent.chapter || recent.author)}</p></div><button class="primary" data-book="${escape(recent.id)}">继续阅读 →</button>`;
  }

  async function importBook(file) {
    if (opening) return;
    if (!file || !/\.epub$/i.test(file.name)) { toast('请选择 .epub 文件。'); return; }
    if (file.size > 150*1024*1024) { toast('文件超过 150 MiB，请选择较小的 EPUB。'); return; }
    opening = true; toast('正在读取 EPUB…');
    let candidate;
    try {
      const data = await file.arrayBuffer();
      const digest = await crypto.subtle.digest('SHA-256',data);
      const id = [...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
      const existing = records.find(r=>r.id===id);
      if (existing) { opening = false; return openBook(existing); }
      // Reject encrypted books and incomplete packages before opening the renderer.
      const zip = await JSZip.loadAsync(data);
      if (!zip.file('META-INF/container.xml')) throw new Error('Missing EPUB container');
      if (zip.file('META-INF/encryption.xml')) {
        const enc = await zip.file('META-INF/encryption.xml').async('string');
        if (/EncryptedData/i.test(enc) && !/embedding|obfuscat/i.test(enc)) throw new Error('DRM');
      }
      candidate = await loadEpub(data);
      const meta = await candidate.loaded.metadata;
      const record = {id,data,title:text(meta.title)||file.name.replace(/\.epub$/i,''),author:text(meta.creator)||'未知作者',updated:Date.now(),progress:0,cfi:'',chapter:'',marks:[],notes:[],color:records.length % colors.length};
      records.push(record);
      try { await operation('readwrite',s=>s.put({id,data}),'files'); } catch { storageWarning(); }
      await persist(record); renderLibrary();
      candidate.destroy(); candidate = null; opening = false;
      await openBook(record);
    } catch(error) {
      console.warn('EPUB import failed',error);
      candidate?.destroy(); opening = false;
      toast(error.message==='DRM' ? '暂不支持 DRM 加密的 EPUB，请选择未加密书籍。' : '无法打开此 EPUB，请确认文件完整且未加密。');
    } finally { $('#file').value = ''; }
  }

  function sanitize(doc) {
    // EPUB content never gets scripting permission. Strip active content and remote resources too.
    for (const el of doc.querySelectorAll('script,iframe,object,embed,form,base,meta[http-equiv],link[rel="preload"]')) el.remove();
    for (const el of doc.querySelectorAll('*')) {
      for (const attr of [...el.attributes]) {
        if (/^on/i.test(attr.name) || attr.name==='srcdoc' || /^(javascript|vbscript):/i.test(attr.value.trim())) el.removeAttribute(attr.name);
        if (['src','srcset','poster','href','xlink:href'].includes(attr.name) && /^(https?:)?\/\//i.test(attr.value.trim())) el.removeAttribute(attr.name);
      }
    }
  }
  function flatten(items,depth=0) { return (items||[]).flatMap(x=>[{...x,depth},...flatten(x.subitems,depth+1)]); }
  async function openBook(record) {
    if (opening) return;
    opening = true; const token = ++generation;
    lastFocus = document.activeElement;
    current = record; closePanel();
    $('#reader').hidden = false; document.body.style.overflow = 'hidden';
    $('#book-loading').hidden = false; $('#library').inert = true; $('.site-header').inert = true;
    $('#book-title').textContent = record.title; $('#book-author').textContent = record.author;
    $('#back').focus();
    try {
      rendition?.destroy(); book?.destroy(); $('#viewer').replaceChildren();
      const data=record.data || (await operation('readonly',s=>s.get(record.id),'files'))?.data;
      if(!data)throw new Error('Book payload unavailable');
      book = await loadEpub(data);
      book.spine.hooks.content.register(sanitize);
      toc = flatten((await book.loaded.navigation).toc);
      rendition = book.renderTo('viewer',{width:'100%',height:'100%',flow:settings.flow,spread:'none',allowScriptedContent:false,allowPopups:false});
      rendition.hooks.content.register(contents => {
        const doc = contents.document;
        if (!wiredDocuments.has(doc)) {
          wiredDocuments.add(doc);
          doc.addEventListener('wheel',onWheel,{passive:false,capture:true});
          doc.addEventListener('keydown',onKey);
          doc.addEventListener('pointerdown',()=>{$('#selection-tools').hidden=true;});
          let touch;
          doc.addEventListener('touchstart',e=>{if(e.touches.length===1)touch={x:e.touches[0].clientX,y:e.touches[0].clientY};},{passive:true});
          doc.addEventListener('touchend',e=>{if(!touch||!e.changedTouches.length)return;const dx=e.changedTouches[0].clientX-touch.x,dy=e.changedTouches[0].clientY-touch.y;touch=null;if(settings.flow==='paginated'&&Math.abs(dx)>70&&Math.abs(dx)>Math.abs(dy)*1.5)turn(dx<0?1:-1);},{passive:true});
        }
      });
      rendition.on('selected',(cfi,contents)=>{
        const selection = contents.window.getSelection();
        const quote = text(selection?.toString());
        if (!quote) return;
        savedSelection = {cfi,quote}; $('#selection-tools').hidden=false;
      });
      rendition.on('relocated',location=>{ if(token===generation)relocated(location); });
      applyTheme();
      await rendition.display(record.cfi || undefined).catch(()=>rendition.display());
      for (const note of record.notes) addAnnotation(note);
      if(token!==generation)return;
      $('#book-loading').hidden=true; opening=false;
      updateModeButtons();
      // Generating true character locations supports progress across chapters and reloads.
      const activeBook = book;
      activeBook.locations.generate(300).then(()=>{
        if(token!==generation)return;
        $('#progress').disabled=false;
        const loc=rendition.currentLocation(); if(loc?.start)relocated(loc);
      }).catch(()=>{if(token===generation)toast('已打开书籍；此 EPUB 的进度定位暂不可用。');});
    } catch(error) {
      console.warn('EPUB rendering failed',error); opening=false;
      closeReader(); toast('书籍渲染失败，请尝试其他未加密 EPUB。');
    }
  }
  function relocated(loc) {
    if (!current || !loc?.start) return;
    const href = loc.start.href?.split('#')[0];
    const chapter = toc.find(x=>x.href.split('#')[0]===href);
    current.cfi=loc.start.cfi; current.chapter=text(chapter?.label)||`第 ${(loc.start.index||0)+1} 章`;
    if (book.locations.length()) current.progress=book.locations.percentageFromCfi(loc.start.cfi)||0;
    if(loc.atEnd)current.progress=1;
    current.updated=Date.now();
    $('#chapter-label').textContent=current.chapter;
    $('#percentage').textContent=`${percent(current)}%`;
    $('#progress').value=Math.round((current.progress||0)*1000);
    $('#previous').disabled=!!loc.atStart; $('#next').disabled=!!loc.atEnd;
    const marked=current.marks.some(m=>m.cfi===current.cfi);
    $('#bookmark').setAttribute('aria-pressed',String(marked));
    $('#bookmark').setAttribute('aria-label',marked?'移除书签':'添加书签');
    $('#selection-tools').hidden=true;
    clearTimeout(saveTimer); const record=current; saveTimer=setTimeout(()=>persist(record),400);
  }
  function closeReader() {
    if (opening) return;
    ++generation; ++searchVersion; clearTimeout(saveTimer);
    persist();
    rendition?.destroy(); book?.destroy(); rendition=null;book=null;
    $('#reader').hidden=true; $('#viewer').replaceChildren();
    $('#library').inert=false; $('.site-header').inert=false;
    document.body.style.overflow=''; $('#progress').disabled=true;
    closePanel(); setFocus(false); renderLibrary(); current=null;
    lastFocus?.focus();
  }
  async function turn(direction) {
    if(!rendition || opening || turning) return;
    turning=true;
    try { await (direction>0 ? rendition.next() : rendition.prev()); }
    catch { toast('无法翻页，请尝试从目录打开章节。'); }
    finally { turning=false; }
  }
  function onWheel(e) {
    if(!rendition || opening || activePanel || !settings.wheel || settings.flow!=='paginated' || $('#note-dialog').open) return;
    if(e.ctrlKey||e.metaKey||e.altKey||e.shiftKey||!e.deltaY||Math.abs(e.deltaX)>Math.abs(e.deltaY))return;
    if(e.target?.closest?.('input,textarea,button,a,select,[contenteditable="true"]'))return;
    if(e.cancelable)e.preventDefault();
    const now=performance.now(), direction=Math.sign(e.deltaY);
    if(now-wheelAt>180||direction!==wheelDirection)wheelSum=0;
    wheelAt=now;wheelDirection=direction;
    if(now-turnAt<450){wheelSum=0;return;}
    wheelSum+=Math.abs(e.deltaY)*(e.deltaMode===1?16:e.deltaMode===2?800:1);
    if(wheelSum<45)return;
    wheelSum=0;turnAt=now;turn(direction);
  }
  function onKey(e) {
    if($('#reader').hidden || e.ctrlKey || e.metaKey || e.altKey || $('#note-dialog').open) return;
    if(e.target?.closest?.('input,textarea,select,[contenteditable="true"]')) return;
    if(e.key==='Escape'){if(activePanel)closePanel();else if(focusMode)setFocus(false);else closeReader();return;}
    if(activePanel)return;
    if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();turn(e.shiftKey?-1:1);}
    if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();turn(-1);}
  }
  document.addEventListener('keydown',onKey);
  $('#viewer').addEventListener('wheel',onWheel,{passive:false});
  function applyTheme() {
    document.documentElement.dataset.theme=settings.theme;
    if(rendition) {
      const palettes={paper:['#fcfbf8','#282720'],sepia:['#f2e8d5','#4d402d'],dark:['#222321','#dddcd5']};
      const [bg,fg]=palettes[settings.theme];
      rendition.themes.default({
        html:{background:`${bg} !important`,color:`${fg} !important`},
        body:{background:`${bg} !important`,color:`${fg} !important`,'font-family':'Georgia, "Noto Serif SC", "Songti SC", SimSun, serif !important','font-size':`${settings.font}px !important`,'line-height':`${settings.line} !important`,padding:'24px 26px !important'},
        p:{'line-height':`${settings.line} !important`,'margin-bottom':'1.1em !important'},
        h1:{'font-size':'1.85em !important','line-height':'1.5 !important','margin-bottom':'1.2em !important'},
        h2:{'font-size':'1.5em !important','line-height':'1.5 !important'},
        img:{'max-width':'100% !important','object-fit':'contain'},a:{color:`${fg} !important`}
      });
      rendition.themes.fontSize(`${settings.font}px`);
    }
    saveSettings();
  }
  function updateModeButtons() {
    for(const [id,flow] of [['page-mode','paginated'],['scroll-mode','scrolled-doc']]) {
      $(`#${id}`).classList.toggle('active',settings.flow===flow); $(`#${id}`).setAttribute('aria-pressed',String(settings.flow===flow));
    }
    $('#wheel-hint').textContent=settings.flow==='paginated'?(settings.wheel?'↕ 滚轮翻页':'滚轮翻页已关闭'):'↕ 章节内连续滚动';
  }
  async function changeFlow(flow) { settings.flow=flow;saveSettings();updateModeButtons();if(rendition){rendition.flow(flow);await rendition.display(current.cfi);} }
  function setFocus(value) {focusMode=value;$('#reader').classList.toggle('focus-mode',value);$('#exit-focus').hidden=!value;$('#focus').setAttribute('aria-label',value?'退出专注模式':'进入专注模式');if(rendition)requestAnimationFrame(()=>rendition.resize());}
  function closePanel() { activePanel=''; ++searchVersion;$('#panel').hidden=true;$$('.reader-header [data-panel]').forEach(b=>b.classList.remove('active')); }
  function openPanel(name) {
    if(activePanel===name){closePanel();return;}
    activePanel=name;++searchVersion;$('#selection-tools').hidden=true;
    $('#panel').hidden=false;
    $$('.reader-header [data-panel]').forEach(b=>b.classList.toggle('active',b.dataset.panel===name));
    $('#panel-title').textContent={contents:'目录',search:'搜索书内文字',settings:'阅读设置',notes:'书签与笔记'}[name];
    const body=$('#panel-body');
    if(name==='contents') {
      body.innerHTML='<div class="toc-list">'+(toc.length?toc.map((x,i)=>`<button data-chapter="${i}" style="padding-left:${12+x.depth*14}px" class="${text(x.label)===current.chapter?'active':''}">${escape(text(x.label))}</button>`).join(''):'<p class="panel-description">这本书没有目录。请用翻页按钮阅读。</p>')+'</div>';
    }
    if(name==='search') {
      body.innerHTML='<form id="book-search" class="panel-search"><input type="search" id="search-query" placeholder="输入关键词" aria-label="书内搜索关键词" required><button class="primary" type="submit">搜索</button></form><p id="search-status" class="panel-description">搜索整本书的文字。</p><div id="search-results"></div>';
      $('#search-query').focus();$('#book-search').addEventListener('submit',searchBook);
    }
    if(name==='settings')renderSettings();
    if(name==='notes')renderNotes();
  }
  function renderSettings() {
    $('#panel-body').innerHTML=`<div class="setting"><label>字号</label><div class="font-control"><button data-font="-1" aria-label="减小字号">A−</button><output id="font-value">${settings.font} px</output><button data-font="1" aria-label="增大字号">A＋</button></div></div><div class="setting"><label for="line-spacing">行距 <output id="line-value">${settings.line.toFixed(1)}</output></label><input id="line-spacing" type="range" min="1.3" max="2.5" step="0.1" value="${settings.line}"></div><div class="setting"><label>纸张主题</label><div class="theme-options">${[['paper','纸白'],['sepia','暖色'],['dark','深夜']].map(([k,v])=>`<button data-theme="${k}" aria-pressed="${settings.theme===k}">${v}</button>`).join('')}</div></div><div class="setting"><label class="setting-toggle" for="wheel-enabled">鼠标滚轮翻页<input id="wheel-enabled" type="checkbox" ${settings.wheel?'checked':''}></label><p class="panel-description">分页模式下，向下翻下一页，向上翻上一页。保留 Ctrl + 滚轮缩放。</p></div><div class="setting"><label>键盘操作</label><p class="panel-description">← / →：翻页<br>Page Up / Page Down：翻页<br>空格 / Shift + 空格：下一页 / 上一页<br>Esc：关闭面板或退出专注模式</p></div>`;
    $('#line-spacing').addEventListener('input',e=>{settings.line=Number(e.target.value);$('#line-value').textContent=settings.line.toFixed(1);applyTheme();});
    $('#wheel-enabled').addEventListener('change',e=>{settings.wheel=e.target.checked;saveSettings();updateModeButtons();});
  }
  async function searchBook(e) {
    e.preventDefault(); const query=text($('#search-query').value);if(!query)return;
    const token=++searchVersion,activeBook=book;
    $('#search-results').replaceChildren();$('#search-status').textContent='正在搜索…';
    const results=[];
    try {
      for(const section of activeBook.spine.spineItems) {
        if(token!==searchVersion||activeBook!==book)return;
        await section.load(activeBook.load.bind(activeBook));
        results.push(...section.find(query));
        if(results.length>=100)break;
      }
      if(token!==searchVersion)return;
      $('#search-status').textContent=results.length?`找到 ${results.length>=100?'至少 100':results.length} 处结果`:'没有找到匹配文字。';
      $('#search-results').innerHTML=results.slice(0,100).map(r=>`<button class="search-result" data-location="${escape(r.cfi)}">${escape(r.excerpt)}</button>`).join('');
    }catch{if(token===searchVersion)$('#search-status').textContent='此书部分章节无法搜索，请换一个关键词重试。';}
  }
  function toggleBookmark() {
    if(!current?.cfi)return;
    const i=current.marks.findIndex(m=>m.cfi===current.cfi);
    if(i>=0){current.marks.splice(i,1);toast('已移除书签');}else{current.marks.push({id:crypto.randomUUID(),cfi:current.cfi,label:current.chapter,progress:current.progress,date:Date.now()});toast('已添加书签');}
    persist(); relocated(rendition.currentLocation()); if(activePanel==='notes')renderNotes();
  }
  function addAnnotation(note) {
    try { rendition.annotations.highlight(note.cfi,{},()=>{openPanel('notes');},'reader-highlight',{'fill':'#d6ae52','fill-opacity':'.28','mix-blend-mode':'multiply'}); } catch {}
  }
  function saveSelection(content='') {
    if(!savedSelection||!current)return;
    const note={id:crypto.randomUUID(),cfi:savedSelection.cfi,quote:savedSelection.quote,content,date:Date.now()};
    const existing=current.notes.find(n=>n.cfi===note.cfi);
    if(existing){existing.content=content||existing.content;persist();$('#selection-tools').hidden=true;if(activePanel==='notes')renderNotes();toast('已更新笔记');return;}
    current.notes.push(note);addAnnotation(note);persist();$('#selection-tools').hidden=true;if(activePanel==='notes')renderNotes();toast(content?'笔记已保存':'文字已标记');
  }
  function renderNotes() {
    $('#panel-body').innerHTML=`<div class="note-tabs"><button id="new-page-note">＋ 当前页笔记</button><button id="export-notes">导出笔记</button></div><p class="panel-description">${current.marks.length} 个书签 · ${current.notes.length} 条笔记与标记。选中文字可添加荧光标记或笔记。</p><h3 style="font-size:13px">书签</h3>${current.marks.map(m=>`<article class="note-card"><button class="text-button" data-location="${escape(m.cfi)}">${escape(m.label)} · ${Math.round((m.progress||0)*100)}%</button><footer><span></span><button data-remove-mark="${m.id}">移除</button></footer></article>`).join('')||'<p class="panel-description">还没有书签。</p>'}<h3 style="font-size:13px;margin-top:22px">笔记与标记</h3>${current.notes.map(n=>`<article class="note-card"><button class="text-button" data-location="${escape(n.cfi)}"><div class="quote">${escape(n.quote)}</div></button>${n.content?`<p>${escape(n.content)}</p>`:''}<footer><small class="subtle">${new Date(n.date).toLocaleDateString()}</small><button data-remove-note="${n.id}">移除</button></footer></article>`).join('')||'<p class="panel-description">还没有笔记。选中文字，记录你的想法。</p>'}`;
  }
  function noteDialog() {if(!savedSelection)return;$('#note-quote').textContent=savedSelection.quote;$('#note-text').value='';$('#note-dialog').showModal();$('#note-text').focus();}
  function exportNotes() {
    const data=`# ${current.title}\n\n${current.author}\n\n`+current.notes.map(n=>`> ${n.quote}\n\n${n.content||'（荧光标记）'}\n\n${new Date(n.date).toLocaleString()}\n\n---\n`).join('\n');
    const url=URL.createObjectURL(new Blob([data],{type:'text/markdown;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download=`${current.title.replace(/[\\/:*?"<>|]/g,'_')}-笔记.md`;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
  }

  document.addEventListener('click',async e=>{
    const target=e.target.closest('button');if(!target)return;
    if(target.hasAttribute('data-upload')){$('#file').click();return;}
    if(target.dataset.book){await openBook(records.find(r=>r.id===target.dataset.book));return;}
    if(target.dataset.delete){
      const id=target.dataset.delete;$('#delete-dialog').showModal();
      $('#delete-dialog').addEventListener('close',async()=>{if($('#delete-dialog').returnValue!=='delete')return;try{await operation('readwrite',s=>s.delete(id));await operation('readwrite',s=>s.delete(id),'files');records=records.filter(r=>r.id!==id);renderLibrary();toast('已从书架移除');}catch{storageWarning();}},{once:true});return;
    }
    if(target.dataset.filter){filter=target.dataset.filter;renderLibrary();return;}
    if(target.dataset.panel){openPanel(target.dataset.panel);return;}
    if(target.dataset.chapter!==undefined){const href=toc[Number(target.dataset.chapter)]?.href;if(href){closePanel();await rendition.display(href);}return;}
    if(target.dataset.location){const cfi=target.dataset.location;closePanel();await rendition.display(cfi);return;}
    if(target.dataset.font){const cfi=current.cfi;settings.font=Math.max(14,Math.min(36,settings.font+Number(target.dataset.font)));applyTheme();$('#font-value').textContent=`${settings.font} px`;await rendition.display(cfi);return;}
    if(target.dataset.theme){settings.theme=target.dataset.theme;applyTheme();renderSettings();return;}
    if(target.dataset.removeMark){current.marks=current.marks.filter(m=>m.id!==target.dataset.removeMark);persist();renderNotes();relocated(rendition.currentLocation());return;}
    if(target.dataset.removeNote){const note=current.notes.find(n=>n.id===target.dataset.removeNote);if(note)rendition.annotations.remove(note.cfi,'highlight');current.notes=current.notes.filter(n=>n.id!==target.dataset.removeNote);persist();renderNotes();return;}
    if(target.id==='new-page-note'){savedSelection={cfi:current.cfi,quote:current.chapter};noteDialog();}
    if(target.id==='export-notes')exportNotes();
  });
  $('#file').addEventListener('change',e=>importBook(e.target.files[0]));
  $('#library-query').addEventListener('input',renderLibrary);
  $('#manage').addEventListener('click',()=>{manage=!manage;renderLibrary();});
  $('#back').addEventListener('click',closeReader);
  $('#previous').addEventListener('click',()=>turn(-1));$('#next').addEventListener('click',()=>turn(1));
  $('#bookmark').addEventListener('click',toggleBookmark);
  $('#focus').addEventListener('click',()=>{closePanel();setFocus(!focusMode);});$('#exit-focus').addEventListener('click',()=>setFocus(false));
  $('#close-panel').addEventListener('click',closePanel);
  $('#page-mode').addEventListener('click',()=>changeFlow('paginated'));$('#scroll-mode').addEventListener('click',()=>changeFlow('scrolled-doc'));
  $('#progress').addEventListener('change',async e=>{if(!book?.locations.length())return;await rendition.display(book.locations.cfiFromPercentage(Math.min(.999,Number(e.target.value)/1000)));});
  $('#site-theme').addEventListener('click',()=>{settings.theme=settings.theme==='dark'?'paper':'dark';applyTheme();});
  $('#highlight').addEventListener('click',()=>saveSelection());$('#add-note').addEventListener('click',noteDialog);
  $('#note-dialog').addEventListener('close',()=>{if($('#note-dialog').returnValue==='save')saveSelection($('#note-text').value.trim());});
  // Trap keyboard focus inside the full-screen reader, while native note dialogs retain their own trap.
  $('#reader').addEventListener('keydown',e=>{if(e.key!=='Tab'||$('#note-dialog').open)return;const items=$$('#reader button,#reader input').filter(x=>!x.disabled&&x.getClientRects().length);const first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}});
  let dragCounter=0;
  $('#library').addEventListener('dragenter',e=>{e.preventDefault();dragCounter++;$('#empty').classList.add('dragging');});
  $('#library').addEventListener('dragover',e=>e.preventDefault());
  $('#library').addEventListener('dragleave',()=>{if(--dragCounter<=0)$('#empty').classList.remove('dragging');});
  $('#library').addEventListener('drop',e=>{e.preventDefault();dragCounter=0;$('#empty').classList.remove('dragging');importBook(e.dataTransfer.files[0]);});
  window.addEventListener('pagehide',()=>{if(current)persist();});

  async function example() {
    if(opening)return;
    const zip=new JSZip();
    zip.file('mimetype','application/epub+zip',{compression:'STORE'});
    zip.file('META-INF/container.xml','<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>');
    const titles=['第一章 一扇朝南的窗','第二章 走在书页之间','第三章 把时间还给自己'];
    const paragraphs=[
      '午后的阳光从窗帘的缝隙里照进来，在书桌上落下一道细长的光。林把刚泡好的茶放在手边，翻开那本在书架上等了很久的书。城市的声音还在窗外继续，房间里却安静下来。',
      '读书有时候像一次很轻的出发。没有行李，也不用查天气，只需要留出一点时间，便能去到从来没有去过的地方。书页之间，有遥远的山，有不知名的海，也有一些似曾相识的人。',
      '他曾经以为，每一段空闲都应该被安排得满满当当。后来才慢慢发现，生活也需要留白。留白不是浪费，它让那些细小的感受有地方落下来：茶香、风声，还有一句恰好在此刻读到的话。',
      '窗边的植物长出了一片新叶，叶缘还带着浅浅的绿。这样的变化很容易被忽略。可当他放慢速度，再抬头看时，很多原以为一成不变的事情，都悄悄有了新的样子。',
      '书里的旅人沿着河岸走了很久。他并不急着抵达某个终点，只是在每一座桥边停下来，看水面上的倒影。那些倒影被风吹散，又重新聚在一起，好像记忆一样。',
      '有些段落需要读两遍。第一次读到的是情节，第二次读到的却是自己。他在页边留下一道标记，心想，等下一次打开这本书时，也许又会有不同的理解。',
      '傍晚的光渐渐变暖，屋里的影子向另一侧移动。茶已经凉了，故事还没有结束。他轻轻翻过一页，像推开一扇小小的门。门的另一边，是下一段尚未展开的时间。',
      '阅读不必总有目的。它可以只是忙碌的一天里，一次温柔的停留。把屏幕上的通知放远一些，把注意力放回文字和呼吸。此刻不需要去别处，此刻就很好。'
    ];
    titles.forEach((title,i)=>zip.file(`OEBPS/ch${i+1}.xhtml`,`<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN"><head><title>${title}</title></head><body><h1>${title}</h1>${Array.from({length:20},(_,j)=>`<p>${paragraphs[(j+i*2)%paragraphs.length]}</p>`).join('')}</body></html>`));
    zip.file('OEBPS/nav.xhtml',`<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>目录</title></head><body><nav epub:type="toc"><ol>${titles.map((t,i)=>`<li><a href="ch${i+1}.xhtml">${t}</a></li>`).join('')}</ol></nav></body></html>`);
    zip.file('OEBPS/content.opf',`<?xml version="1.0" encoding="UTF-8"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">chemex-quiet-reading-v1</dc:identifier><dc:title>留一点时间，读一本书</dc:title><dc:creator>ChemEx · 示例读本</dc:creator><dc:language>zh-CN</dc:language><meta property="dcterms:modified">2026-10-18T00:00:00Z</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>${titles.map((_,i)=>`<item id="ch${i+1}" href="ch${i+1}.xhtml" media-type="application/xhtml+xml"/>`).join('')}</manifest><spine>${titles.map((_,i)=>`<itemref idref="ch${i+1}"/>`).join('')}</spine></package>`);
    zip.forEach((_,entry)=>{entry.date=new Date('2026-10-18T00:00:00Z');});
    const blob=await zip.generateAsync({type:'blob',mimeType:'application/epub+zip'});
    await importBook(new File([blob],'留一点时间，读一本书.epub',{type:'application/epub+zip'}));
  }
  $('#example').addEventListener('click',example);$('#more-example').addEventListener('click',example);
  database().then(async value=>{db=value;records=await operation('readonly',s=>s.getAll());renderLibrary();}).catch(()=>{storageWarning();renderLibrary();});
})();
