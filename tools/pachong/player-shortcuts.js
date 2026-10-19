/* Player-only keyboard controls, shared with the regression tests. */
(() => {
  'use strict';
  function handle(event,video,actions={}) {
    if(!video||event.defaultPrevented||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return false;
    if(event.target?.closest?.('input,textarea,select,button,a,[role="button"],[role="slider"],[contenteditable]:not([contenteditable="false"])'))return false;
    const key=event.key==='Spacebar'?' ':event.key;
    if(![' ','ArrowLeft','ArrowRight'].includes(key)||video.readyState<1)return false;
    // Holding space must not toggle continuously; arrow keys may repeat.
    event.preventDefault();event.stopImmediatePropagation();
    if(key===' '){
      if(event.repeat)return true;
      if(video.paused||video.ended){const result=video.play();result?.catch?.(()=>actions.onError?.());}
      else{video.pause();actions.onPause?.();}
    }else if(Number.isFinite(video.duration)&&video.duration>0){
      video.currentTime=Math.max(0,Math.min(video.duration,video.currentTime+(key==='ArrowRight'?10:-10)));
      actions.onSeek?.(video.currentTime);
    }
    return true;
  }
  globalThis.ChemExPlayerShortcuts=Object.freeze({handle});
})();
