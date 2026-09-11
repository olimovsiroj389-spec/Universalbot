/* Shadow City Web App frontend — all UI is inside the Web App. */
const TG = window.Telegram?.WebApp;
if (TG) { TG.ready(); TG.expand(); }

const S = {
  token: localStorage.getItem('sc_token') || null,
  me: null,
  page: 'dashboard',
  authMode: 'login',
};

const PAGE_INFO = {
  dashboard:['Bosh sahifa','Shahar seni kutmoqda.'], map:['Xarita','Shaharni o‘rganing.'], jobs:['Ishlar','Pul topishning 6 yo‘li.'],
  business:['Biznes','Pulni ishlating va daromadni oshiring.'], transport:['Transport','Shahar bo‘ylab tezroq yuring.'], arena:['Arena','Barcha qobiliyatlar jangda ishlaydi.'],
  clans:['Klanlar','Birga kuchliroqsiz.'], missions:['Missiyalar','Har bir vazifa mukofot beradi.'], inventory:['Inventar','Sizning narsalaringiz.'], shop:['Do‘kon','Kerakli buyumlarni shu yerdan oling.'],
  leaderboard:['Leaderboard','Shaharning kuchlilari.'], profile:['Profil','Qobiliyatlaringiz shu yerda.'], settings:['Sozlamalar','Hisob va o‘yin sozlamalari.'], admin:['Admin panel','Shahar boshqaruvi.']
};
const NAV = [
 ['dashboard','⌂','Bosh sahifa'],['map','◈','Xarita'],['jobs','◉','Ishlar'],['business','▣','Biznes'],['transport','◍','Transport'],
 ['arena','⚔','Arena'],['clans','♜','Klanlar'],['missions','◆','Missiyalar'],['inventory','▤','Inventar'],['shop','🛒','Do‘kon'],
 ['leaderboard','🏆','Leaderboard'],['profile','◉','Profil'],['settings','⚙','Sozlamalar'],['admin','🛠','Admin']
];
const JOBS = {
 carwash:['🚗','Avtomobil yuvish',800,1200,1], delivery:['📦','Yetkazib berish',1500,2500,2], construction:['🔨','Qurilish',2200,4200,3],
 cafe:['☕','Kafe',1200,2000,2], hacking:['💻','Hakerlik',8000,15000,4], secret:['🕵️','Maxfiy topshiriq',5000,12000,5]
};
const BUSINESSES = {
 cafe:['☕','Kafe',50000,1200], autosalon:['🚘','Avtosalon',120000,2800], restaurant:['🍽️','Restoran',200000,5000], it:['💻','IT kompaniya',350000,9000], oil:['⛽','Neft kompaniyasi',600000,15000], mall:['🏬','Savdo markazi',1200000,32000]
};
const VEHICLES = {
 bmw_m4:['🚘','BMW M4',120000,290,16], g63:['🚙','Mercedes G63',200000,240,10], huracan:['🏎️','Lamborghini Huracan',350000,325,24], rolls:['🚘','Rolls-Royce',500000,250,35]
};
const ITEMS = {
 medkit:['🩹','Medkit',2000,'HP +50','hp'], energy_drink:['⚡','Energiya ichimligi',1000,'Energiya +20','energy'], armor:['🦺','Zirh',15000,'Himoya +15','defense'],
 pistol:['🔫','Pistolet',20000,'Kuch +10','strength'], sniper:['🎯','Snayper',50000,'Kuch +25','strength'], gem:['💎','Qimmatbaho tosh',40000,'+ $1,000','money']
};
const MISSIONS = { first_business:['Birinchi biznes',5000,1],join_clan:['Klan a’zosi bo‘ling',10000,1],buy_vehicle:['Mashina sotib oling',15000,1],arena_win:['Arenada g‘alaba qozoning',20000,1],map_center:['Shahar markazini o‘rganing',3000,1],reach_level_5:['5-levelga chiqing',25000,5] };
const STAT_META = {
 jon:['❤️','Jon','Arena maksimal hayoti'], kuch:['⚔️','Kuch','Asosiy hujum kuchi'], topuvchanlik:['🎯','Topuvchanlik','Zarba tegishi va tashabbus'],
 zarba:['💥','Zarba','Zarar va kritik imkoniyati'], chidamlilik:['🛡️','Chidamlilik','Qabul qilinadigan zararni kamaytiradi']
};

