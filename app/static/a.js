(function(){
var E="/cdn/pixel.gif",pid=Math.random().toString(36).slice(2,10),t0=Date.now();
var mm=[],cl=[],sd=0,vis=[],fi={},fo=0,ps=[];

function s(t,d){
try{
var p=JSON.stringify({pid:pid,t:t,ts:Date.now(),url:location.href,data:d});
if(navigator.sendBeacon){navigator.sendBeacon(E,p);return}
fetch(E,{method:"POST",body:p,keepalive:true}).catch(function(){});
}catch(e){}
}

function ch(){
try{
var c=document.createElement("canvas"),x=c.getContext("2d");
c.width=200;c.height=50;
x.textBaseline="top";x.font="14px Arial";
x.fillStyle="#f60";x.fillRect(0,0,62,20);
x.fillStyle="#069";x.fillText("Cwm fjord",2,15);
x.fillStyle="rgba(102,204,0,0.7)";x.fillText("Cwm fjord",4,17);
var d=c.toDataURL();
var h=0;for(var i=0;i<d.length;i++){h=((h<<5)-h)+d.charCodeAt(i);h|=0}
return h.toString(36);
}catch(e){return null}
}

function wr(){
try{
var c=document.createElement("canvas");
var g=c.getContext("webgl")||c.getContext("experimental-webgl");
var d=g.getExtension("WEBGL_debug_renderer_info");
return d?g.getParameter(d.UNMASKED_RENDERER_WEBGL):null;
}catch(e){return null}
}

function af(){
try{
var a=new(window.AudioContext||window.webkitAudioContext)();
var o=a.createOscillator(),n=a.createDynamicsCompressor();
o.type="triangle";o.frequency.setValueAtTime(10000,a.currentTime);
n.threshold.setValueAtTime(-50,a.currentTime);
n.knee.setValueAtTime(40,a.currentTime);
n.ratio.setValueAtTime(12,a.currentTime);
n.attack.setValueAtTime(0,a.currentTime);
n.release.setValueAtTime(0.25,a.currentTime);
o.connect(n);n.connect(a.destination);
o.start(0);
var an=a.createAnalyser();n.connect(an);
var d=new Float32Array(an.frequencyBinCount);
an.getFloatFrequencyData(d);
o.stop();a.close();
var v=0;for(var i=0;i<d.length;i++)v+=Math.abs(d[i]);
return v.toString(36).slice(0,12);
}catch(e){return null}
}

function wip(cb){
try{
var r=new RTCPeerConnection({iceServers:[]});
r.createDataChannel("");
r.createOffer().then(function(o){r.setLocalDescription(o)});
r.onicecandidate=function(e){
if(!e||!e.candidate||!e.candidate.candidate)return;
var m=e.candidate.candidate.match(/(\d+\.\d+\.\d+\.\d+)/);
if(m){cb(m[1]);r.close()}
};
setTimeout(function(){try{r.close()}catch(e){}},3000);
}catch(e){cb(null)}
}

function pt(){
try{
var p=performance.getEntriesByType("navigation")[0];
if(!p)return null;
return{
dns:Math.round(p.domainLookupEnd-p.domainLookupStart),
tcp:Math.round(p.connectEnd-p.connectStart),
ttfb:Math.round(p.responseStart-p.requestStart),
load:Math.round(p.loadEventEnd-p.navigationStart),
dom:Math.round(p.domContentLoadedEventEnd-p.navigationStart)
};
}catch(e){return null}
}

function init(){
var cn=null;
try{var c=navigator.connection||navigator.mozConnection||navigator.webkitConnection;
if(c)cn={type:c.type||null,eff:c.effectiveType||null,dl:c.downlink||null}}catch(e){}

var d={
canvas:ch(),
webgl:wr(),
audio:af(),
screen:[screen.width,screen.height],
depth:screen.colorDepth,
dpr:window.devicePixelRatio||1,
mem:navigator.deviceMemory||null,
cores:navigator.hardwareConcurrency||null,
tz:Intl.DateTimeFormat().resolvedOptions().timeZone,
locale:navigator.language,
langs:navigator.languages?Array.from(navigator.languages):null,
dnt:navigator.doNotTrack==="1",
touch:"ontouchstart" in window||navigator.maxTouchPoints>0,
conn:cn,
plat:navigator.platform||null,
vendor:navigator.vendor||null,
perf:pt()
};

wip(function(ip){
d.webrtc_ip=ip;
s("init",d);
});

setTimeout(function(){
if(!d.webrtc_ip&&d.webrtc_ip!==null)s("init",d);
},3500);
}

var lastMM=0;
function onMM(e){
var n=Date.now();
if(n-lastMM<500)return;
lastMM=n;
mm.push([e.clientX,e.clientY,n-t0]);
if(mm.length>100)mm.shift();
}

function onCl(e){
var t=e.target;
cl.push({
x:e.clientX,y:e.clientY,
tag:t.tagName,id:t.id||null,name:t.name||null,
t:Date.now()-t0
});
if(cl.length>50)cl.shift();
}

function onSc(){
var h=document.documentElement.scrollHeight-window.innerHeight;
if(h>0){var p=Math.round((window.scrollY/h)*100);if(p>sd)sd=p}
}

function onVis(){
vis.push({state:document.visibilityState,t:Date.now()-t0});
}

function onFi(e){
var t=e.target;if(!t.name&&!t.id)return;
var k=t.name||t.id;
fi[k]={enter:Date.now()-t0,order:fo++};
}

function onFo(e){
var t=e.target;if(!t.name&&!t.id)return;
var k=t.name||t.id;
if(fi[k]){fi[k].dwell=Date.now()-t0-fi[k].enter}
}

function onPaste(e){
var t=e.target;
ps.push({field:t.name||t.id||null,t:Date.now()-t0});
}

function flush(){
if(!mm.length&&!cl.length&&sd===0&&!vis.length&&!Object.keys(fi).length)return;
s("interaction",{
mouse:mm.slice(),clicks:cl.slice(),scroll:sd,
visibility:vis.slice(),fields:Object.assign({},fi),pastes:ps.slice()
});
mm=[];cl=[];vis=[];ps=[];
}

function exit(){
s("exit",{
duration:Date.now()-t0,
mouse:mm,clicks:cl,scroll:sd,
visibility:vis,fields:fi,pastes:ps
});
}

document.addEventListener("mousemove",onMM,{passive:true});
document.addEventListener("click",onCl,{passive:true});
window.addEventListener("scroll",onSc,{passive:true});
document.addEventListener("visibilitychange",onVis);
document.addEventListener("focusin",onFi,{passive:true});
document.addEventListener("focusout",onFo,{passive:true});
document.addEventListener("paste",onPaste,{passive:true});

setInterval(flush,15000);

document.addEventListener("visibilitychange",function(){
if(document.visibilityState==="hidden")exit();
});
window.addEventListener("beforeunload",exit);

if(document.readyState==="loading"){
document.addEventListener("DOMContentLoaded",init);
}else{
init();
}
})();
