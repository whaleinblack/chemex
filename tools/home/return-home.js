/* Shared home shortcut. Reads layout only; never accesses account or app state. */
(()=>{
  const mount=()=>{
    if(document.getElementById('chemex-return-home'))return;
    const survival=location.pathname.startsWith('/survival/');
    const link=document.createElement('a');link.id='chemex-return-home';link.href='/';link.title='返回 ChemEx 主页';link.setAttribute('aria-label','返回 ChemEx 主页');
    const image=document.createElement('img');image.src='/home-assets/return-home.png?v=20261020';image.alt='';image.width=56;image.height=56;
    image.style.cssText='display:block;width:100%;height:100%;object-fit:contain';link.append(image);
    link.style.cssText='position:fixed;left:max(12px,env(safe-area-inset-left));top:max(12px,env(safe-area-inset-top));width:56px;height:56px;z-index:1000;background:transparent;border:0;border-radius:12px;cursor:pointer;';document.body.append(link);
    let queued=false;
    const place=()=>{
      queued=false;
      if(survival){
        const visible=e=>e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0;
        const clock=[...document.querySelectorAll('.desktop-time-panel strong')].find(visible) || [...document.querySelectorAll('.player-shell .top-bar h1,.mobile-shell .top-bar h1,.top-bar h1')].find(visible);
        link.hidden=!clock;
        if(clock){
          const range=document.createRange();range.selectNodeContents(clock);const r=range.getBoundingClientRect();
          const desktop=clock.matches('.desktop-time-panel strong');
          let left=r.right+10;
          if(!desktop){
            const bar=clock.closest('.top-bar');
            const settings=bar && [...bar.querySelectorAll('.mobile-module-settings,button[aria-label*="设置"],button[title*="设置"]')].filter(visible).map(e=>e.getBoundingClientRect()).filter(box=>box.left>=r.right).sort((a,b)=>a.left-b.left)[0];
            left=settings?(r.right+settings.left-56)/2:r.right+4;
          }
          link.style.left=Math.max(8,Math.min(left,innerWidth-64))+'px';
          const lift=desktop?8:4;
          link.style.top=Math.max(8,r.top+(r.height-56)/2-lift)+'px';
        }
      }else{
        const brand=document.querySelector('header.top > .brand,.site-header > .brand,.chemex-brand-group > .brand');
        const cof=document.querySelector('.hero-brand-row');
        if(brand){
          let group=brand.parentElement;
          if(!group.classList.contains('chemex-brand-group')){
            group=document.createElement('div');group.className='chemex-brand-group';
            group.style.cssText='display:flex;align-items:center;gap:10px;min-width:0;flex-shrink:0';
            brand.before(group);group.append(brand);
          }
          if(link.parentElement!==group)group.append(link);
        }else if(cof && link.parentElement!==cof)cof.append(link);
        if(brand || cof){
          link.style.position='static';link.style.flex='0 0 56px';link.style.alignSelf='center';
        }
        for(const old of document.querySelectorAll('header.top a.back,.site-header nav a[href="../"]'))old.hidden=true;
      }
    };
    const schedule=()=>{if(!queued){queued=true;requestAnimationFrame(place)}};
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
    window.addEventListener('resize',schedule,{passive:true});window.addEventListener('scroll',schedule,{passive:true});
    place();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
