(() => {
'use strict';
const root=document.getElementById('read-aloud-body'),panel=document.getElementById('read-aloud');
if(!root || !panel) return;
const start=panel.querySelector('[data-start]'),pause=panel.querySelector('[data-pause]'),stop=panel.querySelector('[data-stop]'),rate=panel.querySelector('[data-rate]'),status=panel.querySelector('[data-status]');
if(!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)){
 status.textContent='当前浏览器不支持语音朗读，请尝试使用 Chrome、Edge 或 Safari。';
 [start,pause,stop,rate].forEach(el=>el.disabled=true); return;
}
const synth=window.speechSynthesis;
const selector='h2,h3,p,li,.warning,.callout,.gear > div';
const blocks=[...root.querySelectorAll(selector)].filter(el=>{
 for(let parent=el.parentElement;parent && parent!==root;parent=parent.parentElement){
  if(parent.matches(selector)) return false;
 }
 return true;
});
const chunks=blocks.flatMap(el=>{
 const copy=el.cloneNode(true);
 copy.querySelectorAll('button,nav,script,style,[data-no-read]').forEach(n=>n.remove());
 const text=copy.textContent.replace(/^\s*主持人\s*[AB甲乙一二]\s*[：:]\s*/u,'').replace(/\s+/g,' ').trim();
 const sentences=text.match(/[^。！？；!?;]+[。！？；!?;]?/gu)||[];
 return sentences.flatMap(s=>{
  const parts=[];while(s.length>140){let end=s.lastIndexOf('，',140);if(end<50)end=140;else end+=1;parts.push(s.slice(0,end));s=s.slice(end);}
  if(s.trim())parts.push(s);return parts;
 });
}).filter(Boolean);
let index=0,mode='idle',generation=0,activeUtterance=null;
function render(message){
 start.textContent=mode==='idle'?'朗读正文':'从头朗读';
 pause.disabled=mode==='idle';stop.disabled=mode==='idle';
 pause.textContent=mode==='paused'?'继续':'暂停';
 status.textContent=message||(mode==='playing'?'正在朗读正文':mode==='paused'?'已暂停，继续时从当前句开始。':'只朗读节目正文');
}
function cancel(){generation++;synth.cancel();activeUtterance=null;}
function speak(){
 if(mode!=='playing')return;
 if(index>=chunks.length){mode='idle';index=0;render('正文朗读完毕。');return;}
 const token=generation,utterance=new SpeechSynthesisUtterance(chunks[index]);
 activeUtterance=utterance;utterance.lang='zh-CN';utterance.rate=Number(rate.value);
 const voices=synth.getVoices();
 const voice=voices.find(v=>/^zh[-_]CN$/i.test(v.lang))||voices.find(v=>/^zh/i.test(v.lang));
 if(voice)utterance.voice=voice;
 utterance.onend=()=>{if(token!==generation || mode!=='playing')return;index++;speak();};
 utterance.onerror=(event)=>{
  if(token!==generation || mode!=='playing')return;
  mode='idle';index=0;activeUtterance=null;
  render(event.error==='not-allowed'?'浏览器未允许播放，请再次点击“朗读正文”。':'朗读暂时无法播放，请检查设备语音服务后重试。');
 };
 render('正在朗读正文 · '+(index+1)+' / '+chunks.length);
 try{synth.speak(utterance);}catch(e){mode='idle';render('朗读无法启动，请换一个支持中文语音的浏览器。');}
}
start.addEventListener('click',()=>{cancel();index=0;if(!chunks.length){mode='idle';render('本页暂时没有可朗读的正文。');return;}mode='playing';speak();});
pause.addEventListener('click',()=>{if(mode==='playing'){mode='paused';cancel();render();}else if(mode==='paused'){mode='playing';speak();}});
stop.addEventListener('click',()=>{mode='idle';cancel();index=0;render('已停止。再次点击可从头朗读。');});
rate.addEventListener('change',()=>{if(mode==='playing'){cancel();speak();}});
window.addEventListener('pagehide',()=>{mode='idle';cancel();});
render();
})();