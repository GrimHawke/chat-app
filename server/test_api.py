import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import (
    generate_room_code,
    create_room,
    room_exists,
    add_user_to_room,
    remove_user_from_room,
    get_room_users,
    get_room_messages,
    store_message,
    track_active_room,
    untrack_active_room,
    update_room_user_set,
    recover_orphaned_rooms,
    app,
)

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch('api.redis_client') as mock:
        yield mock

@pytest.fixture
def mock_time():
    """Mock time.time() to return a predictable value."""
    with patch('api.time.time', return_value=1000.0):
        yield

@pytest.fixture
def client():
    """Create a test client for Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

class TestRoomManagement:
    def test_generate_room_code_returns_six_letter_code(self, mock_redis):
        """Test that generate_room_code returns a 6-letter uppercase code."""
        mock_redis.exists.return_value = False
        code = generate_room_code()
        assert len(code) == 6
        assert code.isupper()
        assert code.isalpha()

    def test_generate_room_code_avoids_duplicates(self, mock_redis):
        """Test that generate_room_code doesn't return existing codes."""
        # First call returns True (exists), second returns False (doesn't exist)
        mock_redis.exists.side_effect = [True, False]
        code = generate_room_code()
        assert len(code) == 6
        # Check that exists was called twice
        assert mock_redis.exists.call_count == 2

    def test_create_room_stores_room_data(self, mock_redis, mock_time):
        """Test that create_room stores proper room data in Redis."""
        mock_redis.exists.return_value = False
        create_room()
        
        # Check that set was called with proper structure
        assert mock_redis.set.called
        call_args = mock_redis.set.call_args
        room_key = call_args[0][0]
        room_data_str = call_args[0][1]
        room_data = json.loads(room_data_str)
        
        assert 'code' in room_data
        assert 'created_at' in room_data
        assert 'users' in room_data
        assert room_data['users'] == []

    def test_create_room_returns_code(self, mock_redis):
        """Test that create_room returns a room code."""
        mock_redis.exists.return_value = False
        code = create_room()
        assert isinstance(code, str)
        assert len(code) == 6

    def test_room_exists_checks_redis(self, mock_redis):
        """Test that room_exists checks Redis correctly."""
        mock_redis.exists.return_value = 1
        assert room_exists('ABC123') == True
        mock_redis.exists.assert_called_with('room:ABC123')

    def test_room_not_exists(self, mock_redis):
        """Test that room_exists returns False when room doesn't exist."""
        mock_redis.exists.return_value = 0
        assert room_exists('ABC123') == False

    def test_track_active_room(self, mock_redis):
        """Test that track_active_room adds room to active set."""
        track_active_room('ABC123')
        mock_redis.sadd.assert_called_with('active_rooms', 'ABC123')

    def test_untrack_active_room(self, mock_redis):
        """Test that untrack_active_room removes room from active set."""
        untrack_active_room('ABC123')
        mock_redis.srem.assert_called_with('active_rooms', 'ABC123')

    def test_update_room_user_set_add(self, mock_redis):
        """Test adding a user to room's active users set."""
        update_room_user_set('ABC123', 'socket1', add=True)
        mock_redis.sadd.assert_called_with('room:ABC123:active_users', 'socket1')

    def test_update_room_user_set_remove(self, mock_redis):
        """Test removing a user from room's active users set."""
        update_room_user_set('ABC123', 'socket1', add=False)
        mock_redis.srem.assert_called_with('room:ABC123:active_users', 'socket1')

