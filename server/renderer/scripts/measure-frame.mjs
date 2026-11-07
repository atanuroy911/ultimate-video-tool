// Pure DOM measurements, shared by the production probe and software-browser fixtures.
// This function must remain self-contained: Puppeteer serializes it into the page.
export function measureFrame(at, noRoom = {}) {
window.__vt.seek(at);
const shown = (n) => {
  for (let e = n; e && e.nodeType === 1; e = e.parentElement) {
    const s = getComputedStyle(e);
    if (s.display === "none" || s.visibility === "hidden" || parseFloat(s.opacity) < 0.3) return false;
  }
  const r = n.getBoundingClientRect();
  return r.width > 1 && r.height > 1;
};
const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
const both = (a, b) => ({ left: Math.max(a.left, b.left), right: Math.min(a.right, b.right), top: Math.max(a.top, b.top), bottom: Math.min(a.bottom, b.bottom) });
const part = (a, b) => (area(a) && a.right > b.left && b.right > a.left && a.bottom > b.top && b.bottom > a.top ? area(both(a, b)) / area(a) : 0);
const W = innerWidth, H = innerHeight, facts = [];
const faces = [...document.querySelectorAll(".cn-actor")].filter(shown).map((b) => {   // the drawing is 300 by 520: the head is the middle of its top third
  const r = (b.querySelector("svg") || b).getBoundingClientRect();
  return { name: b.getAttribute("data-name") || "a character", body: { left: r.left + r.width * 0.2, right: r.right - r.width * 0.2, top: r.top + r.height * 0.33, bottom: r.bottom }, box: { left: r.left + r.width * 0.25, right: r.right - r.width * 0.25, top: r.top + r.height * 0.05, bottom: r.top + r.height * 0.33 } };
});
for (const face of document.querySelectorAll("[data-face]")) {
  if (!shown(face)) continue;
  const person = face.closest("[data-person], .stk-ch");
  if (!person) continue;
  faces.push({name:person.dataset.name || "a character",box:face.getBoundingClientRect(),body:person.getBoundingClientRect(),owner:person});
}
// Face rectangles measured in source pixels must follow the image's actual
// object-fit crop and focal position, rather than stretching with its box.
for (const image of document.querySelectorAll("img[data-faces], video[data-faces]")) {
  if (!shown(image)) continue;
  let detected;
  try { detected = JSON.parse(image.dataset.faces); } catch { continue; }
  const r=image.getBoundingClientRect(),s=getComputedStyle(image);
  const sw=image.naturalWidth || image.videoWidth || Number(image.dataset.sourceWidth),sh=image.naturalHeight || image.videoHeight || Number(image.dataset.sourceHeight);
  if (!sw || !sh) continue;
  const k=s.objectFit === "contain" ? Math.min(r.width/sw,r.height/sh) : s.objectFit === "cover" ? Math.max(r.width/sw,r.height/sh) : null;
  const dw=k ? sw*k : r.width,dh=k ? sh*k : r.height;
  const pos=s.objectPosition.split(/\s+/).map(n=>parseFloat(n)/100);
  const left=r.left+(r.width-dw)*(pos[0]??.5),top=r.top+(r.height-dh)*(pos[1]??.5);
  for (const [x,y,w,h] of detected) {
    const box=both({left:left+x*dw,top:top+y*dh,right:left+(x+w)*dw,bottom:top+(y+h)*dh},r);
    if(area(box)>1) faces.push({name:image.dataset.personName || "a person",box,body:box,owner:image});
  }
}
const els = [...document.querySelectorAll(".el[data-el]")].filter((e) => shown(e) && !e.classList.contains("el-cartoon") && !e.classList.contains("el-story"))
  .map((e) => ({ node:e,label: `element ${e.getAttribute("data-el")} (${(/el-(\w+)/.exec(e.className) || [])[1] || "visual"})`, box: e.getBoundingClientRect() }));
for(const item of document.querySelectorAll("[data-story-type]")) {
  if(!shown(item) || ["person","group","particles"].includes(item.dataset.storyType)) continue;
  els.push({node:item,label:`story item (${item.dataset.storyType})`,box:item.getBoundingClientRect()});
}
const caps = [...document.querySelectorAll(".cap")].filter(shown).map((e) => ({node:e,label: "the caption", box: (e.querySelector(".cap-inner") || e).getBoundingClientRect() }));
for (const f of faces) for (const e of [...els, ...caps]) {
  if(f.owner && e.node?.contains(f.owner)) continue; // the person's own container is not an overlay
  if(f.owner && e.node?.dataset.storyType && (f.owner.compareDocumentPosition(e.node)&Node.DOCUMENT_POSITION_PRECEDING)) continue; // scenery painted before the character
  const covered = part(f.box, e.box);
  if (covered > 0.1) facts.push(`${e.label} covers ${Math.round(covered * 100)}% of ${f.name}'s face.`);
  const hidden = part(f.body, e.box);
  if (hidden > 0.08) facts.push(`${e.label} covers ${Math.round(hidden * 100)}% of ${f.name}'s body.`);
}
if (faces.length && !facts.length) facts.push("Nothing covers any character.");
for (const e of els) {
  const r = e.box, kept = area(both(r, { left: 0, top: 0, right: W, bottom: H })) / (area(r) || 1);
  if (kept < 0.9) facts.push(`${e.label} is ${Math.round((1 - kept) * 100)}% outside the frame.`);
  for (const c of caps) if (part(c.box, r) > 0.1) facts.push(`${e.label} overlaps the caption.`);
}
for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
  const small = area(els[i].box) < area(els[j].box) ? [els[i], els[j]] : [els[j], els[i]];
  const o = part(small[0].box, small[1].box);
  if (o > 0.2) facts.push(`${small[1].label} covers ${Math.round(o * 100)}% of ${small[0].label}.`);
}
// What the layout guard would have done to a scene an AI directed. It did nothing: the director is told instead. Measured on the scene's last frame, when everything has arrived.
// A finding the measurements above already say (an element outside the frame, one covering another) is not said twice.
const here = [...document.querySelectorAll(".scene")].find(shown), sceneId = here ? here.dataset.scene : "";
const add = (text) => { if (!facts.includes(text)) facts.push(text); };
// Report readable text size after transforms, simple solid-background contrast,
// platform controls and partial opacity. Unknown image backgrounds are not
// assigned an invented contrast ratio.
const rgba = value => { const m=value.match(/^rgba?\(([^)]+)\)/);return m ? m[1].split(/[,\s/]+/).map(Number) : null; };
const lum = rgb => rgb.slice(0,3).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
for(const e of [...els,...caps]) {
  let opacity=1;
  for(let node=e.node;node&&node.nodeType===1;node=node.parentElement) opacity*=Number(getComputedStyle(node).opacity);
  if(opacity>=.3 && opacity<.95) add(`${e.label} is partly transparent (${Math.round(opacity*100)}% opacity) at this moment.`);
  const textNodes=[];
  const walker=document.createTreeWalker(e.node,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()) if(walker.currentNode.textContent.trim()) textNodes.push(walker.currentNode);
  let small=false,low=false,platform=false;
  for(const text of textNodes) {
    const node=text.parentElement;if(!shown(node))continue;
    const s=getComputedStyle(node),rect=node.getBoundingClientRect();
    const own=node.offsetHeight||rect.height,scale=own?rect.height/own:1;
    if(parseFloat(s.fontSize)*scale < 34*W/1080)small=true;
    if(H>W && (rect.right>W*.88 || rect.bottom>H*.84))platform=true;
    let bg=null;
    for(let p=node;p&&p.nodeType===1;p=p.parentElement){
      const ps=getComputedStyle(p);if(ps.backgroundImage!=="none")break;
      const c=rgba(ps.backgroundColor);if(c&&(c.length<4||c[3]===1)){bg=c;break;}
    }
    const fg=rgba(s.color);
    if(bg&&fg&&(fg.length<4||fg[3]===1)){const a=lum(fg),b=lum(bg);if((Math.max(a,b)+.05)/(Math.min(a,b)+.05)<4.5)low=true;}
  }
  if(small)add(`${e.label} has letters smaller than the phone reading target (34 px at 1080 wide).`);
  if(low)add(`${e.label} has low text contrast on a solid background (below 4.5:1).`);
  if(platform)add(`${e.label} has text in the platform button or bottom-caption zone (right 12% or bottom 16% of a portrait frame).`);
}
const said = (...needles) => facts.some((f) => needles.every((n) => f.includes(n)));
for (const g of window.__guard || []) {
  if (!g.directed) continue;
  if (/^prop:/.test(g.type)) { if (g.scene === sceneId) add(`The prop ${g.type.slice(5)} is cut by the shot: more than a quarter of it is outside the frame.`); continue; }
  if (!els.some((e) => e.label.startsWith(`element ${g.el} (`))) continue;           // on another page of the scene, or not on screen at this moment
  const what = `element ${g.el} (${g.type})`;
  if (g.rule === "cut-off" && !said(what, "outside the frame")) add(`${what} runs off the frame.`);
  else if (g.rule === "too-small") add(`${what} has letters too small to read on a phone.`);
  else if (g.rule === "overlap" && !said(what, `element ${g.with} (`)) add(`${what} overlaps element ${g.with} by more than a fifth of the smaller one.`);
}
if (noRoom[sceneId]) add("There is no free room beside the person in the picture for this scene's elements: they sit on the picture.");
if (facts.some((f) => f !== "Nothing covers any character.")) {             // where a moved element could go
  const taken = [...faces.flatMap((f) => [f.box, f.body]), ...els.map((e) => e.box), ...caps.map((c) => c.box)];
  const free = [];
  for (let y = 0.04; y < 0.82; y += 0.04) {
    const band = { left: W * 0.08, right: W * 0.92, top: H * y, bottom: H * (y + 0.04) };
    if (!taken.some((r) => part(band, r) > 0)) { const last = free[free.length - 1]; if (last && Math.abs(last[1] - y) < 0.001) last[1] = y + 0.04; else free.push([y, y + 0.04]); }
  }
  const room = free.filter(([a, b]) => b - a >= 0.08).map(([a, b]) => `y ${a.toFixed(2)} to ${b.toFixed(2)}`);
  if (room.length) facts.push(`Empty across the frame: ${room.join(", ")}.`);
}
return facts;
}
