/* Survival's standalone homepage shortcut; no account or app state access. */
(()=>{
  const mount=()=>{
    if(document.getElementById('chemex-return-home'))return;
    const link=document.createElement('a');
    link.id='chemex-return-home';link.href='/';link.title='返回 ChemEx 主页';link.setAttribute('aria-label','返回 ChemEx 主页');
    const image=document.createElement('img');image.src='/home-assets/return-home.png?v=20261020';image.alt='返回 ChemEx 主页';image.width=44;image.height=44;
    image.style.cssText='display:block;width:100%;height:100%;object-fit:contain';link.append(image);
    link.style.cssText='position:fixed;left:max(12px,env(safe-area-inset-left));top:max(12px,env(safe-area-inset-top));width:44px;height:44px;z-index:1000;background:transparent;border:0;border-radius:12px;cursor:pointer;';
    document.body.append(link);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
