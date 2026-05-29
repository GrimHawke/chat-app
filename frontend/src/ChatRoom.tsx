import { useState, useEffect, useRef } from 'react'
import './ChatRoom.css'

interface Message {
  username: string
  message: string
  timestamp: number
  isSystemMessage?: boolean
}

interface User {
  socket_id: string
  username: string
}

interface ChatRoomProps {
  roomCode: string
  username: string
  onExit: () => void
  socket: any
}

export function ChatRoom({ roomCode, username, onExit, socket }: ChatRoomProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState('')
  const [isReconnecting, setIsReconnecting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasInitializedRef = useRef(false)
  const previousUserCountRef = useRef(0)

  useEffect(() => {
    if (!socket) return

    // Handle successful connection
    const handleConnect = () => {
      console.log('Connected to server')
      setIsConnected(true)
      setConnectionError('')
      setIsReconnecting(false)
    }

    // Handle connection error
    const handleError = (data: any) => {
      const errorMsg = data?.message || 'Connection failed'
      setConnectionError(errorMsg)
      setIsConnected(false)
      console.error('Socket error:', errorMsg)
    }

    // Handle disconnect
    const handleDisconnect = () => {
      console.log('Disconnected from server')
      setIsConnected(false)
      setConnectionError('Connection lost. Attempting to reconnect...')
      setIsReconnecting(true)
    }

    // Handle reconnect attempt
    const handleReconnectAttempt = () => {
      setIsReconnecting(true)
      setConnectionError('Attempting to reconnect...')
    }

    // Handle reconnection failure
    const handleReconnectFailed = () => {
      setIsReconnecting(false)
      setConnectionError('Failed to reconnect. Please try again.')
    }

    // Listen for message history on initial connect
    socket.on('message_history', (data: any) => {
      if (data.messages && Array.isArray(data.messages)) {
        setMessages(data.messages)
      }
    })

    // Listen for messages
    socket.on('message', (data: any) => {
      setMessages((prev) => [...prev, {
        username: data.username,
        message: data.message,
        timestamp: data.timestamp
      }])
    })

    // Listen for user joined
    socket.on('user_joined', (data: any) => {
      if (data.users) {
        const currentUserCount = data.users.length
        
        // On initial connection, track user count but don't show system message
        if (!hasInitializedRef.current) {
          hasInitializedRef.current = true
          previousUserCountRef.current = currentUserCount
        } else if (currentUserCount > previousUserCountRef.current) {
          // Another user joined - find who it is and add system message
          const newUsers = data.users.filter(
            (user: User) => !users.some((u) => u.socket_id === user.socket_id)
          )
          
          // Add system message for each new user
          newUsers.forEach((newUser: User) => {
            if (newUser.username !== username) {
              setMessages((prev) => [...prev, {
                username: newUser.username,
                message: 'joined the chat',
                timestamp: Math.floor(Date.now() / 1000),
                isSystemMessage: true
              }])
            }
          })
        }
        
        setUsers(data.users)
        previousUserCountRef.current = currentUserCount
      }
      if (data.status === 'success') {
        setConnectionError('')
      }
    })

    // Listen for user left
    socket.on('user_left', (data: any) => {
      const { username: leftUsername, users: updatedUsers } = data
      if (updatedUsers) {
        setUsers(updatedUsers)
      }
      // Add system message about user leaving
      setMessages((prev) => [...prev, {
        username: leftUsername,
        message: 'left the chat',
        timestamp: Math.floor(Date.now() / 1000),
        isSystemMessage: true
      }])
    })

    // Listen for room users
    socket.on('room_users', (data: any) => {
      if (data.users) {
        setUsers(data.users)
      }
    })

    // Listen for connection states
    socket.on('connect', handleConnect)
    socket.on('disconnect', handleDisconnect)
    socket.on('reconnect_attempt', handleReconnectAttempt)
    socket.on('reconnect_failed', handleReconnectFailed)
    socket.on('error', handleError)

    return () => {
      socket.off('message_history')
      socket.off('message')
      socket.off('user_joined')
      socket.off('user_left')
      socket.off('room_users')
      socket.off('connect', handleConnect)
      socket.off('disconnect', handleDisconnect)
      socket.off('reconnect_attempt', handleReconnectAttempt)
      socket.off('reconnect_failed', handleReconnectFailed)
      socket.off('error', handleError)
    }
  }, [socket, roomCode, username])

  useEffect(() => {
    // Auto-scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // Handle page unload to properly disconnect
    const handleBeforeUnload = () => {
      if (socket && isConnected) {
        socket.disconnect()
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [socket, isConnected])

  useEffect(() => {
    // Handle browser back button to return to main screen
    window.history.pushState({ type: 'chatRoom' }, '', window.location.href)

    const handlePopState = () => {
      // Disconnect socket and exit chat
      if (socket) {
        socket.disconnect()
      }
      onExit()
    }

    window.addEventListener('popstate', handlePopState)
    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [socket, onExit])

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim() && socket && isConnected) {
      socket.emit('send_message', {
        room: roomCode,
        message: inputValue,
        username: username
      })
      setInputValue('')
    }
  }

  const handleReconnect = () => {
    if (socket) {
      setIsReconnecting(true)
      setConnectionError('Attempting to reconnect...')
      socket.connect()
    }
  }

  const handleExit = () => {
    if (socket) {
      socket.disconnect()
    }
    onExit()
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="room-info">
          <h2>{roomCode}</h2>
          <p className="connection-status">
            {isConnected ? '🟢 Connected' : isReconnecting ? '🟡 Reconnecting...' : '🔴 Disconnected'}
          </p>
        </div>
        <button className="exit-btn" onClick={handleExit}>
          ✕
        </button>
      </div>

      {connectionError && (
        <div className="connection-error-banner">
          <div className="error-content">
            <span className="error-message">{connectionError}</span>
            {!isConnected && !isReconnecting && (
              <div className="error-actions">
                <button className="reconnect-btn" onClick={handleReconnect}>
                  Reconnect
                </button>
                <button className="exit-error-btn" onClick={handleExit}>
                  Go Home
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="chat-content">
        <div className="messages-section">
          <div className="messages-list">
            {messages.length === 0 ? (
              <div className="empty-state">
                <p>No messages yet. Start the conversation!</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`message ${msg.isSystemMessage ? 'system-message' : msg.username === username ? 'own-message' : ''}`}
                >
                  {msg.isSystemMessage ? (
                    <div className="system-message-content">
                      <span className="system-text">{msg.username} {msg.message}</span>
                    </div>
                  ) : (
                    <>
                      <div className="message-header">
                        <span className="username">
                          {msg.username}
                          {msg.username === username && <span className="you-label"> (You)</span>}
                        </span>
                        <span className="timestamp">{formatTime(msg.timestamp)}</span>
                      </div>
                      <div className="message-text">{msg.message}</div>
                    </>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="users-section">
          <h3>Users ({users.length})</h3>
          <div className="users-list">
            {users.map((user) => (
              <div key={user.socket_id} className="user-item">
                <span className="user-badge">👤</span>
                <span className="user-name">{user.username}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="chat-footer">
        <form onSubmit={handleSendMessage} className="message-form">
          <input
            type="text"
            placeholder="Type a message..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            maxLength={500}
            disabled={!isConnected}
          />
          <button type="submit" disabled={!isConnected || !inputValue.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
