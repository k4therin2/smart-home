# User Management (WP-10.11)

Smart Home Assistant supports multiple user roles with different permission levels.

## User Roles

### Owner
- Full control over all features
- Can manage users and guests
- Can create/modify automations
- Access to security settings
- View command history

### Resident
- Most controls including lights, temperature, music
- Can invite guests
- Can create/modify automations
- Can view command history
- Cannot manage other users

### Guest
- Limited controls: lights, temperature, music
- Cannot view history
- Cannot manage automations
- Cannot access security settings
- Session expires after configurable time (default: 4 hours)

## Guest Access

### Creating a Guest Link

Owners and residents can create password-protected guest links:

```python
from src.security.user_manager import generate_guest_link

link_data = generate_guest_link(
    name="Party Guest",
    password="welcome2024",
    expires_hours=8  # Link expires in 8 hours
)

print(f"Share this link: {link_data['url']}")
```

### Guest Link Features

- Password-protected for security
- Configurable expiration time
- Can be revoked at any time
- Each link creates a unique access token

### Managing Guest Links

```python
from src.security.user_manager import list_active_guest_links, revoke_guest_link

# List all active (non-expired, non-revoked) links
links = list_active_guest_links()
for link in links:
    print(f"{link['name']} - expires {link['expires_at']}")

# Revoke a link
revoke_guest_link(token)
```

## User Preferences

Each user can have personalized preferences:

```python
from src.security.user_manager import save_user_preference, get_user_preference

# Save a preference
save_user_preference("username", "theme", "dark")
save_user_preference("username", "language", "en")

# Get a preference
theme = get_user_preference("username", "theme", default="light")
```

## Command History

Commands are logged per user:

```python
from src.security.user_manager import log_user_command, get_user_history

# Log a command
log_user_command("username", "turn on living room lights", "success")

# Get history (newest first)
history = get_user_history("username", limit=50)
for entry in history:
    print(f"{entry['timestamp']}: {entry['command']} - {entry['result']}")
```

## Permission Checking

```python
from src.security.user_manager import has_permission, has_permission_for_user, UserRole

# Check role permission
if has_permission(UserRole.OWNER, 'manage_users'):
    # Show user management UI
    pass

# Check user object permission
if has_permission_for_user(current_user, 'control_lights'):
    # Allow light control
    pass
```

## Available Permissions

| Permission | Owner | Resident | Guest |
|------------|-------|----------|-------|
| manage_users | Yes | No | No |
| manage_guests | Yes | Yes | No |
| manage_automations | Yes | Yes | No |
| control_lights | Yes | Yes | Yes |
| control_temperature | Yes | Yes | Yes |
| view_history | Yes | Yes | No |
| access_security | Yes | No | No |
| access_settings | Yes | Yes | No |
| control_vacuum | Yes | Yes | No |
| control_music | Yes | Yes | Yes |

## Database Schema

The multi-user system adds the following to the database:

- `users.role` - User role (owner/resident/guest)
- `guest_links` - Guest access tokens and expiration
- `user_preferences` - Per-user settings
- `user_history` - Per-user command history

Initialize with:
```python
from src.security.user_manager import init_user_management_db
init_user_management_db()
```
