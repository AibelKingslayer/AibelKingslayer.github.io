const loader=document.querySelector('.loader');
if(loader){const bar=loader.querySelector('.loader-track i'),num=loader.querySelector('small b');let n=0;const tick=setInterval(()=>{n=Math.min(100,n+Math.ceil(Math.random()*13));bar.style.width=n+'%';num.textContent=String(n).padStart(2,'0');if(n===100){clearInterval(tick);setTimeout(()=>loader.classList.add('done'),180)}},35)}
const toggle=document.querySelector('.nav-toggle'),nav=document.querySelector('.site-header nav');
toggle?.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',open)});
const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');observer.unobserve(e.target)}}),{threshold:0,rootMargin:'0px 0px -24px'});
document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));
const dot=document.querySelector('.cursor-dot');document.addEventListener('pointermove',e=>{if(dot){dot.style.left=e.clientX+'px';dot.style.top=e.clientY+'px'}});
const slug=s=>s.toLowerCase().trim().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');
const prose=document.querySelector('.prose'),toc=document.querySelector('.toc nav');
if(prose&&toc){prose.querySelectorAll('h2,h3').forEach(h=>{h.id=h.id||slug(h.textContent);const a=document.createElement('a');a.href='#'+h.id;a.textContent=h.textContent;a.style.paddingLeft=h.tagName==='H3'?'24px':'';toc.append(a)})}
const updateProgress=()=>{const article=document.querySelector('.article-layout'),rail=document.querySelector('.rail');if(!article||!rail)return;const rect=article.getBoundingClientRect(),total=article.offsetHeight-innerHeight,p=Math.max(0,Math.min(100,(-rect.top/total)*100));rail.querySelector('b').textContent=Math.round(p).toString().padStart(2,'0')+'%';rail.querySelector('i').style.setProperty('--progress',p+'%')};addEventListener('scroll',updateProgress,{passive:true});updateProgress();
const filter=document.querySelector('#post-filter');filter?.addEventListener('input',()=>{const q=filter.value.toLowerCase();document.querySelectorAll('#post-list .post-card').forEach(c=>c.hidden=!c.textContent.toLowerCase().includes(q))});
const tagButtons=document.querySelectorAll('.tag-cloud button'),tagCards=document.querySelectorAll('#tag-results .post-card');
tagButtons.forEach(btn=>btn.addEventListener('click',()=>{const active=!btn.classList.contains('active');tagButtons.forEach(b=>b.classList.toggle('active',active&&b===btn));tagCards.forEach(c=>c.hidden=active&&!c.dataset.tags.split(' ').includes(btn.dataset.tag));history.replaceState(null,'',active?'#'+encodeURIComponent(btn.dataset.tag):'/tags/')}));
if(location.hash&&tagButtons.length){const wanted=decodeURIComponent(location.hash.slice(1)).toLowerCase(),btn=[...tagButtons].find(b=>b.dataset.tag===wanted);btn?.click()}
