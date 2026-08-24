// Single-page frontend for Ticket Booking Demo
(function(){
  let token = null;
  let currentUser = { id: null, name: null, role: null };
  let socket = null;
  let currentShowId = null;
  let held = null; // { hold_id, seat_id, expires_at }

  // helpers
  function el(id){ return document.getElementById(id) }
  function q(sel, ctx=document){ return ctx.querySelector(sel) }

  function showView(name){
    document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));
    const node = document.getElementById('view-'+name);
    if(node) node.classList.remove('hidden');
    updateUserBar();
  }

  function api(path, opts={}){
    opts.headers = opts.headers || {};
    if(token) opts.headers['Authorization'] = 'Bearer '+token;
    return fetch(path, opts).then(r=>r.json().then(j=>({ok:r.ok, status:r.status, data:j}))).catch(e=>({ok:false, error:e}));
  }

  function updateUserBar(){
    const bar = el('user-bar');
    // hide organiser/admin nav buttons by default
    document.querySelectorAll('[data-view="organiser"], [data-view="admin"]').forEach(b=>b.style.display = 'none');
    if(token && currentUser && currentUser.id){
      bar.innerHTML = `Logged in: ${currentUser.name||('User '+currentUser.id)} (${currentUser.role||'unknown'}) <button id="logout-btn">Logout</button>`;
      // show role-specific nav
      if(currentUser.role === 'organiser' || currentUser.role === 'admin') document.querySelector('[data-view="organiser"]').style.display = '';
      if(currentUser.role === 'admin') document.querySelector('[data-view="admin"]').style.display = '';
      const logoutBtn = q('#logout-btn');
      if(logoutBtn) logoutBtn.addEventListener('click', ()=>{ token=null; currentUser={}; held=null; showView('auth'); renderSeats(null); updateUserBar(); });
    } else {
      bar.textContent = 'Not logged in';
    }
  }

  // auth
  function initAuth(){
    el('login-form').addEventListener('submit', async e=>{
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = { email: fd.get('email'), password: fd.get('password') };
      const res = await api('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(res.ok){ token = res.data.access_token;
        // fetch user info from /api/me
        const me = await api('/api/me');
        if(me.ok && me.data && me.data.user){ currentUser = me.data.user; }
        showView('customer'); initSocket(); loadEvents(); loadBookings(); updateUserBar();
      } else alert('Login failed');
    });

    el('register-form').addEventListener('submit', async e=>{
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = { name: fd.get('name'), email: fd.get('email'), password: fd.get('password'), role: fd.get('role') };
      const res = await api('/api/register', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(res.ok){ alert('Registered -- now log in'); } else alert('Register failed');
    });
  }

  // events & seats
  async function loadEvents(){
    const res = await api('/api/events');
    const sel = el('events-list'); sel.innerHTML='';
    if(res.ok){ res.data.events.forEach(ev=>{ const o=document.createElement('option'); o.value=ev.show_id; o.textContent = `${ev.event_name} @ ${ev.venue || ''} (${ev.start_at})`; sel.appendChild(o); }); }
  }

  el('load-show').addEventListener('click', ()=>{
    const sel = el('events-list'); if(!sel.value) return alert('Select an event'); currentShowId = sel.value; renderSeats(currentShowId);
  });

  async function renderSeats(showId){
    const map = el('seat-map'); map.innerHTML = '';
    if(!showId) return;
    const res = await api('/api/seats/'+showId);
    if(!res.ok) return map.textContent = 'Failed to load seats';
    const seats = res.data.seats;
    // approximate grid by max row/number
    let maxRow = 0, maxNum=0;
    seats.forEach(s=>{ maxRow = Math.max(maxRow, parseInt(s.row)); maxNum = Math.max(maxNum, s.number); });
    map.style.gridTemplateColumns = `repeat(${maxNum}, 44px)`;
    seats.forEach(s=>{
      const d = document.createElement('div'); d.className = 'seat ' + (s.status==='available' ? 'available' : (s.status==='held' ? 'held' : 'booked'));
      if(s.status !== 'available') d.classList.add('disabled');
      d.dataset.seatId = s.seat_id;
      d.dataset.row = s.row;
      d.dataset.number = s.number;
      d.textContent = s.number;
      d.addEventListener('click', ()=>onSeatClick(s));
      map.appendChild(d);
    });
  }

  async function onSeatClick(s){
    if(!token) return alert('Please log in');
    if(s.status !== 'available') return;
    const res = await api('/api/hold_seat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ show_id: currentShowId, seat_id: s.seat_id }) });
    if(res.ok){ held = { hold_id: res.data.hold_id, seat_id: s.seat_id, expires_at: res.data.expires_at }; el('hold-info').classList.remove('hidden'); el('held-seat').textContent = `Row ${s.row} #${s.number}`; startHoldTimer(); renderSeats(currentShowId); }
    else if(res.status==409) alert('Seat unavailable'); else alert('Hold failed');
  }

  function startHoldTimer(){
    if(!held) return;
    const ttlNode = el('hold-ttl');
    function tick(){
      const exp = new Date(held.expires_at).getTime(); const now = Date.now(); const sec = Math.max(0, Math.floor((exp-now)/1000)); ttlNode.textContent = sec + 's'; if(sec<=0){ clearInterval(interval); held=null; el('hold-info').classList.add('hidden'); renderSeats(currentShowId); }}
    tick(); const interval = setInterval(tick, 1000);
  }

  el('confirm-book').addEventListener('click', async ()=>{
    if(!held) return alert('No hold');
    const res = await api('/api/book', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hold_id: held.hold_id }) });
    if(res.ok){ alert('Booked: '+res.data.booking_ref); held=null; el('hold-info').classList.add('hidden'); renderSeats(currentShowId); loadBookings(); } else alert('Booking failed');
  });

  // bookings
  async function loadBookings(){
    const res = await api('/api/bookings'); const box = el('my-bookings'); box.innerHTML='';
    if(!res.ok) return box.textContent = 'Failed to load';
    res.data.bookings.forEach(b=>{ const div=document.createElement('div'); div.className='booking'; div.innerHTML = `<strong>${b.event_name}</strong> Row ${b.row} #${b.number} <button data-id="${b.booking_id}">Cancel</button>`; div.querySelector('button').addEventListener('click', ()=>cancelBooking(b.booking_id)); box.appendChild(div); });
  }

  async function cancelBooking(id){ const res = await api('/api/cancel_booking', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ booking_id: id }) }); if(res.ok){ alert('Cancelled'); loadBookings(); renderSeats(currentShowId); } else alert('Cancel failed'); }

  // waitlist
  async function joinWaitlist(show_id, category){ const res = await api('/api/join_waitlist', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ show_id, category }) }); if(res.ok) alert('Joined waitlist'); else alert('Failed to join waitlist'); }

  // organiser/admin forms
  function initOrganiser(){
    el('venue-form').addEventListener('submit', async e=>{ e.preventDefault(); const fd=new FormData(e.target); const body={ name: fd.get('name'), rows: parseInt(fd.get('rows')), cols: parseInt(fd.get('cols')) }; const res=await api('/api/venues',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }); if(res.ok) alert('Venue created: '+res.data.venue_id); else alert('Failed'); });

    el('show-form').addEventListener('submit', async e=>{ e.preventDefault(); const fd=new FormData(e.target); const cat = fd.get('category_prices') || ''; const obj={}; cat.split(',').map(p=>p.trim()).filter(Boolean).forEach(kv=>{ const [k,v]=kv.split(':'); if(k&&v) obj[k.trim()]=parseFloat(v); }); const body={ event_name: fd.get('event_name'), venue_id: parseInt(fd.get('venue_id')), start_at: fd.get('start_at'), category_prices: obj }; const res=await api('/api/shows',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }); if(res.ok) alert('Show created: '+res.data.show_id); else alert('Failed'); });

    el('load-summary').addEventListener('click', async ()=>{ const id = el('summary-show-id').value; if(!id) return alert('Enter show id'); const res = await api('/api/organiser/summary/'+id); if(res.ok) el('summary-result').textContent = JSON.stringify(res.data); else el('summary-result').textContent = 'Failed'; });
  }

  // socket
  function initSocket(){ if(socket) return; try{ socket = io(); socket.on('connect', ()=>console.log('socket connected')); socket.on('seat_update', data=>{ if(data.show_id == currentShowId) renderSeats(currentShowId); }); }catch(e){ console.warn('Socket init failed', e); } }

  // nav
  document.querySelectorAll('.nav-btn').forEach(b=>b.addEventListener('click', ()=>{ showView(b.dataset.view); }));

  // init
  initAuth(); initOrganiser(); showView('auth'); updateUserBar();

})();
