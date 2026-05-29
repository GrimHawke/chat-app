import { useState, useEffect } from 'react'
import { io, Socket } from 'socket.io-client'
import './App.css'
import { LandingPage } from './LandingPage'
import { RoomJoinForm } from './RoomJoinForm'
import { ChatRoom } from './ChatRoom'

type AppState = 'landing' | 'join-room' | 'chat'

function App() {
  const [state, setState] = useState<AppState>('landing')
  const [socket, setSocket] = useState<Socket | null>(null)
  const [roomCode, setRoomCode] = useState('')
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [isLoadingLanding, setIsLoadingLanding] = useState(false)

  // Clean up socket on unmount or when leaving chat
  useEffect(() => {
    return () => {
      if (socket && state !== 'chat') {
        socket.disconnect()
        setSocket(null)
      }
    }
  }, [state, socket])

  // Auto-clear error after 10 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => {
        setError('')
      }, 10000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const handleCreateRoom = async () => {
    try {
      setError('')
      setIsLoadingLanding(true)
      const response = await fetch('http://localhost:5000/api/rooms/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
      const data = await response.json()
      if (data.code) {
        setRoomCode(data.code)
        setIsLoadingLanding(false)
        setState('join-room')
      } else {
        setError('Failed to create room')
        setIsLoadingLanding(false)
      }
    } catch (err) {
      setError('Failed to connect to server')
      setIsLoadingLanding(false)
      console.error(err)
    }
  }

  const handleJoinRoomClick = () => {
    setRoomCode('')
    setState('join-room')
  }

  const handleJoinRoom = async (code: string, user: string) => {
    try {
      setError('')
      setIsLoadingLanding(true)
      // Validate room exists
      const response = await fetch(`http://localhost:5000/api/rooms/${code}/validate`)
      const data = await response.json()
      if (!data.exists) {
        setError('Room not found')
        setIsLoadingLanding(false)
        return
      }
      setRoomCode(code)
      setUsername(user)
      setIsLoadingLanding(false)
      
      // Set state to chat BEFORE establishing connection
      setState('chat')
      
      // Create Socket.io connection with room code and username as query params
      const newSocket = io('http://localhost:5000', {
        query: {
          roomCode: code,
          username: user
        },
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5
      })

      setSocket(newSocket)
    } catch (err) {
      setError('Failed to validate room')
      setIsLoadingLanding(false)
      console.error(err)
    }
  }

  const handleExit = () => {
    // Close socket connection when exiting
    if (socket) {
      socket.disconnect()
      setSocket(null)
    }
    setState('landing')
    setRoomCode('')
    setUsername('')
    setError('')
  }

  return (
    <>
      {state === 'landing' && (
        <>
          {error && <div className="error-banner">{error}</div>}
          <LandingPage 
            isLoading={isLoadingLanding}
            onCreateRoom={handleCreateRoom} 
            onJoinRoom={handleJoinRoomClick} 
          />
        </>
      )}
      {state === 'join-room' && (
        <>
          {error && <div className="error-banner">{error}</div>}
          <RoomJoinForm
            roomCode={roomCode}
            isLoading={isLoadingLanding}
            onJoin={handleJoinRoom}
            onBack={() => setState('landing')}
          />
        </>
      )}
      {state === 'chat' && socket && (
        <ChatRoom
          roomCode={roomCode}
          username={username}
          onExit={handleExit}
          socket={socket}
        />
      )}
    </>
  )
}

export default App
