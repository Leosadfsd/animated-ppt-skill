// Config-driven local authoring. No user-machine paths and no automatic installs.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

async function runtime() {
  const location=process.env.RUNTIME_NODE_MODULES;
  let target;
  if(location) target=pathToFileURL(path.join(location,'@oai/artifact-tool/dist/artifact_tool.mjs')).href;
  else {
    const require=createRequire(path.join(process.cwd(),'package.json'));
    target=pathToFileURL(require.resolve('@oai/artifact-tool')).href;
  }
  return import(target);
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

export function previewHtml(title,states){
  // Text is inserted via textContent; escape '<' in script data to block </script>.
  const data=JSON.stringify(states).replace(/</g,'\\u003c');
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)} · 点击预览</title><style>
body{margin:0;background:#f4f3ef;color:#183c34;font:16px system-ui,sans-serif}main{max-width:1120px;margin:32px auto;padding:0 24px}h1{font-size:26px;margin-bottom:8px}p{line-height:1.7}nav{display:flex;gap:12px;align-items:center;margin:20px 0}button,select{font:inherit;padding:9px 14px;border:1px solid #a6b0aa;border-radius:6px;background:white;color:inherit}img{display:block;width:100%;border:1px solid #c4cac4}#cue{white-space:pre-wrap}#units{color:#68736c}small{color:#68736c}
</style><main><h1>${escapeHtml(title)}</h1><small>静态累计状态预览，用于检查讲述顺序；不模拟实际飞入、延迟或软件兼容性。</small>
<nav><button id="prev">上一步</button><select id="step" aria-label="页码与点击节点"></select><button id="next">下一步</button></nav>
<img id="image" alt="当前点击节点的静态画面"><h2 id="label"></h2><p id="cue"></p><p id="units"></p></main>
<script>const states=${data};const pick=document.getElementById('step');let index=0;
for(const [i,s] of states.entries()){const o=document.createElement('option');o.value=i;o.textContent='第 '+s.slide+' 页 · '+(s.beat===0?'自动入场后':'点击 '+s.beat+' 后');pick.append(o);}
function show(i){index=Math.max(0,Math.min(states.length-1,i));pick.value=index;const s=states[index];document.getElementById('image').src=s.file;document.getElementById('label').textContent='第 '+s.slide+' 页 · '+s.title;document.getElementById('cue').textContent=s.cue||'此节点没有配置讲稿提示';document.getElementById('units').textContent='本次出现：'+(s.entering.join('、')||'静态内容');document.getElementById('prev').disabled=index===0;document.getElementById('next').disabled=index===states.length-1;}
pick.onchange=()=>show(Number(pick.value));document.getElementById('prev').onclick=()=>show(index-1);document.getElementById('next').onclick=()=>show(index+1);show(0);</script></html>`;
}

export async function render(sceneFile,output){
  const {Presentation,PresentationFile}=await runtime();
  const scene=JSON.parse((await fs.readFile(sceneFile,'utf8')).replace(/^\uFEFF/,''));
  const base=path.dirname(path.resolve(sceneFile));
  const assets=new Map();
  for(const page of scene.slides)for(const unit of page.units)for(const item of unit.elements){
    if(item.type==='image'&&!assets.has(item.src))assets.set(item.src,new Uint8Array(await fs.readFile(path.resolve(base,item.src))));
  }
  const make=()=>Presentation.create({slideSize:{width:scene.width,height:scene.height}});
  function populate(p,page,cutoff=Infinity){
    const slide=p.slides.add();slide.background.fill=page.background||scene.background||'#F5F1E8';
    for(const unit of page.units){
      if(unit.beat>cutoff)continue;
      for(const [index,item] of unit.elements.entries()){
        const [left,top,width,height]=item.frame,key=unit.name+'__'+index;
        let shape;
        if(item.type==='image'){
          const ext=path.extname(item.src).toLowerCase();
          shape=slide.images.add({blob:assets.get(item.src),contentType:ext==='.jpg'||ext==='.jpeg'?'image/jpeg':'image/png',alt:key,position:{left,top,width,height},fit:item.fit||'contain'});
        }else{
          shape=slide.shapes.add({geometry:'textbox',name:key,position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
          shape.text=item.text;
          shape.text.style={typeface:item.font||scene.font,fontSize:item.size||42,bold:item.bold||false,italic:item.italic||false,color:item.color||scene.color||'#183C34',alignment:item.align||'left',verticalAlignment:'middle',wrap:'none',autoFit:'none',insets:0};
        }
        if(item.rotation)shape.rotation=item.rotation;
      }
    }
    slide.speakerNotes.text=[page.notes||'',...(page.sources||[]).map(s=>'Source: '+s)].join('\n');
    return slide;
  }
  await fs.mkdir(path.join(output,'previews'),{recursive:true});
  const p=make();const states=[];
  for(const [index,page] of scene.slides.entries()){
    const slide=populate(p,page);
    const png=await p.export({slide,format:'png',scale:1});
    await fs.writeFile(path.join(output,'previews',`p${index+1}-final.png`),new Uint8Array(await png.arrayBuffer()));
    const beats=[0,...new Set(page.units.filter(u=>u.beat>0).map(u=>u.beat))].sort((a,b)=>a-b);
    for(const beat of beats){
      const preview=make();const state=populate(preview,page,beat);
      const image=await preview.export({slide:state,format:'png',scale:1});
      const file=`previews/p${index+1}-beat${beat}.png`;
      await fs.writeFile(path.join(output,file),new Uint8Array(await image.arrayBuffer()));
      const entering=page.units.filter(u=>u.beat===beat);
      states.push({slide:index+1,title:page.title||'',beat,file,cue:entering.map(u=>u.cue||'').filter(Boolean).join('\n'),entering:entering.map(u=>u.name),visible:page.units.filter(u=>u.beat<=beat).map(u=>u.name)});
    }
  }
  await (await PresentationFile.exportPptx(p)).save(path.join(output,'draft.pptx'));
  await fs.writeFile(path.join(output,'states.json'),JSON.stringify(states,null,2));
  await fs.writeFile(path.join(output,'index.html'),previewHtml(scene.title||'动画PPT',states));
  const guide=['# '+(scene.title||'动画PPT')+'：点击与讲稿提示','','这些是静态累计状态；实际动画需在目标软件检查。',''];
  for(const s of states){guide.push(`## 第 ${s.slide} 页 · ${s.beat===0?'自动入场后':'第 '+s.beat+' 次点击后'}`,'',s.cue||'未配置提示','',`本次出现：${s.entering.join('、')||'静态内容'}`,'',`![点击状态](${s.file})`,'');}
  await fs.writeFile(path.join(output,'click-guide.md'),guide.join('\n'));
  console.log(JSON.stringify({slides:scene.slides.length,states:states.length,preview:'Static cumulative states only'}));
}

if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  if(process.argv[2]==='--probe'){
    try{await runtime();console.log(JSON.stringify({node:{ready:true,version:process.version,executable:process.execPath},authoring:{ready:true,backend:'@oai/artifact-tool'}}));}
    catch(e){console.log(JSON.stringify({node:{ready:true,version:process.version,executable:process.execPath},authoring:{ready:false,error:e.message,action:'Set RUNTIME_NODE_MODULES from your host dependency discovery tool; no packages were installed.'}}));}
  }else if(process.argv.length===4){
    try{await render(path.resolve(process.argv[2]),path.resolve(process.argv[3]));}
    catch(e){console.error(e.stack||e.message);process.exitCode=1;}
  }else{console.error('Usage: node render_scene.mjs --probe | scene.json new-build-directory');process.exitCode=1;}
}
