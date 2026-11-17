// Run with a host-provided @oai/artifact-tool runtime.
// RUNTIME_NODE_MODULES points to its node_modules; no author-machine paths.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const modules=process.env.RUNTIME_NODE_MODULES;
const lib=modules ? pathToFileURL(path.join(modules,'@oai/artifact-tool/dist/artifact_tool.mjs')).href : '@oai/artifact-tool';
const {Presentation, PresentationFile}=await import(lib);
const output=path.resolve(process.argv[2] || path.join(here,'build'));
await fs.mkdir(output,{recursive:true});
const manuscript=await fs.readFile(path.join(here,'manuscript.md'),'utf8');
const sections=manuscript.split(/^## \d+\..*$/m).slice(1).map(x=>x.trim());
if(sections.length!==3) throw new Error('Expected exactly three manuscript sections');
const data=[
 {title:'给散步留一点时间', large:'十分钟', cue:'没有任务，也不追求走多远'},
 {title:'一条熟悉的路', large:'路边的树', cue:'窗里的灯光'},
 {title:'把时间留给自己', large:'不追求成绩', cue:'走回来就很好'},
];
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
const motion={version:1,slides:[]};
function text(slide,name,value,box,size,color,bold=false){
 const t=slide.shapes.add({geometry:'textbox',name,position:box,fill:'none',line:{fill:'none',width:0}});
 t.text=value;
 t.text.style={typeface:'Microsoft YaHei',fontSize:size,color,bold,wrap:'none',autoFit:'none',insets:0,verticalAlignment:'middle'};
}
for(let i=0;i<data.length;i++){
 const slide=presentation.slides.add();slide.background.fill='#F5F1E8';
 text(slide,'title',data[i].title,{left:90,top:84,width:1100,height:86},52,'#183C34',true);
 text(slide,'main',data[i].large,{left:90,top:245,width:1100,height:170},118,'#183C34',true);
 text(slide,'cue',data[i].cue,{left:96,top:515,width:1090,height:70},42,'#AE4B27');
 slide.speakerNotes.text=sections[i];
 motion.slides.push({slide:i+1,units:[
  {name:'title',beat:0,from:'top',delay_ms:0,duration_ms:750},
  {name:'main',beat:1,from:i===1?'right':'left',delay_ms:0,duration_ms:850},
  {name:'cue',beat:2,from:'bottom',delay_ms:0,duration_ms:750},
 ]});
 const png=await presentation.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(output,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
await (await PresentationFile.exportPptx(presentation)).save(path.join(output,'draft.pptx'));
await fs.writeFile(path.join(output,'motion.json'),JSON.stringify(motion,null,2));
console.log('Created three editable slides, manuscript notes, previews and motion.json');
