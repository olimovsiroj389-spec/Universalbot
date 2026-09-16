const TG=window.Telegram?.WebApp||null;

const S={
  initData:TG?.initData||"",
  home:null,
  current:null,
  selectedSeason:null
};

const $=q=>document.querySelector(q);
const $$=q=>[...document.querySelectorAll(q)];

function initTG(){
  try{
    TG?.ready();
    TG?.expand();
    TG?.setHeaderColor?.("#07070b");
    TG?.setBackgroundColor?.("#07070b");
  }catch(_){}
}

function headers(){
  return {
    "Content-Type":"application/json",
    ...(S.initData?{"X-Telegram-Init-Data":S.initData}:{})
  };
}

async function api(url,opt={}){
  const r=await fetch(url,{...opt,headers:{...headers(),...(opt.headers||{})}});
  let d={};
  try{d=await r.json()}catch(_){}
  if(!r.ok)throw new Error(d.error||"Server xatosi");
  return d;
}

function esc(v){
  return String(v??"").replace(/[&<>"']/g,m=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}

function toast(t){
  const el=$("#toast");
  el.textContent=t;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t=setTimeout(()=>el.classList.remove("show"),1900);
}

function showPage(name){
  $$(".page").forEach(x=>x.classList.remove("active"));
  const el=$(`#${name}Page`);
  if(el)el.classList.add("active");

  $$(".bottom .nav").forEach(x=>x.classList.remove("active"));
  const n=$(`.bottom .nav[data-page="${name}"]`);
  if(n)n.classList.add("active");

  window.scrollTo({top:0,behavior:"smooth"});

  if(name==="profile")loadProfile();
  if(name==="favorites")loadFavorites();
  if(name==="history")loadHistory();
  if(name==="pass")loadPass();
}

function card(a){
  return `
  <article class="anime-card" data-id="${a.id}">
    <div class="anime-poster">
      ${a.poster?`<img src="${esc(a.poster)}" loading="lazy" alt="${esc(a.title)}">`
      :`<div style="height:100%;display:grid;place-items:center;color:#747b8c;font-size:28px">A</div>`}
      <div class="rating">★ ${Number(a.rating||0).toFixed(2)}</div>
      ${a.premium?`<div class="premium">PREMIUM</div>`:""}
    </div>
    <div class="anime-body">
      <div class="anime-title">${esc(a.title)}</div>
      <div class="anime-sub">${a.year||"—"} • ${esc((a.genres||"").split(",")[0]||"Anime")}</div>
    </div>
  </article>`;
}

function render(el,items){
  el.innerHTML=items?.length?items.map(card).join(""):`<div class="empty">Hozircha ma’lumot yo‘q.</div>`;
}

async function loadHome(){
  $("#popularGrid").innerHTML=Array.from({length:5},()=>`<div class="skeleton"></div>`).join("");
  $("#newGrid").innerHTML=Array.from({length:5},()=>`<div class="skeleton"></div>`).join("");

  try{
    S.home=await api("/api/home");
    render($("#popularGrid"),S.home.popular);
    render($("#newGrid"),S.home.newest);
    render($("#catalogGrid"),S.home.catalog);
    drawGenres(S.home.genres||[]);
  }catch(e){toast(e.message)}
}

function drawGenres(items){
  const list=["Barchasi",...items];
  $("#genreChips").innerHTML=list.map((x,i)=>
    `<button class="chip ${i===0?"active":""}" data-genre="${esc(x)}">${esc(x)}</button>`
  ).join("");
}

async function search(q){
  q=String(q||"").trim();
  if(!q)return;
  showPage("search");
  $("#searchInput").value=q;
  $("#clearBtn").classList.remove("hidden");

  try{
    const d=await api(`/api/search?q=${encodeURIComponent(q)}`);
    $("#resultCount").textContent=`${d.items.length} ta`;
    render($("#searchGrid"),d.items);
  }catch(e){toast(e.message)}
}

async function openAnime(id){
  try{
    const d=await api(`/api/anime/${id}`);
    S.current=d;

    const a=d.anime;
    $("#detailCover").innerHTML=a.banner?`<img src="${esc(a.banner)}">`
      :(a.poster?`<img src="${esc(a.poster)}">`:"");

    $("#detailPoster").innerHTML=a.poster?`<img src="${esc(a.poster)}">`
      :`<div style="height:100%;display:grid;place-items:center;color:#7d8390;font-size:28px">A</div>`;

    $("#detailTitle").textContent=a.title;
    $("#detailInfo").textContent=
      `★ ${Number(a.rating||0).toFixed(2)} • ${a.year||"—"} • ${a.status||"ongoing"}\n${a.genres||"Janr yo‘q"}\n${a.studio||""}`;
    $("#detailDesc").textContent=a.description||"Tavsif kiritilmagan.";

    $("#seasonTabs").innerHTML=d.seasons.map((s,i)=>
      `<button class="season-tab ${i===0?"active":""}" data-season="${s.id}">
        ${esc(s.title||`${s.number}-fasl`)}
      </button>`
    ).join("");

    renderEpisodes(d,d.seasons[0]?.id);
    await related(id);

    $("#detailModal").classList.add("show");
  }catch(e){toast(e.message)}
}

function renderEpisodes(d,seasonId){
  S.selectedSeason=seasonId;
  const list=d.episodes.filter(e=>Number(e.season_id)===Number(seasonId));

  $("#episodeList").innerHTML=list.length?list.map(e=>`
    <div class="episode-row">
      <div class="episode-no">${e.number}</div>
      <div class="episode-copy">
        <div class="episode-title">${esc(e.title||`${e.number}-qism`)}</div>
        <div class="episode-sub">${e.premium?"Premium":"Tomosha qilish"}</div>
      </div>
      <button class="ep-btn ${e.premium?"locked":""}" data-episode="${e.id}">
        ${e.premium?"✦":"▶"}
      </button>
    </div>
  `).join(""):`<div class="empty">Bu faslda qism yo‘q.</div>`;
}

async function related(id){
  try{
    const d=await api(`/api/anime/${id}/related`);
    render($("#relatedGrid"),d.items);
  }catch(_){$("#relatedGrid").innerHTML=""}
}

async function loadProfile(){
  try{
    const d=await api("/api/profile");
    const u=d.user;
    $("#profileName").textContent=u.first_name||"Mehmon";
    $("#profileUsername").textContent=u.username?`@${u.username}`:"@guest";
    $("#avatar").textContent=(u.first_name||"A").slice(0,1).toUpperCase();
    $("#watched").textContent=u.total_watched||0;
    $("#favs").textContent=u.favorites||0;
    $("#refs").textContent=u.referrals||0;
  }catch(e){toast(e.message)}
}

async function loadFavorites(){
  showPageRaw("favorites");
  try{
    const d=await api("/api/favorites");
    render($("#favoritesGrid"),d.items);
  }catch(e){toast(e.message)}
}

async function loadHistory(){
  showPageRaw("history");
  try{
    const d=await api("/api/history");
    $("#historyList").innerHTML=d.items.length?d.items.map(x=>`
      <div class="episode-row">
        <div class="episode-no">${x.episode_number}</div>
        <div class="episode-copy">
          <div class="episode-title">${esc(x.title)}</div>
          <div class="episode-sub">Davom ettirish</div>
        </div>
        <button class="ep-btn" data-episode="${x.episode_id}">▶</button>
      </div>
    `).join(""):`<div class="empty">Tarix bo‘sh.</div>`;
  }catch(e){toast(e.message)}
}

function showPageRaw(name){
  $$(".page").forEach(x=>x.classList.remove("active"));
  $(`#${name}Page`)?.classList.add("active");
  $$(".bottom .nav").forEach(x=>x.classList.remove("active"));
  $(`.bottom .nav[data-page="${name}"]`)?.classList.add("active");
  window.scrollTo({top:0});
}

async function loadPass(){
  try{
    const d=await api("/api/pass");
    showPageRaw("pass");
    $("#passStatus").textContent=d.active
      ?"✓ Pass faol"
      :"Pass faol emas";

    $("#plans").innerHTML=d.plans.map((p,i)=>`
      <div class="plan ${i===2?"highlight":""}">
        <div class="plan-copy">
          <div class="plan-title">${esc(p.title)}</div>
          <div class="plan-price">⭐ ${p.stars} Telegram Stars</div>
          ${i===2?`<div class="plan-note">Ommabop</div>`:""}
        </div>
        <button data-plan="${p.days}">Sotib olish</button>
      </div>
    `).join("");
  }catch(e){toast(e.message)}
}

async function toggleFavorite(){
  if(!S.current?.anime?.id)return;
  try{
    const d=await api("/api/favorite",{
      method:"POST",
      body:JSON.stringify({anime_id:S.current.anime.id})
    });
    toast(d.added?"❤️ Sevimliga qo‘shildi":"💔 Sevimlilardan olindi");
  }catch(e){toast(e.message)}
}

async function openEpisode(id){
  try{
    const d=await api(`/api/episode/${id}`);
    $("#playerTitle").textContent=d.title||`${d.number}-qism`;

    if(d.media_url){
      $("#playerBox").innerHTML=`
        <div>
          <div>Ruxsat etilgan media manzili mavjud.</div>
          <a href="${esc(d.media_url)}" target="_blank" rel="noopener">▶ Tomosha qilish</a>
        </div>`;
    }else if(d.file_id && d.bot_url){
      $("#playerBox").innerHTML=`
        <div>
          <div>Episode Telegram fayli sifatida saqlangan.</div>
          <a href="${esc(d.bot_url)}">↗ Telegramda ochish</a>
        </div>`;
    }else{
      $("#playerBox").innerHTML=`<div>📭 Media hali ulanmagan.</div>`;
    }

    $("#playerModal").classList.add("show");
  }catch(e){toast(e.message)}
}

function closeModal(name){
  const el=name==="detail"?$("#detailModal"):$("#playerModal");
  el.classList.remove("show");
}

async function filterGenre(g){
  if(g==="Barchasi"){
    render($("#catalogGrid"),S.home?.catalog||[]);
    return;
  }
  try{
    const d=await api(`/api/search?q=${encodeURIComponent(g)}`);
    render($("#catalogGrid"),d.items);
  }catch(e){toast(e.message)}
}

function bind(){
  document.addEventListener("click",async e=>{
    const cardEl=e.target.closest(".anime-card");
    if(cardEl){
      openAnime(Number(cardEl.dataset.id));
      return;
    }

    const pageBtn=e.target.closest("[data-page]");
    if(pageBtn){
      const p=pageBtn.dataset.page;
      if(p==="home")showPage("home");
      else if(p==="search")showPage("search");
      else if(p==="catalog")showPage("catalog");
      else if(p==="favorites")loadFavorites();
      else if(p==="history")loadHistory();
      else if(p==="profile"){showPage("profile");loadProfile()}
      else if(p==="pass")loadPass();
      return;
    }

    const close=e.target.closest("[data-close]");
    if(close){closeModal(close.dataset.close);return;}

    const season=e.target.closest("[data-season]");
    if(season){
      $$(".season-tab").forEach(x=>x.classList.remove("active"));
      season.classList.add("active");
      renderEpisodes(S.current,Number(season.dataset.season));
      return;
    }

    const ep=e.target.closest("[data-episode]");
    if(ep){openEpisode(Number(ep.dataset.episode));return;}

    const genre=e.target.closest("[data-genre]");
    if(genre){
      $$(".chip").forEach(x=>x.classList.remove("active"));
      genre.classList.add("active");
      filterGenre(genre.dataset.genre);
      return;
    }

    const plan=e.target.closest("[data-plan]");
    if(plan){
      const days=Number(plan.dataset.plan);
      // Telegram invoice is opened by a Web App callback mechanism.
      // The easiest standard-library-only route is to ask the bot to send
      // the invoice to this chat through Telegram's bot API is not available
      // directly from the browser, so we deep-link to the bot.
      const url=`https://t.me/${window.BOT_USERNAME||""}?start=buy_${days}`;
      try{
        if(TG?.openTelegramLink && window.BOT_USERNAME){
          TG.openTelegramLink(url);
        }else{
          toast("Bot orqali Pass bo‘limini oching.");
        }
      }catch(_){
        toast("Bot orqali Pass bo‘limini oching.");
      }
      return;
    }
  });

  $("#searchBtn").addEventListener("click",()=>search($("#searchInput").value));
  $("#searchInput").addEventListener("keydown",e=>{if(e.key==="Enter")search(e.target.value)});
  $("#searchInput").addEventListener("input",e=>$("#clearBtn").classList.toggle("hidden",!e.target.value));
  $("#clearBtn").addEventListener("click",()=>{
    $("#searchInput").value="";
    $("#clearBtn").classList.add("hidden");
    $("#searchInput").focus();
  });

  $("#profileBtn").addEventListener("click",()=>{
    showPage("profile");
    loadProfile();
  });

  $("#favDetail").addEventListener("click",toggleFavorite);
  $("#shareDetail").addEventListener("click",async()=>{
    const a=S.current?.anime;
    if(!a)return;
    try{
      if(navigator.share)await navigator.share({title:a.title,text:a.title});
      else{
        await navigator.clipboard.writeText(a.title);
        toast("Nusxalandi");
      }
    }catch(_){}
  });
}

async function loadMeta(){
  try{
    const d=await api("/api/meta");
    window.BOT_USERNAME=d.bot_username||"";
  }catch(_){}
}

async function boot(){
  initTG();
  bind();
  await loadMeta();
  await loadHome();
}

boot();
