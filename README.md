# Chat Application

A real-time chat application with temporary, code-based rooms that expire automatically.

## How It Works

1. **Create or Join a Room**: Users generate a unique 6-letter room code or join existing rooms
2. **Real-Time Messaging**: Messages broadcast instantly to all users in the room via WebSocket
3. **Auto-Cleanup**: Rooms persist while users are connected; empty rooms auto-expire after 10 minutes
4. **Message History**: New users joining a room receive all previous messages

The backend manages room state and message persistence in Redis. Rooms are tracked with TTLs to prevent orphaned data, and users are validated for room membership on every action.

## Tech Stack

### Frontend
- **React** 19 with TypeScript
- **Vite** for fast development and building
- **Socket.io Client** for real-time WebSocket communication
- **Vitest** and React Testing Library for testing

### Backend
- **Flask** 3.1 with Flask-SocketIO for WebSocket support
- **Redis** 7.4 for room management, user tracking, and message storage
- **Python 3.8+** runtime

### Architecture
- **Frontend**: React SPA (Single Page Application) communicates via Socket.io
- **Backend**: Flask HTTP API + Socket.io event handlers
- **Database**: Redis for in-memory data with automatic TTL-based cleanup

## Quick Start

### Prerequisites
- Python 3.8+, Node.js 16+, Redis running on localhost:6379

### Setup

```bash
# Backend (from server/ directory)
cd server
pip install -r requirements.txt
flask run  # Runs on localhost:5000

# Frontend (from frontend/ directory, in new terminal)
cd frontend
npm install
npm run dev  # Runs on localhost:5173
```

### Usage
1. Open `http://localhost:5173`
2. Create a room or join with a code
3. Start chatting—messages appear instantly for all users


## Testing

```bash
# Run backend tests (from server/ directory)
cd server
pytest test_api.py
```

## API Reference

### HTTP Endpoints
- `GET /api/time` - Server timestamp
- `POST /api/rooms/create` - Create new room, returns code
- `GET /api/rooms/<code>/validate` - Check if room exists
- `GET /api/rooms/<code>/users` - Get users in room

### Socket.io Events

**Client → Server:**
- `send_message` - Broadcast message to room
- `get_room_users` - Request user list

**Server → Client:**
- `connected` - Connection established
- `message_history` - Previous messages in room
- `user_joined` - User joined with updated user list
- `message` - New message received
- `user_left` - User left with updated user list
- `error` - Error message

## File Structure

```
chat-app/
├── frontend/                   # Vite React frontend
│   ├── src/
│   │   ├── App.tsx            # Main app component
│   │   ├── LandingPage.tsx    # Room creation/joining
│   │   ├── ChatRoom.tsx       # Chat interface
│   │   ├── RoomJoinForm.tsx   # Room code display
│   │   └── main.tsx           # React entry point
│   ├── index.html             # HTML template
│   ├── package.json           # Node.js dependencies
│   ├── vite.config.ts         # Vite configuration
│   └── vitest.config.ts       # Vitest configuration
├── server/                     # Flask backend
│   ├── api.py                 # Flask backend + Socket.io handlers
│   ├── test_api.py            # Unit tests
│   ├── requirements.txt        # Python dependencies
│   └── requirements-test.txt   # Testing dependencies
├── README.md                   # This file
└── .gitignore
```

## TODO:
- Refactor server code such that different components are separated out into their own files
- Add frontend tests
- Expand application beyond the degenerate case of a single application server such that multiple servers behind a load balancer are supported using Redis pub/sub