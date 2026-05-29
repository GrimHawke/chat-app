import time
import redis
import random
import string
import threading
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chat-app-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Constants
ROOM_EXPIRATION_EMPTY = 600  # 10 minutes in seconds (when room is empty)
MESSAGE_KEY_PREFIX = "room:"
MESSAGES_KEY_PREFIX = "messages:"
USER_KEY_PREFIX = "user:"
ACTIVE_ROOMS_KEY = "active_rooms"  # Set of rooms actively managed by server
ROOM_ACTIVE_USERS_PREFIX = "room:"  # Hash: room:{code}:active_users
MAX_MESSAGES_PER_ROOM = 100  # Maximum messages to store per room

# Track if recovery has been run
recovery_completed = False

# ============================================================================
# Room Management Functions
# ============================================================================

def track_active_room(code):
    """Mark a room as actively managed by the server (no TTL)."""
    redis_client.sadd(ACTIVE_ROOMS_KEY, code)

def untrack_active_room(code):
    """Remove a room from active management (it will get TTL)."""
    redis_client.srem(ACTIVE_ROOMS_KEY, code)

def update_room_user_set(code, socket_id, add=True):
    """Add or remove a user from the room's active users set."""
    key = f"{ROOM_ACTIVE_USERS_PREFIX}{code}:active_users"
    if add:
        redis_client.sadd(key, socket_id)
    else:
        redis_client.srem(key, socket_id)

def recover_orphaned_rooms():
    """
    On server startup, check for rooms that were actively managed but have no connections.
    These rooms crashed while they had users, so we need to clean them up.
    """
    global recovery_completed
    if recovery_completed:
        return
    
    print("[Recovery] Starting orphaned room recovery...")
    active_rooms = redis_client.smembers(ACTIVE_ROOMS_KEY)
    
    recovered_count = 0
    for room_code in active_rooms:
        # Get the room's active users set
        active_users_key = f"{ROOM_ACTIVE_USERS_PREFIX}{room_code}:active_users"
        active_users = redis_client.smembers(active_users_key)
        
        if active_users:
            print(f"[Recovery] Found orphaned room {room_code} with {len(active_users)} users")
            
            # Clean up the active users set
            redis_client.delete(active_users_key)
            
            # Set TTL on the room so it gets cleaned up
            room_key = f"{MESSAGE_KEY_PREFIX}{room_code}"
            room_data = redis_client.get(room_key)
            if room_data:
                redis_client.expire(room_key, ROOM_EXPIRATION_EMPTY)
            
            # Remove room from active tracking
            untrack_active_room(room_code)
            recovered_count += 1
        else:
            # Room exists in active set but has no users - untrack it
            untrack_active_room(room_code)
    
    print(f"[Recovery] Recovered {recovered_count} orphaned rooms")
    recovery_completed = True

def generate_room_code():
    """Generate a unique 6-letter room code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=6))
        if not redis_client.exists(f"{MESSAGE_KEY_PREFIX}{code}"):
            return code

def create_room():
    """Create a new room and return the room code."""
    code = generate_room_code()
    room_data = {
        'code': code,
        'created_at': time.time(),
        'users': []
    }
    # Store room without expiration - it will only expire when empty
    redis_client.set(
        f"{MESSAGE_KEY_PREFIX}{code}",
        json.dumps(room_data)
    )
    return code

def room_exists(code):
    """Check if a room exists."""
    return redis_client.exists(f"{MESSAGE_KEY_PREFIX}{code}") > 0

def add_user_to_room(code, socket_id, username):
    """Add a user to a room."""
    room_key = f"{MESSAGE_KEY_PREFIX}{code}"
    user_key = f"{USER_KEY_PREFIX}{socket_id}"
    
    # Update room data
    room_data = redis_client.get(room_key)
    if room_data:
        room_data = json.loads(room_data)
        if socket_id not in room_data['users']:
            room_data['users'].append(socket_id)
        # Persist room without TTL while users are connected
        redis_client.set(room_key, json.dumps(room_data))
    
    # Track active room and add user to active users set
    track_active_room(code)
    update_room_user_set(code, socket_id, add=True)
    
    # Store user data
    user_data = {
        'socket_id': socket_id,
        'username': username,
        'room': code,
        'joined_at': time.time()
    }
    redis_client.set(user_key, json.dumps(user_data))

def remove_user_from_room(socket_id):
    """Remove a user from their room and set TTL to 10 minutes if empty."""
    user_key = f"{USER_KEY_PREFIX}{socket_id}"
    user_data = redis_client.get(user_key)
    
    if user_data:
        user_data = json.loads(user_data)
        code = user_data['room']
        room_key = f"{MESSAGE_KEY_PREFIX}{code}"
        
        # Remove user from active users set
        update_room_user_set(code, socket_id, add=False)
        
        # Update room data
        room_data = redis_client.get(room_key)
        if room_data:
            room_data = json.loads(room_data)
            if socket_id in room_data['users']:
                room_data['users'].remove(socket_id)
            
            # If no users left, set TTL to 10 minutes for cleanup
            if len(room_data['users']) == 0:
                redis_client.setex(room_key, ROOM_EXPIRATION_EMPTY, json.dumps(room_data))
                untrack_active_room(code)
            else:
                # Keep room persistent while users remain
                redis_client.set(room_key, json.dumps(room_data))
    
    # Remove user data
    redis_client.delete(user_key)

def get_room_users(code):
    """Get list of users in a room."""
    room_key = f"{MESSAGE_KEY_PREFIX}{code}"
    room_data = redis_client.get(room_key)
    if room_data:
        room_data = json.loads(room_data)
        users = []
        for socket_id in room_data['users']:
            user_key = f"{USER_KEY_PREFIX}{socket_id}"
            user_data = redis_client.get(user_key)
            if user_data:
                user_data = json.loads(user_data)
                users.append({
                    'socket_id': socket_id,
                    'username': user_data['username']
                })
        return users
    return []

def get_room_messages(code):
    """Get all messages for a room from Redis list."""
    messages_key = f"{MESSAGES_KEY_PREFIX}{code}"
    messages = redis_client.lrange(messages_key, 0, -1)
    return [json.loads(msg) for msg in messages] if messages else []

def store_message(code, username, message, timestamp):
    """Store a message in the room's message list."""
    messages_key = f"{MESSAGES_KEY_PREFIX}{code}"
    message_data = {
        'username': username,
        'message': message,
        'timestamp': timestamp
    }
    # Push message to the list
    redis_client.rpush(messages_key, json.dumps(message_data))
    # Trim list to keep only the last MAX_MESSAGES_PER_ROOM messages
    redis_client.ltrim(messages_key, -MAX_MESSAGES_PER_ROOM, -1)

