// Exercise the real renderer without a browser or third-party dependencies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor() { this.children = []; this.textContent = ''; this.classList = {toggle(){},add(){},remove(){}}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; this.textContent = ''; }
  addEventListener() {}
  show() { this.open = true; }
  close() { this.open = false; }
}
const elements = new Map();
const document = {
  getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
  createElement() { return new Element(); },
  createTextNode(text) { const e = new Element(); e.textContent = text; return e; },
  querySelector() { return new Element(); }, addEventListener(){}, body: new Element()
};
const context = vm.createContext({document, setInterval(){}, fetch: () => new Promise(()=>{})});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../web_assets/app.js'), 'utf8'), context);
const brief = {};
for (const key of ['headline','goal','capability','gap','next','decision']) brief[key] = {text:'旧地图结论', refs:[]};
const data = {project:'fixture', brief_status:'stale', brief, translations:{routes:{'R-A':{text:'保留的中文路线',detail:'仍然适用'}}},
  activity:{text:'本轮研究攻击防护'}, events:[{id:'EV-1',title:'English event',kind:'evidence'}], findings:[],
  payload:{recorded_status:'idle',block:{id:'RB-2',objective:'Attack defense'},
    routes:[{id:'R-A',title:'English route',status:'active',priority:1},{id:'R-B',title:'English changed',status:'queued',priority:2}],
    conclusions:[{id:'F-1',title:'English finding',status:'Open'}]}};
context.testData = data;
vm.runInContext('render(testData)', context);
function text(e) { return e.textContent + e.children.map(text).join(''); }
assert(text(document.getElementById('headline')).includes('旧地图结论'));
assert(text(document.getElementById('brief-label')).includes('待更新'));
assert.equal(document.getElementById('brief-panel').hidden, false);
assert.equal(text(document.getElementById('activity-text')), '本轮研究攻击防护');
assert(text(document.getElementById('routes')).includes('保留的中文路线'));
for (const id of ['routes','events','conclusions']) assert(!text(document.getElementById(id)).includes('English'));
data.activity = null;
data.payload.block = {id:'RB-3',objective:'Another direction'};
vm.runInContext('render(testData)', context);
assert(!text(document.getElementById('activity-text')).includes('攻击防护'));
assert(text(document.getElementById('activity-meta')).includes('RB-3'));
document.getElementById('brief-panel').open = false;
vm.runInContext('render(testData)', context);
assert.equal(document.getElementById('brief-panel').open, false);
data.brief_status = 'missing'; data.brief = null;
vm.runInContext('render(testData)', context);
assert.equal(document.getElementById('brief-panel').hidden, true);
console.log('Dashboard renderer: stale judgment, row fallback and current activity checks passed');
