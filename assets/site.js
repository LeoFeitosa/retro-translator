(function(){
var tv=document.querySelector(".tv");if(!tv)return;
var root=tv.getAttribute("data-root"),img=document.getElementById("shot");
var lang=tv.querySelector("[data-shot][aria-pressed=true]").getAttribute("data-shot"),orig=false;
function show(){img.src=root+"assets/save-"+(orig?"ja":lang)+".png";
tv.querySelectorAll("[data-shot]").forEach(function(b){b.setAttribute("aria-pressed",b.getAttribute("data-shot")===lang)});
tv.querySelectorAll("[data-view]").forEach(function(b){b.setAttribute("aria-pressed",(b.getAttribute("data-view")==="orig")===orig)})}
tv.addEventListener("click",function(ev){var b=ev.target.closest("button");if(!b)return;
if(b.hasAttribute("data-shot")){lang=b.getAttribute("data-shot");orig=false}else orig=b.getAttribute("data-view")==="orig";show()});
document.querySelectorAll(".langs a").forEach(function(a){a.addEventListener("click",function(){
try{localStorage.setItem("rt-lang",a.getAttribute("hreflang"))}catch(e){}})})
})();