function esc(v){return String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
function fmt(v){return Number(v||0).toLocaleString('en-US').replaceAll(',',' ');}
function btn(text, onclick, cls=''){return `<button class="btn ${cls}" onclick="${onclick}">${text}</button>`;}
function row(icon,title,sub,right,action=''){return `<div class="row"><div class="row-left"><div class="row-icon">${icon}</div><div><b>${esc(title)}</b><small>${esc(sub)}</small></div></div><div style="display:flex;align-items:center;gap:8px">${right?`<span class="price">${right}</span>`:''}${action}</div></div>`;}
function pageButton(p){return `onclick="go('${p}')"`}

async function api(url,opts={}){
  const headers = {'Content-Type':'application/json',...(opts.headers||{})};
  if(S.token) headers.Authorization='Bearer '+S.token;
  const r = await fetch(url,{...opts,headers});
  let data={}; try{data=await r.json();}catch{}
  if(!r.ok) throw new Error(data.detail || data.message || 'Xatolik yuz berdi.');
  return data;
}

function showToast(text){const t=document.getElementById('toast');t.textContent=text;t.classList.add('show');clearTimeout(showToast._timer);showToast._timer=setTimeout(()=>t.classList.remove('show'),2800);}
function initials(name){return esc((name||'S').trim().slice(0,1).toUpperCase());}

function startView(){
  const telegramMode = Boolean(TG?.initData);
  document.getElementById('root').innerHTML=`<div class="start-page">
    <div class="city-art" aria-hidden="true"><div class="stars"></div><div class="moon"></div><div class="city-glow"></div><div class="road-light"></div></div>
    <div class="city-title">
      <div class="eyebrow">ROLEPLAY • ONLINE CITY • WEB APP</div>
      <h1>SHADOW CITY</h1>
      <p>Bu oddiy o‘yin emas. Bu yerda o‘z yo‘lingizni o‘zingiz yaratasiz: pul toping, biznes quring, shaharni o‘rganing va Arena janglarida kuchingizni sinang.</p>
      <div class="start-badges"><span>♙ RPG</span><span>⚔️ ARENA</span><span>♜ KLAN</span><span>◈ LIVE CITY</span></div>
    </div>
    <div class="start-panel">
      <div class="brand"><div class="brand-mark">♛</div><div><b>SHADOW CITY</b><small>O‘Z YO‘LINGIZNI TANLANG</small></div></div>
      <div class="welcome-chip">✦ YANGI SARGUZASHT</div>
      <h2>${telegramMode?'Tayyormisiz?':'Shaharga xush kelibsiz.'}</h2>
      <div class="intro">${telegramMode?'Telegram profilingiz bilan bir tugmada davom etishingiz mumkin.':'Hisob yarating yoki mavjud profilingizga kiring. Barcha o‘yin tizimi shu Web App ichida ishlaydi.'}</div>
      <div class="start-features"><div><b>❤️</b><span>Qahramon</span><small>Statlaringizni rivojlantiring</small></div><div><b>💎</b><span>Arena</span><small>Kristallar bilan kuchaying</small></div><div><b>🏙️</b><span>Shahar</span><small>Hududlarni oching</small></div></div>
      <div class="field"><label>USERNAME</label><input id="authUser" autocomplete="username" placeholder="doniyor"></div>
      <div class="field"><label>PAROL</label><input id="authPass" type="password" autocomplete="current-password" placeholder="••••••••"></div>
      <div id="authErr" class="auth-err"></div>
      ${btn(S.authMode==='login'?'🚪 Kirish':'✨ Ro‘yxatdan o‘tish', 'submitAuth()', 'primary')}
      ${telegramMode?`<button class="secondary tg-primary" onclick="telegramQuickLogin()">✈️ Telegram orqali davom etish</button>`:''}
      <div class="switch-auth" onclick="toggleAuth()">${S.authMode==='login'?'Hisobingiz yo‘qmi? Ro‘yxatdan o‘ting':'Hisobingiz bormi? Kirish'}</div>
      <div class="tg-hint"><b>WEB APP:</b> Botdagi <b>/start</b> xabaridan <b>🎮 O‘YINNI BOSHLASH</b> tugmasini bossangiz, o‘yin Telegram ichida ochiladi.</div>
    </div>
    <div class="start-foot"><span>♙ 1 247 online</span><span>◉ Real-time o‘yin</span><span>◆ Bitta Web App</span><span>◈ 5 ta Arena stat</span></div>
  </div>`;
  document.getElementById('authPass')?.addEventListener('keydown',e=>{if(e.key==='Enter')submitAuth();});
}
function toggleAuth(){S.authMode=S.authMode==='login'?'register':'login';startView();}
async function submitAuth(){
  const username=document.getElementById('authUser')?.value?.trim()||'';const password=document.getElementById('authPass')?.value||'';const err=document.getElementById('authErr');
  err.textContent='';
  try{const data=await api(S.authMode==='login'?'/api/login':'/api/register',{method:'POST',body:JSON.stringify({username,password})}); S.token=data.token;localStorage.setItem('sc_token',S.token);S.me=data.user;await renderShell();showToast('Xush kelibsiz, '+data.user.username+'!');}
  catch(e){err.textContent=e.message;}
}
async function telegramQuickLogin(){
  if(!TG?.initData){showToast('Telegram Web App ichidan oching.');return;}
  try{const data=await api('/api/telegram/auth',{method:'POST',body:JSON.stringify({init_data:TG.initData})});S.token=data.token;localStorage.setItem('sc_token',S.token);S.me=data.user;await renderShell();showToast('Telegram orqali kirildi.');}
  catch(e){document.getElementById('authErr').textContent=e.message;}
}

async function loadMe(){S.me=await api('/api/me');}
function shell(){
  const p=PAGE_INFO[S.page]||PAGE_INFO.dashboard;
  document.getElementById('root').innerHTML=`<div class="shell">
    <aside class="sidebar"><div class="sidebar-brand"><div class="mark">♛</div><div class="brand-text"><b>SHADOW CITY</b><small>WEB RPG</small></div></div>
      <div class="mini-profile"><div class="avatar">${initials(S.me?.username)}</div><div class="mini-text"><b>${esc(S.me?.username||'Player')}</b><small>Lv.${S.me?.level||1} · ${S.me?.clan?esc(S.me.clan.name):'Klan yo‘q'}</small></div></div>
      <nav class="nav">${NAV.filter(([id])=>id!=='admin'||S.me?.is_admin).map(([id,ic,label])=>`<button class="${S.page===id?'active':''}" ${pageButton(id)}><span class="nav-ic">${ic}</span><span class="label">${label}</span></button>`).join('')}</nav>
      <div class="sidebar-foot"><button onclick="notifications()">🔔 <span class="label">Xabarlar</span></button><button onclick="logout()">⎋ <span class="label">Chiqish</span></button></div>
    </aside>
    <main class="main"><header class="topbar"><div><div class="crumb">${esc(p[0])}</div><h1>${esc(p[0])}</h1></div><div class="resources">
      <div class="resource">💵 <b>$${fmt(S.me?.money)}</b></div><div class="resource">💎 <b>${fmt(S.me?.diamonds)}</b></div><div class="resource">⚡ <b>${fmt(S.me?.energy)}/100</b></div><div class="resource">🔔</div><button class="resource" onclick="go('profile')">${initials(S.me?.username)}</button>
    </div></header><section class="content" id="content"></section></main>
  </div>`;
}
async function renderShell(){shell();await renderPage();}
async function go(page){S.page=page;shell();await renderPage();window.scrollTo({top:0,behavior:'smooth'});}
async function renderPage(){
  const c=document.getElementById('content'); if(!c)return;
  try{
    if(S.page==='dashboard')c.innerHTML=dashboardPage();
    else if(S.page==='map')c.innerHTML=mapPage();
    else if(S.page==='jobs')c.innerHTML=jobsPage();
    else if(S.page==='business')c.innerHTML=businessPage();
    else if(S.page==='transport')c.innerHTML=transportPage();
    else if(S.page==='arena')c.innerHTML=arenaPage();
    else if(S.page==='clans')c.innerHTML=await clansPage();
    else if(S.page==='missions')c.innerHTML=missionsPage();
    else if(S.page==='inventory')c.innerHTML=inventoryPage();
    else if(S.page==='shop')c.innerHTML=shopPage();
    else if(S.page==='leaderboard')c.innerHTML=await leaderboardPage();
    else if(S.page==='profile')c.innerHTML=profilePage();
    else if(S.page==='settings')c.innerHTML=settingsPage();
    else if(S.page==='admin')c.innerHTML=await adminPage();
  }catch(e){c.innerHTML=`<div class="card empty">${esc(e.message)}</div>`;}
}

function dashboardPage(){
  const xpNeed=S.me.level*100,pct=Math.min(100,Math.round(S.me.xp/xpNeed*100));
  const job=S.me.active_job;
  return `<div class="grid g4"><div class="card stat-card"><small>💵 PUL</small><b>$${fmt(S.me.money)}</b><span class="up">+2.4% today</span></div><div class="card stat-card"><small>💎 OLmos</small><b>${fmt(S.me.diamonds)}</b><span class="up">Premium</span></div><div class="card stat-card"><small>⚡ ENERGIYA</small><b>${fmt(S.me.energy)}/100</b><span class="up">+12 / 45s</span></div><div class="card stat-card"><small>★ REPUTATSIYA</small><b>${fmt(S.me.reputation)}</b><span class="muted">${S.me.reputation>0?'Ijobiy':'Neytral'}</span></div></div>
    <div class="grid g2" style="margin-top:14px"><div class="card hero-card"><div class="hero-content"><span class="eyebrow">SHADOW CITY</span><h2>Shaharga qadam qo‘ydingiz. Endi o‘z yo‘lingizni tanlang.</h2><p>Har bir qaror sizning daromadingiz, obro‘yingiz va kuchingizga ta’sir qiladi. Xarita orqali yangi joylarni oching.</p>${btn('Xaritaga o‘tish',`go('map')`)}</div></div>
    <div class="card"><div class="title"><div><h3>Bugungi voqealar</h3><p>Shahar yangiliklari</p></div><span class="pill">LIVE</span></div>${row('💵','Siz ${S.me.money} pulga egasiz','Bugungi balans', '$'+fmt(S.me.money))}${row('⚔️','Arena tayyor','Profil ichida 5 ta qobiliyat', '💎 '+fmt(S.me.arena_crystals))}${row('♜',S.me.clan?S.me.clan.name:'Klan topilmadi','Birga kuchliroqsiz',S.me.clan?'A’zo':'—')}</div></div>
    <div class="grid g3" style="margin-top:14px"><div class="card"><div class="title"><h3>Faol ish</h3></div>${job?row(JOBS[job.job_key]?.[0]||'💼',JOBS[job.job_key]?.[1]||job.job_key,'Faol ish',`$${fmt(job.reward)}`,btn('Mukofotni olish','claimJob()','green')):'<div class="empty">Hozircha faol ish yo‘q.</div>'}</div>
    <div class="card"><div class="title"><h3>Tajriba</h3><span class="price">Lv.${S.me.level}</span></div><div class="profile-head"><div class="avatar">${initials(S.me.username)}</div><div><b>${esc(S.me.username)}</b><p>Daraja ${S.me.level}</p></div></div><div class="xp"><div class="xp-bar"><i style="width:${pct}%"></i></div><small class="muted">${S.me.xp}/${xpNeed} XP</small></div></div>
    <div class="card"><div class="title"><h3>Tezkor bo‘limlar</h3></div>${row('⚔️','Arena','Jangga kirish','',btn('Ochish',`go('arena')`))}${row('🏪','Do‘kon','Buyumlar sotib olish','',btn('Ochish',`go('shop')`))}</div></div>`;
}
function mapPage(){
  const locs=[['home','🏠','Uy',12,20,''],['bank','🏦','Bank',35,18,'purple'],['mall','🛒','Savdo',58,27,'green'],['arena','⚔️','Arena',82,19,'purple'],['park','🌳','Park',23,52,'green'],['center','🏢','Markaz',49,49,''],['race','🏎️','Poyga',75,52,''],['clan','♜','Klan',61,79,'purple'],['service','🔧','Avtoservis',30,79,'green']];
  return `<div class="card"><div class="title"><div><h3>Shadow City xaritasi</h3><p>Joy tanlang va tashrif buyuring.</p></div><span class="pill">9 HUDUD</span></div><div class="map"><div class="road" style="top:40%;transform:rotate(16deg)"></div><div class="road" style="top:64%;transform:rotate(-13deg)"></div>${locs.map(l=>`<div class="node ${l[5]}" style="left:${l[3]}%;top:${l[4]}%" onclick="visit('${l[0]}')"><div class="bubble">${l[1]}</div><span>${l[2]}</span></div>`).join('')}<div class="map-label">📍 Tanlangan joyga boring — energiya va missiyalar ham hisobga olinadi.</div></div></div>`;
}
function jobsPage(){return `<div class="grid g3">${Object.entries(JOBS).map(([k,v])=>`<div class="card"><div class="cover">${v[0]}</div><div class="title"><h3>${v[1]}</h3><span class="price">${v[4]} min</span></div><p class="muted">Daromad: $${fmt(v[2])} — $${fmt(v[3])}</p><p class="muted">⚡ ${8+v[4]*4} energiya · XP ${15+v[4]*10}</p>${btn('Boshlash',`startJob('${k}')`,'green')}</div>`).join('')}</div>`;}
function businessPage(){return `<div class="grid g3">${Object.entries(BUSINESSES).map(([k,v])=>`<div class="card"><div class="cover">${v[0]}</div><div class="title"><h3>${v[1]}</h3><span class="price">$${fmt(v[2])}</span></div><p class="muted">Daromad: $${fmt(v[3])} / yig‘ish</p>${S.me.businesses.some(b=>b.business_key===k)?btn('Daromadni olish',`collectBusiness('${k}')`,'green'):btn('Sotib olish',`buyBusiness('${k}')`)}</div>`).join('')}</div>`;}
function transportPage(){return `<div class="grid g2">${Object.entries(VEHICLES).map(([k,v])=>{const owned=S.me.vehicles.find(x=>x.vehicle_key===k);return `<div class="card"><div class="grid" style="grid-template-columns:140px 1fr;gap:14px"><div class="cover" style="height:120px">${v[0]}</div><div><div class="title"><h3>${v[1]}</h3><span class="price">$${fmt(v[2])}</span></div><p class="muted">🚀 ${v[3]} km/h · +${v[4]} umumiy bonus</p>${owned?btn(owned.active?'Faol':'Tanlash',`activateVehicle('${k}')`,owned.active?'green':''):btn('Sotib olish',`buyVehicle('${k}')`)}</div></div></div>`}).join('')}</div>`;}
function arenaPage(){
  const stats=STAT_META; const a=S.me;
  return `<div class="grid g2"><div><div class="card arena-match"><div class="fighter"><div class="big-av">${initials(a.username)}</div><div class="meta"><b>${esc(a.username)}</b><small>❤️ ${a.arena_jon} · ⚔️ ${a.arena_kuch}</small><small>🎯 ${a.arena_topuvchanlik} · 💥 ${a.arena_zarba} · 🛡️ ${a.arena_chidamlilik}</small></div></div><div class="vs">VS</div><div class="fighter"><div class="big-av">?</div><div class="meta"><b>Raqib</b><small>Jon: ±9 matchmaking</small><small>Natija jang davomida aniqlanadi.</small></div></div></div><div class="card" style="margin-top:14px"><div class="title"><div><h3>Arena janglari</h3><p>Raqib Jon'i sizniki bilan ±9 oralig‘ida.</p></div><span class="pill">💎 ${fmt(a.arena_crystals)} KRISTALL</span></div><div class="grid g3">${[['❤️',a.arena_jon,'Jon'],['⚔️',a.arena_kuch,'Kuch'],['🎯',a.arena_topuvchanlik,'Topuvchanlik'],['💥',a.arena_zarba,'Zarba'],['🛡️',a.arena_chidamlilik,'Chidamlilik'],['🏆',a.wins+' / '+a.losses,'W / L']].map(x=>`<div class="card soft"><small class="muted">${x[0]} ${x[2]}</small><b style="display:block;font-size:19px;margin-top:7px">${x[1]}</b></div>`).join('')}</div>${btn('⚔️ Jangga kirish','arenaFight()','green full')}</div></div>
  <div class="card"><div class="title"><div><h3>Oxirgi janglar</h3><p>Tarix va mukofotlar</p></div></div>${loadArenaMatches(a)}</div></div>`;
}
function loadArenaMatches(a){
  // /api/arena is fetched lazily only for this page.
  return `<div id="arenaHistory"><div class="empty">Tarix yuklanmoqda…</div></div><script>setTimeout(loadArenaHistory,0)</script>`;
}
async function loadArenaHistory(){try{const a=await api('/api/arena');const el=document.getElementById('arenaHistory');if(!el)return;el.innerHTML=a.matches.length?a.matches.map(m=>row(m.won?'🏆':'✖️',m.opponent,`${m.rounds} raund · ${new Date(m.created_at*1000).toLocaleString()}`,`+$${fmt(m.reward)} · +${m.crystals} 💎`)).join(''):'<div class="empty">Hali jang yo‘q.</div>';}catch{}}
function missionsPage(){return `<div class="grid g2">${S.me.missions.map(m=>{const x=MISSIONS[m.mission_key]||[m.mission_key,0,m.target];const p=Math.min(100,Math.round((m.progress/m.target)*100));return `<div class="card">${row('◆',x[0],`${m.progress}/${m.target}`,m.claimed?'✅':'$'+fmt(x[1]),!m.claimed&&m.progress>=m.target?btn('Mukofotni olish',`claimMission('${m.mission_key}')`,'green'):'')}<div class="progress"><i style="width:${p}%"></i></div></div>`}).join('')}</div>`;}
async function clansPage(){const cs=await api('/api/clans');return `<div class="grid g2"><div class="card"><div class="title"><div><h3>Klan yaratish</h3><p>O‘z jamoangizni yarating.</p></div><span class="pill">30 A’ZO</span></div><div class="field"><label>NOM</label><input id="cn" placeholder="Night Wolves"></div><div class="field"><label>TAG</label><input id="ct" placeholder="WOLF"></div>${btn('Klan yaratish','createClan()','green')}</div><div class="card"><div class="title"><h3>Top klanlar</h3></div>${cs.length?cs.map((c,i)=>row('♜',`#${i+1} ${c.name}`,`${c.tag} · ${c.members}/30 a’zo`,`XP ${fmt(c.xp)}`,S.me.clan?'':btn('Qo‘shilish',`joinClan(${c.id})`))).join(''):'<div class="empty">Hali klan yo‘q.</div>'}</div></div>`;}
function inventoryPage(){const inv=Object.fromEntries(S.me.inventory.map(x=>[x.item_key,x.qty]));return `<div class="grid g3">${Object.entries(ITEMS).map(([k,v])=>`<div class="card"><div class="cover">${v[0]}</div><div class="title"><h3>${v[1]}</h3><span class="price">x${inv[k]||0}</span></div><p class="muted">${v[3]}</p>${inv[k]?btn('Ishlatish',`useItem('${k}')`,'green'):'<small class="muted">Inventarda yo‘q</small>'}</div>`).join('')}</div>`;}
function shopPage(){return `<div class="tabs"><button class="tab active">Barcha</button><button class="tab">Qurollar</button><button class="tab">Zirh</button><button class="tab">Oziq-ovqat</button><button class="tab">Boshqalar</button></div><div class="grid g3">${Object.entries(ITEMS).map(([k,v])=>`<div class="card"><div class="cover">${v[0]}</div><div class="title"><h3>${v[1]}</h3><span class="price">$${fmt(v[2])}</span></div><p class="muted">${v[3]}</p>${btn('Sotib olish',`buyItem('${k}')`)}</div>`).join('')}</div>`;}
async function leaderboardPage(){const j=await api('/api/leaderboard');return `<div class="card"><div class="title"><div><h3>Leaderboard</h3><p>Shaharning eng boy o‘yinchilari.</p></div><span class="pill">Siz #${j.me_rank}</span></div>${j.items.map((u,i)=>row(i<3?['🥇','🥈','🥉'][i]:'#'+(i+1),u.username,`Lv.${u.level} · ${u.wins}W / ${u.losses}L`,`$${fmt(u.money)}`,u.id===S.me.id?'<span class="pill">SIZ</span>':'')).join('')}</div>`;}
function profilePage(){
  const xpNeed=S.me.level*100,pct=Math.min(100,Math.round(S.me.xp/xpNeed*100));
  const stats=[['jon',S.me.arena_jon,''],['kuch',S.me.arena_kuch,''],['topuvchanlik',S.me.arena_topuvchanlik,''],['zarba',S.me.arena_zarba,''],['chidamlilik',S.me.arena_chidamlilik,'']];
  return `<div class="grid g2"><div class="card"><div class="profile-head"><div class="avatar">${initials(S.me.username)}</div><div><h2>${esc(S.me.username)}</h2><p>Lv.${S.me.level} · ${S.me.clan?esc(S.me.clan.name):'Klan yo‘q'}</p><div class="xp"><div class="xp-bar"><i style="width:${pct}%"></i></div><small class="muted">${S.me.xp}/${xpNeed} XP</small></div></div></div><div style="margin-top:16px">${row('💵','Pul','Asosiy balans','$'+fmt(S.me.money))}${row('💎','Kristallar','Arena qobiliyatlari uchun',fmt(S.me.arena_crystals))}${row('⭐','Obro‘','Reputatsiya',fmt(S.me.reputation))}${row('❤️','HP','Joriy / Maks',`${S.me.hp}/${S.me.max_hp}`)}</div></div>
  <div class="card"><div class="title"><div><h3>Arena qobiliyatlari</h3><p>Barchasi Profil ichida oshiriladi.</p></div><span class="pill">💎 ${fmt(S.me.arena_crystals)}</span></div>${stats.map(([k,v])=>{const m=STAT_META[k];return `<div class="arena-stat"><div class="stat-top"><div class="meta"><b>${m[0]} ${m[1]}</b><small>${m[2]}</small></div><strong>${v}</strong></div><div class="cost"><span>Keyingi +1 · kristall narxi o‘sib boradi</span>${btn('+1 · Profil ichida oshirish',`arenaUpgrade('${k}')`)}</div></div>`}).join('')}</div></div>
  <div class="card" style="margin-top:14px"><div class="title"><div><h3>Oddiy profil ko‘rsatkichlari</h3><p>Umumiy RPG statlari</p></div></div>${row('💪','Kuch','Umumiy jang kuchi',S.me.strength)}${row('🛡️','Himoya','Umumiy himoya',S.me.defense)}${row('⚡','Tezlik','Transport ko‘rsatkichi',S.me.speed)}</div>`;
}
function settingsPage(){const s=S.me.settings||{};return `<div class="grid g2"><div class="card"><div class="title"><div><h3>Profil</h3><p>Username'ni o‘zgartiring.</p></div></div><div class="field"><label>USERNAME</label><input id="newuser" value="${esc(S.me.username)}"></div>${btn('Saqlash','saveProfile()','green')}</div><div class="card"><div class="title"><div><h3>O‘yin</h3><p>Web App sozlamalari</p></div></div>${settingRow('🔊','Ovoz','sound',s.sound!==false)}${settingRow('🔔','Bildirishnomalar','notifications',s.notifications!==false)}${settingRow('🎨','Grafika','graphics',s.graphics!==false)}</div></div>`;}
function settingRow(icon,title,key,val){return row(icon,title,val?'Yoqilgan':'O‘chirilgan','',btn(val?'ON':'OFF',`toggleSetting('${key}')`,val?'green':'alt'));}
async function adminPage(){try{const j=await api('/api/admin');return `<div class="grid g4"><div class="card stat-card"><small>👥 USERS</small><b>${fmt(j.users)}</b></div><div class="card stat-card"><small>♜ KLANLAR</small><b>${fmt(j.clans)}</b></div><div class="card stat-card"><small>🟢 ONLINE</small><b>${fmt(j.online_sessions)}</b></div><div class="card stat-card"><small>💰 ECONOMY</small><b>$${fmt(j.economy_money)}</b></div></div><div class="card" style="margin-top:14px"><div class="title"><div><h3>Admin</h3><p>ADMIN_ID orqali boshqariladi.</p></div><span class="pill">SECURE</span></div>${row('🔐','Admin huquqi','Telegram ADMIN_ID bilan bog‘langan','ACTIVE')}</div>`;}catch(e){return `<div class="card empty">${esc(e.message)}</div>`;}}

async function startJob(k){try{await api('/api/jobs/start',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Ish boshlandi.');}catch(e){showToast(e.message)}}
async function claimJob(){try{const j=await api('/api/jobs/claim',{method:'POST'});await loadMe();await renderShell();showToast('+$'+fmt(j.reward)+' olindi!');}catch(e){showToast(e.message)}}
async function buyBusiness(k){try{await api('/api/businesses/buy',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Biznes sotib olindi.');}catch(e){showToast(e.message)}}
async function collectBusiness(k){try{const j=await api('/api/businesses/collect',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('+$'+fmt(j.income)+' biznes daromadi.');}catch(e){showToast(e.message)}}
async function buyVehicle(k){try{await api('/api/vehicles/buy',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Transport sotib olindi.');}catch(e){showToast(e.message)}}
async function activateVehicle(k){try{await api('/api/vehicles/activate',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Transport faollashtirildi.');}catch(e){showToast(e.message)}}
async function buyItem(k){try{await api('/api/shop/buy',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Sotib olindi.');}catch(e){showToast(e.message)}}
async function useItem(k){try{await api('/api/inventory/use',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Item ishlatildi.');}catch(e){showToast(e.message)}}
async function arenaFight(){
  try{const j=await api('/api/arena/fight',{method:'POST'});await loadMe();await renderShell();showBattle(j);}
  catch(e){showToast(e.message)}
}
function showBattle(j){
  const log=(j.battle_log||[]).map(x=>`<div class="log-line">${esc(x)}</div>`).join('');
  document.body.insertAdjacentHTML('beforeend',`<div class="modal" id="battleModal"><div class="modal-box"><div class="modal-head"><div><span class="pill">ARENA NATIJASI</span><h2 style="margin:10px 0 3px">${j.won?'🏆 G‘ALABA':'✖️ MAG‘LUBIYAT'}</h2><div class="muted">${esc(j.opponent)} · ${j.rounds} raund</div></div><button class="close" onclick="document.getElementById('battleModal')?.remove()">×</button></div><div class="grid g2" style="margin:14px 0"><div class="card soft"><small class="muted">Siz</small><h3 style="margin:5px 0">💚 ${j.user_hp_left}</h3><small>Power ${j.user_power}</small></div><div class="card soft"><small class="muted">Raqib</small><h3 style="margin:5px 0">💚 ${j.opponent_hp_left}</h3><small>Power ${j.opponent_power}</small></div></div><div class="battle-log">${log}</div><div class="actions" style="margin-top:12px"><span class="pill">+$${fmt(j.reward)}</span><span class="pill">+${j.crystals} 💎</span>${btn('Yopish',`document.getElementById('battleModal').remove()`,'green')}</div></div></div>`);
}
async function arenaUpgrade(stat){try{const j=await api('/api/arena/upgrade',{method:'POST',body:JSON.stringify({stat})});await loadMe();await renderShell();showToast(`${STAT_META[stat][1]} +1 · -${j.cost} 💎`);}catch(e){showToast(e.message)}}
async function visit(k){try{const j=await api('/api/location/'+k,{method:'POST'});await loadMe();await renderShell();showToast(j.message);}catch(e){showToast(e.message)}}
async function createClan(){try{await api('/api/clans/create',{method:'POST',body:JSON.stringify({name:document.getElementById('cn').value,tag:document.getElementById('ct').value})});await loadMe();await renderShell();showToast('Klan yaratildi!');}catch(e){showToast(e.message)}}
async function joinClan(id){try{await api('/api/clans/join',{method:'POST',body:JSON.stringify({clan_id:id})});await loadMe();await renderShell();showToast('Klan a’zosi bo‘ldingiz.');}catch(e){showToast(e.message)}}
async function claimMission(k){try{const j=await api('/api/missions/claim',{method:'POST',body:JSON.stringify({key:k})});await loadMe();await renderShell();showToast('Mukofot: +$'+fmt(j.reward));}catch(e){showToast(e.message)}}
async function saveProfile(){try{await api('/api/profile',{method:'POST',body:JSON.stringify({username:document.getElementById('newuser').value})});await loadMe();await renderShell();showToast('Profil saqlandi.');}catch(e){showToast(e.message)}}
async function toggleSetting(key){const s={...(S.me.settings||{})};s[key]=!s[key];try{await api('/api/settings',{method:'POST',body:JSON.stringify(s)});await loadMe();await renderShell();showToast('Sozlama yangilandi.');}catch(e){showToast(e.message)}}
async function notifications(){try{const n=await api('/api/notifications');const text=n.length?n.map(x=>'• '+x.text).join('\n'):'Xabarlar yo‘q.';alert(text);}catch(e){showToast(e.message)}}
async function logout(){await api('/api/logout',{method:'POST'}).catch(()=>{});localStorage.removeItem('sc_token');S.token=null;S.me=null;S.page='dashboard';startView();}

async function boot(){
  document.getElementById('boot')?.remove();
  if(S.token){try{await loadMe();await renderShell();return;}catch{localStorage.removeItem('sc_token');S.token=null;}}
  startView();
  if(TG?.initData){
    // Keep the cinematic start screen for a moment, then validate Telegram silently.
    try{const data=await api('/api/telegram/auth',{method:'POST',body:JSON.stringify({init_data:TG.initData})});S.token=data.token;localStorage.setItem('sc_token',S.token);S.me=data.user;await renderShell();showToast('Telegram orqali avtomatik kirildi.');}catch{}
  }
}
boot();
