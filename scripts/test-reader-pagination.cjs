/* Browser regression: generate fixtures first, serve the reader, then run this file.
 * PLAYWRIGHT_MODULE may point to an existing Playwright installation.
 * CHROME_PATH optionally selects the system Chrome executable.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fixtures=path.resolve(process.argv[2]||'delivery/writing-fixtures');
const url=process.env.READER_TEST_URL||'http://127.0.0.1:8783/epubreader/';
const output=process.env.READER_QA_OUTPUT;
async function clipping(page){
  return page.evaluate(()=>{
    const viewport=document.querySelector('#viewer .epub-container').getBoundingClientRect();
    const clipped=[];let visible=0;
    for(const iframe of document.querySelectorAll('#viewer iframe')){
      const doc=iframe.contentDocument,base=iframe.getBoundingClientRect();
      const walker=doc.createTreeWalker(doc.body,NodeFilter.SHOW_TEXT);let node;
      while(node=walker.nextNode()){
        if(!node.textContent.trim()||node.parentElement.closest('style,script'))continue;
        const range=doc.createRange();range.selectNodeContents(node);
        for(const box of range.getClientRects()){
          const left=base.left+box.left,right=base.left+box.right;
          if(right>viewport.left+1&&left<viewport.right-1){
            visible++;
            if(left<viewport.left-1||right>viewport.right+1)clipped.push(node.textContent.slice(0,24));
          }
        }
      }
    }
    return {visible,clipped};
  });
}
(async()=>{
  if(output)fs.mkdirSync(output,{recursive:true});
  for(const [name,engine] of [['webkit',webkit],['chromium',chromium]]){
    const browser=await engine.launch({headless:true,...(name==='chromium'&&process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
    try{for(const width of [1280,390]){
      const context=await browser.newContext({viewport:{width,height:900}});
      try{
        const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
        await page.goto(url);await page.locator('#file').setInputFiles(path.join(fixtures,'japanese-hanging.epub'));
        const ready=()=>page.waitForFunction(()=>!document.querySelector('#reader').hidden&&document.querySelector('#book-loading').hidden,null,{timeout:30000});
        await ready();await page.waitForTimeout(200);
        for(let i=0;i<4;i++){
          const result=await clipping(page);assert(result.visible>0);assert.deepEqual(result.clipped,[],name+' '+width+' page '+i);
          if(output&&i<2)await page.screenshot({path:path.join(output,`${name}-${width}-page-${i}.png`)});
          await page.locator('#next').click();await page.waitForTimeout(100);
        }
        await page.locator('[data-panel=settings]').click();await page.locator('[data-font="1"]').click();await page.locator('#close-panel').click();await page.waitForTimeout(250);
        assert.deepEqual((await clipping(page)).clipped,[],name+' font resize');
        await page.locator('[data-panel=settings]').click();await page.locator('[data-writing=original]').click();await ready();await page.locator('[data-writing=original][aria-pressed=true]').waitFor();
        await page.locator('[data-writing=horizontal]').click();await ready();await page.locator('[data-writing=horizontal][aria-pressed=true]').waitFor();await page.locator('#close-panel').click();
        assert.deepEqual((await clipping(page)).clipped,[],name+' restore horizontal');
        assert.deepEqual(errors,[]);console.log(`${name} ${width}: TOC, dialogue, 4 pages, font resize and writing restore: no clipped text`);
      }finally{await context.close()}
    }}finally{await browser.close()}
  }
})().catch(error=>{console.error(error);process.exit(1)});