class TestUserManagement:
    def test_add_user_to_room(self, mock_redis, mock_time):
        """Test adding a user to a room."""
        room_data = {'code': 'ABC123', 'created_at': 1000.0, 'users': []}
        mock_redis.get.return_value = json.dumps(room_data).encode()
        
        add_user_to_room('ABC123', 'socket123', 'TestUser')
        
        # Verify room data was updated
        assert mock_redis.set.called
        # Verify user was tracked
        assert mock_redis.sadd.called

    def test_add_user_to_room_existing_users(self, mock_redis, mock_time):
        """Test adding a user to a room that already has users."""
        room_data = {'code': 'ABC123', 'created_at': 1000.0, 'users': ['socket1']}
        mock_redis.get.return_value = json.dumps(room_data).encode()
        
        add_user_to_room('ABC123', 'socket2', 'NewUser')
        
        # Verify set was called twice
        assert mock_redis.set.call_count == 2
        room_call = mock_redis.set.call_args_list[0]
        updated_data = json.loads(room_call.args[1])
        assert 'socket2' in updated_data['users']
        
        user_call = mock_redis.set.call_args_list[1]
        updated_data = json.loads(user_call.args[1])
        assert 'NewUser' in updated_data['username']

    def test_add_user_duplicate_not_added_twice(self, mock_redis, mock_time):
        """Test that adding same user twice doesn't duplicate."""
        room_data = {'code': 'ABC123', 'created_at': 1000.0, 'users': ['socket1']}
        mock_redis.get.return_value = json.dumps(room_data).encode()
        
        add_user_to_room('ABC123', 'socket1', 'TestUser')
        
        # Verify set was called twice
        assert mock_redis.set.call_count == 2
        room_call = mock_redis.set.call_args_list[0]
        updated_data = json.loads(room_call.args[1])
        assert updated_data['users'] == ['socket1']
        assert updated_data['users'].count('socket1') == 1

        user_call = mock_redis.set.call_args_list[1]
        updated_data = json.loads(user_call.args[1])
        assert updated_data['room'] == 'ABC123'
        assert updated_data['username'] == 'TestUser'
        assert updated_data['socket_id'] == 'socket1'

    def test_remove_user_from_room(self, mock_redis):
        """Test removing a user from a room."""
        user_data = {
            'socket_id': 'socket123',
            'username': 'TestUser',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket123']
        }
        
        # Setup mock responses
        mock_redis.get.side_effect = [
            json.dumps(user_data).encode(),
            json.dumps(room_data).encode()
        ]
        
        remove_user_from_room('socket123')
        
        # Verify user was removed
        assert mock_redis.delete.called
        assert mock_redis.srem.called

    def test_remove_user_from_room_sets_ttl_when_empty(self, mock_redis):
        """Test that empty room gets TTL when last user leaves."""
        user_data = {
            'socket_id': 'socket123',
            'username': 'TestUser',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket123']
        }
        
        mock_redis.get.side_effect = [
            json.dumps(user_data).encode(),
            json.dumps(room_data).encode()
        ]
        
        remove_user_from_room('socket123')
        
        # Verify setex was called with TTL
        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 600  # ROOM_EXPIRATION_EMPTY

    def test_remove_user_keeps_room_active_with_other_users(self, mock_redis):
        """Test that room stays active when other users remain."""
        user_data = {
            'socket_id': 'socket123',
            'username': 'TestUser',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket123', 'socket456']
        }
        
        mock_redis.get.side_effect = [
            json.dumps(user_data).encode(),
            json.dumps(room_data).encode()
        ]
        
        remove_user_from_room('socket123')
        
        # Verify set was called (no TTL) instead of setex
        set_calls = [c for c in mock_redis.method_calls if c[0] == 'set']
        assert len(set_calls) > 0

    def test_get_room_users(self, mock_redis, mock_time):
        """Test getting users in a room."""
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket1', 'socket2']
        }
        user1_data = {
            'socket_id': 'socket1',
            'username': 'User1',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        user2_data = {
            'socket_id': 'socket2',
            'username': 'User2',
            'room': 'ABC123',
            'joined_at': 1001.0
        }
        
        mock_redis.get.side_effect = [
            json.dumps(room_data).encode(),
            json.dumps(user1_data).encode(),
            json.dumps(user2_data).encode()
        ]
        
        users = get_room_users('ABC123')
        
        assert len(users) == 2
        assert users[0]['username'] == 'User1'
        assert users[1]['username'] == 'User2'

    def test_get_room_users_empty_room(self, mock_redis):
        """Test getting users from empty room."""
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': []
        }
        
        mock_redis.get.return_value = json.dumps(room_data).encode()
        
        users = get_room_users('ABC123')
        
        assert users == []

    def test_get_room_users_nonexistent_room(self, mock_redis):
        """Test getting users from nonexistent room."""
        mock_redis.get.return_value = None
        
        users = get_room_users('INVALID')
        
        assert users == []

    def test_get_room_users_skips_missing_user_data(self, mock_redis):
        """Test that missing user data is handled gracefully."""
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket1', 'socket2']
        }
        user1_data = {
            'socket_id': 'socket1',
            'username': 'User1',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        
        # socket2 has no data in Redis
        mock_redis.get.side_effect = [
            json.dumps(room_data).encode(),
            json.dumps(user1_data).encode(),
            None
        ]
        
        users = get_room_users('ABC123')
        
        # Only user1 should be returned
        assert len(users) == 1
        assert users[0]['username'] == 'User1'

class TestMessaging:
    def test_store_message(self, mock_redis, mock_time):
        """Test storing a message in Redis."""
        store_message('ABC123', 'TestUser', 'Hello World', 1000.0)
        
        # Verify rpush was called
        assert mock_redis.rpush.called
        call_args = mock_redis.rpush.call_args
        assert call_args[0][0] == 'messages:ABC123'
        
        message_data = json.loads(call_args[0][1])
        assert message_data['username'] == 'TestUser'
        assert message_data['message'] == 'Hello World'
        assert message_data['timestamp'] == 1000.0

    def test_store_message_trims_old_messages(self, mock_redis, mock_time):
        """Test that store_message trims old messages to MAX_MESSAGES_PER_ROOM."""
        store_message('ABC123', 'TestUser', 'Hello World', 1000.0)
        
        # Verify ltrim was called to limit message count
        assert mock_redis.ltrim.called
        call_args = mock_redis.ltrim.call_args
        assert call_args[0][0] == 'messages:ABC123'
        # Should keep last MAX_MESSAGES_PER_ROOM (100) messages
        assert call_args[0][1] == -100
        assert call_args[0][2] == -1

    def test_get_room_messages(self, mock_redis):
        """Test retrieving messages from a room."""
        messages = [
            json.dumps({'username': 'User1', 'message': 'Hello', 'timestamp': 1000.0}).encode(),
            json.dumps({'username': 'User2', 'message': 'Hi there', 'timestamp': 1001.0}).encode()
        ]
        mock_redis.lrange.return_value = messages
        
        result = get_room_messages('ABC123')
        
        assert len(result) == 2
        assert result[0]['message'] == 'Hello'
        assert result[1]['message'] == 'Hi there'

    def test_get_room_messages_empty(self, mock_redis):
        """Test getting messages from a room with no messages."""
        mock_redis.lrange.return_value = []
        
        result = get_room_messages('ABC123')
        
        assert result == []

    def test_get_room_messages_maintains_order(self, mock_redis):
        """Test that messages maintain chronological order."""
        messages = [
            json.dumps({'username': 'User1', 'message': 'First', 'timestamp': 1000.0}).encode(),
            json.dumps({'username': 'User2', 'message': 'Second', 'timestamp': 1001.0}).encode(),
            json.dumps({'username': 'User3', 'message': 'Third', 'timestamp': 1002.0}).encode()
        ]
        mock_redis.lrange.return_value = messages
        
        result = get_room_messages('ABC123')
        
        assert len(result) == 3
        assert result[0]['message'] == 'First'
        assert result[1]['message'] == 'Second'
        assert result[2]['message'] == 'Third'

class TestRecovery:
    def test_recover_orphaned_rooms_cleans_orphaned_room(self, mock_redis):
        """Test that recovery cleans up orphaned rooms."""
        with patch('api.recovery_completed', False):
            with patch.dict('api.__dict__', {'recovery_completed': False}):
                active_rooms = {b'ABC123'}
                mock_redis.smembers.return_value = active_rooms
                mock_redis.smembers.side_effect = [
                    active_rooms,  # First call gets active rooms
                    {b'socket1', b'socket2'}  # Second call gets active users
                ]
                mock_redis.get.return_value = json.dumps({
                    'code': 'ABC123',
                    'created_at': 1000.0,
                    'users': ['socket1', 'socket2']
                }).encode()
                
                # Need to reset recovery_completed flag
                import api
                api.recovery_completed = False
                
                recover_orphaned_rooms()
                
                # Verify cleanup was called
                assert mock_redis.delete.called

    def test_recover_orphaned_rooms_untracks_empty_rooms(self, mock_redis):
        """Test that recovery untracks rooms with no users."""
        with patch('api.recovery_completed', False):
            active_rooms = {b'ABC123'}
            mock_redis.smembers.side_effect = [
                active_rooms,  # First call gets active rooms
                set()  # Second call gets empty active users
            ]
            
            import api
            api.recovery_completed = False
            
            recover_orphaned_rooms()
            
            # Should untrack the room
            assert mock_redis.srem.called

    def test_recover_orphaned_rooms_only_runs_once(self, mock_redis):
        """Test that recovery only runs once."""
        import api
        
        # Reset flag
        api.recovery_completed = False
        
        active_rooms = {b'ABC123'}
        mock_redis.smembers.side_effect = [
            active_rooms,
            set()
        ]
        
        recover_orphaned_rooms()
        assert api.recovery_completed == True
        
        # Reset call count
        mock_redis.reset_mock()
        
        # Call again - should not execute
        recover_orphaned_rooms()
        
        # smembers should not be called again
        assert not mock_redis.smembers.called

class TestHTTPEndpoints:
    def test_api_time_endpoint(self, client, mock_redis):
        """Test /api/time endpoint returns current time."""
        with patch('api.time.time', return_value=1234567890.0):
            response = client.get('/api/time')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'time' in data
            assert data['time'] == 1234567890.0

    def test_api_create_room_endpoint(self, client, mock_redis):
        """Test /api/rooms/create endpoint creates a room."""
        mock_redis.exists.return_value = False
        
        response = client.post('/api/rooms/create')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'code' in data
        assert 'status' in data
        assert data['status'] == 'success'
        assert len(data['code']) == 6

    def test_api_validate_room_exists(self, client, mock_redis):
        """Test /api/rooms/<code>/validate endpoint when room exists."""
        mock_redis.exists.return_value = 1
        
        response = client.get('/api/rooms/abc123/validate')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['exists'] == True
        assert data['code'] == 'ABC123'

    def test_api_validate_room_not_exists(self, client, mock_redis):
        """Test /api/rooms/<code>/validate endpoint when room doesn't exist."""
        mock_redis.exists.return_value = 0
        
        response = client.get('/api/rooms/invalid/validate')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['exists'] == False

    def test_api_get_room_users_success(self, client, mock_redis):
        """Test /api/rooms/<code>/users endpoint returns users."""
        room_data = {
            'code': 'ABC123',
            'created_at': 1000.0,
            'users': ['socket1']
        }
        user1_data = {
            'socket_id': 'socket1',
            'username': 'User1',
            'room': 'ABC123',
            'joined_at': 1000.0
        }
        
        mock_redis.exists.return_value = 1
        mock_redis.get.side_effect = [
            json.dumps(room_data).encode(),
            json.dumps(user1_data).encode()
        ]
        
        response = client.get('/api/rooms/ABC123/users')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'users' in data
        assert 'status' in data
        assert data['status'] == 'success'
        assert len(data['users']) == 1

    def test_api_get_room_users_room_not_found(self, client, mock_redis):
        """Test /api/rooms/<code>/users endpoint when room doesn't exist."""
        mock_redis.exists.return_value = 0
        
        response = client.get('/api/rooms/INVALID/users')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
