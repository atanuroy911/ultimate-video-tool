document.getElementById('address').textContent=location.origin;
fetch('/api/server').then(r=>r.ok?r.json():null).then(info=>{if(info?.addresses)document.getElementById('address').textContent=info.addresses.join(' · ');}).catch(()=>{});
