import React, { useEffect, useState } from 'react'
import io from 'socket.io-client'

function App() {
  const [showId, setShowId] = useState(1)
  const [seats, setSeats] = useState([])

  useEffect(() => {
    const socket = io()
    socket.on('seat_update', data => {
      if (data.show_id === showId) loadSeats(showId)
    })
    loadSeats(showId)
    return () => socket.disconnect()
  }, [showId])

  async function loadSeats(id) {
    const res = await fetch(`/api/seats/${id}`)
    const j = await res.json()
    if (j.ok) setSeats(j.seats)
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>TicketFlow (React demo)</h2>
      <label>Show ID: <input value={showId} onChange={e => setShowId(Number(e.target.value))} /></label>
      <button onClick={() => loadSeats(showId)}>Load</button>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(10, 40px)`, gap: 6, marginTop: 12 }}>
        {seats.map(s => (
          <div key={s.seat_id} style={{ padding: 6, background: s.status === 'available' ? '#e6ffed' : s.status === 'held' ? '#fff5b1' : '#f8d7da' }}>
            {s.number}
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
