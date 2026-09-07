"""Role constants. Kept as plain strings (not a DB enum) to match the
existing User.role column, which is a simple String(20).
"""

SUPERUSER = "SuperUser"
ADMIN = "Admin"
OPERATOR = "Operator"

ALL_ROLES = (SUPERUSER, ADMIN, OPERATOR)

# Roles allowed to define/activate receipt templates
CAN_MANAGE_RECEIPTS = (SUPERUSER, ADMIN)

# Roles allowed to manage user accounts
CAN_MANAGE_USERS = (SUPERUSER,)

# Roles allowed to scan
CAN_SCAN = (SUPERUSER, ADMIN, OPERATOR)
