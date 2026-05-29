import { useState } from 'react'
import './RoomJoinForm.css'

interface RoomJoinFormProps {
  roomCode?: string
  isLoading: boolean
  onJoin: (code: string, username: string) => void
  onBack: () => void
}

export function RoomJoinForm({ roomCode = '', isLoading, onJoin, onBack }: RoomJoinFormProps) {
  const [copied, setCopied] = useState(false)
  const [username, setUsername] = useState('')
  const [code, setCode] = useState(roomCode)

  const isCreating = !!roomCode

  const handleCopyCode = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault()
    if (username.trim() && code.trim()) {
      onJoin(code.toUpperCase(), username)
    }
  }

  return (
    <div className="room-created-container">
      <div className="room-created-card">
        <form onSubmit={handleJoin} className="unified-form">
          <h2>{isCreating ? 'Enter Chat Room' : 'Join Chat Room'}</h2>
          <p className="form-subtitle">
            {isCreating ? 'Share this code with others' : 'Enter the room code and your name'}
          </p>

          <div className="form-group">
            <label htmlFor="room-code">
              {isCreating ? 'Room Code' : 'Room Code'}
            </label>
            <div className={isCreating ? 'code-display-inline' : 'form-group-input'}>
              <input
                id="room-code"
                type="text"
                placeholder="Enter 6-letter code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                maxLength={6}
                pattern="[A-Z]{0,6}"
                disabled={isCreating || isLoading}
                autoFocus={!isCreating}
                className={isCreating ? 'code-input-display' : ''}
              />
              {isCreating && (
                <button 
                  type="button"
                  className="copy-btn-inline" 
                  onClick={handleCopyCode}
                >
                  {copied ? '✓ Copied!' : 'Copy'}
                </button>
              )}
            </div>
            {isCreating && (
              <div className="info-box">
                <p>
                  <strong>Expiry:</strong> Room will expire after 15 minutes of inactivity
                </p>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="enter-username">Your Name</label>
            <input
              id="enter-username"
              type="text"
              placeholder="Enter your name"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={20}
              disabled={isLoading}
            />
          </div>

          <button 
            type="submit" 
            className="submit-btn" 
            disabled={isLoading || !username.trim() || !code.trim()}
          >
            {isLoading ? 'Entering...' : 'Enter Chat'}
          </button>

          <button 
            type="button"
            className="back-btn" 
            onClick={onBack}
            disabled={isLoading}
          >
            Back
          </button>
        </form>
      </div>
    </div>
  )
}
