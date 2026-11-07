document.addEventListener("DOMContentLoaded",()=>{
 const search=document.getElementById("playerSearch");
 if(search){search.addEventListener("input",()=>{const q=search.value.toLowerCase();document.querySelectorAll("#playerTable tbody tr[data-search]").forEach(r=>r.style.display=r.dataset.search.includes(q)?"":"none")})}
 document.querySelectorAll(".flash").forEach(el=>{setTimeout(()=>{el.style.opacity="0";el.style.transform="translateY(-5px)"},4500);setTimeout(()=>el.remove(),5000)})
});
const fmt=document.getElementById('formatSelect');
const groupWrap=document.getElementById('groupCountWrap');
if(fmt&&groupWrap){const sync=()=>groupWrap.style.display=['groups_knockout','league_playoff'].includes(fmt.value)?'grid':'none';fmt.addEventListener('change',sync);sync()}
