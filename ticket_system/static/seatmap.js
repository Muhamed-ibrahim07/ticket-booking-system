const seatmap = document.getElementById('seatmap')
const loadBtn = document.getElementById('load')

function renderSeats(seats) {
  seatmap.innerHTML = ''
  // simple grid: compute cols
  const cols = Math.max(...seats.map(s => s.number || 1))
  seatmap.style.gridTemplateColumns = `repeat(${cols}, 40px)`
  seats.forEach(s => {
    const d = document.createElement('div')
    d.className = 'seat ' + s.status
    d.textContent = s.number
    d.dataset.seatId = s.seat_id
    d.onclick = () => alert('Clicked seat ' + s.seat_id + ' status=' + s.status)
    seatmap.appendChild(d)
  })
}

async function load(showId) {
  const res = await fetch(`/api/seats/${showId}`)
  const j = await res.json()
  if (j.ok) renderSeats(j.seats)
}

loadBtn.onclick = () => load(document.getElementById('showId').value)

// socket
const socket = io({ transports: ['websocket'] })
socket.on('connect', () => console.log('socket connected'))
socket.on('seat_update', data => {
  console.log('seat_update', data)
  // refresh seats for that show
  const showId = document.getElementById('showId').value
  if (String(data.show_id) === String(showId)) load(showId)
})

// initial load
load(document.getElementById('showId').value)