# ============================================================================
# HTTP Routes
# ============================================================================

@app.route('/api/time')
def get_current_time():
    return {'time': time.time()}

@app.route('/api/rooms/create', methods=['POST'])
def api_create_room():
    """Create a new room via HTTP API."""
    code = create_room()
    return {'code': code, 'status': 'success'}

@app.route('/api/rooms/<code>/validate', methods=['GET'])
def api_validate_room(code):
    """Check if a room exists."""
    code = code.upper()
    exists = room_exists(code)
    return {'exists': exists, 'code': code}

@app.route('/api/rooms/<code>/users', methods=['GET'])
def api_get_room_users(code):
    """Get list of users in a room via HTTP API."""
    code = code.upper()
    if not room_exists(code):
        return {'error': 'Room not found'}, 404
    users = get_room_users(code)
    return {'users': users, 'status': 'success'}

# ============================================================================
# Socket.IO Events
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection and immediately join the room."""
    from flask import request
    
    # Run recovery once on first connection
    global recovery_completed
    if not recovery_completed:
        recover_orphaned_rooms()
    
    # Get room code and username from query parameters
    room_code = request.args.get('roomCode', '').upper()
    username = request.args.get('username', 'Anonymous')
    socket_id = request.sid
    
    # Check if room exists
    if not room_code or not room_exists(room_code):
        emit('error', {'message': 'Room not found or invalid', 'status': 'error'})
        return
    
    # Add user to room
    add_user_to_room(room_code, socket_id, username)
    
    # Join Socket.IO room
    join_room(room_code)
    
    # Get current users
    users = get_room_users(room_code)
    
    # Send message history to the newly connected user
    messages = get_room_messages(room_code)
    emit('message_history', {
        'messages': messages,
        'status': 'success'
    })
    
    # Notify all users in room about the join
    emit('user_joined', {
        'username': username,
        'users': users,
        'status': 'success'
    }, room=room_code, include_self=True)
    
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnect and notify remaining users."""
    from flask import request
    socket_id = request.sid
    user_key = f"{USER_KEY_PREFIX}{socket_id}"
    user_data = redis_client.get(user_key)
    
    if user_data:
        user_data = json.loads(user_data)
        room_code = user_data['room']
        username = user_data['username']
        
        # Remove user from room
        remove_user_from_room(socket_id)
        
        # Notify remaining users in room
        remaining_users = get_room_users(room_code)
        emit('user_left', {
            'username': username,
            'users': remaining_users,
            'status': 'success'
        }, room=room_code)
    else:
        remove_user_from_room(socket_id)

@socketio.on('send_message')
def handle_send_message(data):
    """Broadcast message to room and store in Redis."""
    from flask import request
    code = data.get('room')
    message = data.get('message')
    username = data.get('username', 'Anonymous')
    timestamp = time.time()
    
    # Validate user is in the specified room
    user_key = f"{USER_KEY_PREFIX}{request.sid}"
    user_data = redis_client.get(user_key)
    if not user_data or json.loads(user_data).get('room') != code:
        emit('error', {'message': 'Not in this room', 'status': 'error'})
        return
    
    # Store message in Redis
    store_message(code, username, message, timestamp)
    
    # Broadcast message to all users in room
    emit('message', {
        'username': username,
        'message': message,
        'timestamp': timestamp
    }, room=code)

@socketio.on('get_room_users')
def handle_get_room_users(data):
    """Get list of users in room."""
    from flask import request
    code = data.get('code')
    
    # Validate user is in this room
    user_key = f"{USER_KEY_PREFIX}{request.sid}"
    user_data = redis_client.get(user_key)
    if not user_data or json.loads(user_data).get('room') != code:
        emit('error', {'message': 'Not in this room', 'status': 'error'})
        return
    
    if room_exists(code):
        users = get_room_users(code)
        emit('room_users', {'users': users, 'status': 'success'})
    else:
        emit('error', {'message': 'Room not found', 'status': 'error'})

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)