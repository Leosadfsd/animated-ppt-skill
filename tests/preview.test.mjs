import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {previewHtml} from '../skills/script-to-animated-ppt/scripts/render_scene.mjs';

test('offline preview preserves cues without injecting executable HTML',()=>{
 const cue='</script><script>throw new Error("injected")</script>';
 const states=[{slide:1,title:'One slide',beat:0,file:'previews/p1-beat0.png',cue,entering:['heading']}];
 const html=previewHtml('<unsafe title>',states);
 assert.ok(html.includes('&lt;unsafe title&gt;'));
 assert.ok(!html.includes(cue));
 const data=html.match(/const states=(.*?);const pick=/s)[1];
 assert.equal(JSON.parse(data)[0].cue,cue);
 assert.ok(html.includes('.textContent=s.cue'));
 assert.ok(html.includes('静态累计状态预览'));
});

test('click gallery advances cumulative screen states and corresponding manuscript cues',()=>{
 const states=[{slide:1,title:'Page one',beat:0,file:'previews/a.png',cue:'开场',entering:['title']},
 {slide:1,title:'Page one',beat:1,file:'previews/b.png',cue:'讲到纸条',entering:['label']},
 {slide:2,title:'Page two',beat:0,file:'previews/c.png',cue:'换页',entering:['photo']}];
 const html=previewHtml('Example',states);
 const nodes=new Map();
 const node=()=>({children:[],append(o){this.children.push(o);},value:'',textContent:'',disabled:false,src:''});
 const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
 vm.runInNewContext(html.match(/<script>([\s\S]*)<\/script>/)[1],{document});
 assert.equal(nodes.get('image').src,'previews/a.png');
 assert.equal(nodes.get('prev').disabled,true);
 nodes.get('next').onclick();
 assert.equal(nodes.get('image').src,'previews/b.png');
 assert.equal(nodes.get('cue').textContent,'讲到纸条');
 assert.equal(nodes.get('units').textContent,'本次出现：label');
 nodes.get('next').onclick();
 assert.equal(nodes.get('next').disabled,true);
 assert.equal(nodes.get('image').src,'previews/c.png');
 nodes.get('step').value='0';nodes.get('step').onchange();
 assert.equal(nodes.get('image').src,'previews/a.png');
});
