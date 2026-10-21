const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const test=require('node:test');
const assert=require('node:assert/strict');
const context={};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/epubreader/reader-preferences.js'),'utf8'),context);
const rules=context.ReaderPreferences;
const plain=value=>JSON.parse(JSON.stringify(value));

test('book A changes do not mutate book B, defaults or the caller object',()=>{
  const a={id:'a'},b={id:'b'};
  rules.saveBook(a,rules.defaults);rules.saveBook(b,rules.defaults);
  const changed={...a.preferences,font:14,line:1.3};rules.saveBook(a,changed);
  changed.font=36;
  assert.equal(a.preferences.font,14);
  assert.equal(b.preferences.font,21);
  assert.equal(b.preferences.line,1.9);
  assert.equal(rules.defaults.font,21);
});
test('book preferences survive serialized storage and normalize independently',()=>{
  const a={id:'a'},b={id:'b'};
  rules.saveBook(a,{font:14,line:1.3,theme:'sepia'});
  rules.saveBook(b,{font:30,line:2.2,theme:'dark'});
  const restored=JSON.parse(JSON.stringify([a,b]));
  assert.equal(rules.normalize(restored[0].preferences).font,14);
  assert.equal(rules.normalize(restored[1].preferences).font,30);
  assert.equal(rules.normalize().font,21);
});
test('legacy migration takes independent snapshots',()=>{
  const legacy={font:17,line:1.4},a={},b={};
  rules.saveBook(a,legacy);rules.saveBook(b,legacy);
  rules.saveBook(a,{...a.preferences,font:29});
  assert.equal(b.preferences.font,17);assert.equal(legacy.font,17);
});
test('minimum body metrics are the same absolute pixels for every book',()=>{
  assert.deepEqual(plain(rules.metrics('body',14,1.3)),{font:14,line:18.2});
  assert.deepEqual(plain(rules.metrics('body',14,2.5)),{font:14,line:35});
  assert.deepEqual(plain(rules.metrics('body',28,1.3)),{font:28,line:36.4});
  assert.equal(rules.metrics('h1',14,1.3).font,25.2);
  assert.equal(rules.metrics('rt',14,1.3).font,7);
});
test('invalid stored values cannot escape supported ranges',()=>{
  assert.equal(rules.normalize({font:100,line:0}).font,36);
  assert.equal(rules.normalize({font:100,line:0}).line,1.3);
  assert.equal(rules.normalize({font:'bad',line:Infinity,theme:'bad'}).font,21);
});

test('optional cream paper persists per book without changing the default or other books',()=>{
  const a={id:'a'},b={id:'b'};
  rules.saveBook(a,{font:22,theme:'cream'});
  rules.saveBook(b,{font:18,theme:'sepia'});
  const restored=JSON.parse(JSON.stringify([a,b]));
  assert.equal(rules.normalize(restored[0].preferences).theme,'cream');
  assert.equal(rules.normalize(restored[1].preferences).theme,'sepia');
  assert.equal(rules.normalize().theme,'paper');
});

test('horizontal writing persists per book and generic defaults retain publisher layout',()=>{
  const a={},b={};rules.saveBook(a,{writing:'horizontal'});rules.saveBook(b,{});
  assert.equal(rules.normalize(JSON.parse(JSON.stringify(a.preferences))).writing,'horizontal');
  assert.equal(b.preferences.writing,'original');
  assert.equal(rules.normalize({writing:'vertical'}).writing,'original');
  assert.equal(rules.defaults.writing,'original');
});

test('Japanese books default to horizontal, including old automatic original values',()=>{
  for(const language of ['ja','ja-JP','ja_JP','jpn','Japanese','日本語']){
    assert.equal(rules.forBook({writing:'original'},{language}).writing,'horizontal');
  }
  assert.equal(rules.forBook({writing:'original',writingExplicit:true},{language:'ja'}).writing,'original');
  assert.equal(rules.forBook({}, {language:'en'}).writing,'original');
  assert.equal(rules.forBook({}, {language:'ja',layout:'pre-paginated'}).writing,'original');
  assert.equal(rules.forBook({writing:'horizontal',writingExplicit:true},{language:'ja'}).writing,'horizontal');
});
