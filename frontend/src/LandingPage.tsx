import './LandingPage.css'

interface LandingPageProps {
  isLoading: boolean
  onCreateRoom: () => void
  onJoinRoom: () => void
}

export function LandingPage({ isLoading, onCreateRoom, onJoinRoom }: LandingPageProps) {
  return (
    <div className="landing-container">
      <div className="main-view">
        <div className="header">
          <h1>Chat Room</h1>
          <p>Connect with others in real-time</p>
        </div>

        <div className="button-group">
          <button 
            className="action-btn create-btn" 
            onClick={onCreateRoom}
            disabled={isLoading}
          >
            <span className="icon">✨</span>
            Create a Room
          </button>
          <button 
            className="action-btn join-btn" 
            onClick={onJoinRoom}
            disabled={isLoading}
          >
            <span className="icon">🚪</span>
            Join a Room
          </button>
        </div>
      </div>
    </div>
  )
}
